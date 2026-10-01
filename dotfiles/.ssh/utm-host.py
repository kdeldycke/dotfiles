#!/usr/bin/python3
"""Resolve a UTM virtual machine to its current IP address, by MAC address.

A UTM guest takes its address from DHCP, whether it sits on the host's shared
network or bridges onto the LAN, and that address moves. The MAC address does
not: UTM pins it in the guest's own `config.plist`. So this script reads the
MAC from there, finds the matching entry in the host ARP table, and prints the
address.

That indirection keeps addresses out of `~/.ssh/config`, which is a public
file. It also survives a move to a different network.

macOS hides the ARP table, and the MAC addresses `netstat` prints, from any
process with an ad-hoc signed binary among its ancestors: under a Homebrew or
uv Python 3.14, or under Homebrew's `ssh` running this script as its
`ProxyCommand`, `arp -an` prints nothing, measured on macOS 27. So the script
runs under Apple's own `/usr/bin/python3`, and stays compatible with its Python
3.9, and it has two more sources:

- The leases file of macOS's own DHCP server, which any process can read. It
  covers every guest on UTM's shared network.
- The host key `~/.ssh/known_hosts_utm` holds for the alias, matched against
  what each host answering on the port presents. It covers a bridged guest,
  and since ssh checks that key anyway, it cannot land on another machine. The
  last address found this way is cached, so the scan stays rare.

Usage:
    utm-host.py list                     Show every virtual machine and address.
    utm-host.py ip {alias}               Print one address.
    utm-host.py connect {alias} {port}   Open a connection, for `ProxyCommand`.

An alias is the first word of the virtual machine name, in lower case:
"Ubuntu 26.06 LTS" answers to `ubuntu`.
"""

from __future__ import annotations

import ipaddress
import json
import os
import plistlib
import re
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import NoReturn

UTM_DOCUMENTS = Path.home() / "Library/Containers/com.utmapp.UTM/Data/Documents"

# Written by macOS's DHCP server for its shared networks, readable by anyone.
DHCP_LEASES = Path("/var/db/dhcpd_leases")

# Where the ssh configuration keeps the host keys of these guests.
KNOWN_HOSTS = Path.home() / ".ssh/known_hosts_utm"

# The last address each alias answered at.
ADDRESS_CACHE = Path.home() / ".cache/utm-host.json"

# macOS `arp` prints each octet without its leading zero, so both sides of a
# comparison must be reduced to that form before they can match.
ARP_ENTRY = re.compile(r"\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-fA-F:]+)")

# A network wider than this is narrowed to this prefix around the host's own
# address rather than skipped. A router handing out a /8 is common, and sweeping
# 16 million addresses is not an option, but a DHCP pool sits next to the host
# it served, so the neighbouring /24 finds the guests in practice.
WIDEST_SWEEPABLE_PREFIX = 24

# Addresses that belong to no reachable network: the unspecified block, the
# loopback, and link-local.
UNSWEEPABLE_PREFIXES = ("0.", "127.", "169.254.")


def fail(message: str) -> NoReturn:
    """Report a failure and stop.

    ssh discards what a `ProxyCommand` writes to stderr once connection
    sharing is on, and reports only `Connection closed by UNKNOWN port 65535`.
    Writing to the terminal as well is what puts the real reason in front of
    the person who has to act on it.
    """
    for stream in (sys.stderr, None):
        try:
            if stream is None:
                with open("/dev/tty", "w", encoding="UTF-8") as tty:
                    tty.write(message + "\n")
            else:
                stream.write(message + "\n")
        except OSError:
            pass
    raise SystemExit(1)


def normalize_mac(mac: str) -> str:
    """Strip the leading zero from each octet, and lower the case."""
    return ":".join(octet.lstrip("0") or "0" for octet in mac.lower().split(":"))


def virtual_machines() -> dict[str, dict[str, str]]:
    """Map each alias to the name and MAC address of its virtual machine."""
    machines: dict[str, dict[str, str]] = {}
    for bundle in sorted(UTM_DOCUMENTS.glob("*.utm")):
        config = bundle / "config.plist"
        if not config.exists():
            continue
        data = plistlib.loads(config.read_bytes())
        networks = data.get("Network") or []
        if not networks:
            continue
        name = (data.get("Information") or {}).get("Name") or bundle.stem
        alias = re.sub(r"[^a-z0-9]", "", name.split()[0].lower())
        # A second machine claiming an alias takes its full name instead, so
        # one machine cannot shadow another.
        if alias in machines:
            alias = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        machines[alias] = {
            "name": name,
            "mac": normalize_mac(networks[0]["MacAddress"]),
        }
    return machines


def arp_table() -> dict[str, list[str]]:
    """Map each known MAC address to the IP addresses claiming it.

    One MAC address can hold several entries at once: macOS keeps a stale entry
    for around twenty minutes, so a guest that moved to a new address still
    answers under the old one until that entry expires.
    """
    output = subprocess.run(
        ["arp", "-an"], capture_output=True, text=True, encoding="UTF-8", check=False
    ).stdout
    table: dict[str, list[str]] = {}
    for line in output.splitlines():
        match = ARP_ENTRY.search(line)
        if match:
            table.setdefault(normalize_mac(match.group(2)), []).append(match.group(1))
    return table


def dhcp_leases() -> dict[str, list[str]]:
    """Map each MAC address to the addresses macOS's DHCP server leased it.

    An expired lease is left out, so a guest that moved to a bridged network
    costs no connection attempt at its old address. The newest lease comes
    first.
    """
    try:
        text = DHCP_LEASES.read_text(encoding="UTF-8")
    except OSError:
        return {}
    leases = []
    for block in re.findall(r"\{(.*?)\}", text, re.DOTALL):
        fields = dict(re.findall(r"^\s*(\w+)=(.*)$", block, re.MULTILINE))
        address = fields.get("ip_address")
        hardware = fields.get("hw_address", "")
        expiry = int(fields.get("lease", "0x0"), 16)
        if address and "," in hardware and expiry > time.time():
            leases.append((expiry, normalize_mac(hardware.split(",", 1)[1]), address))
    table: dict[str, list[str]] = {}
    for _, mac, address in sorted(leases, reverse=True):
        table.setdefault(mac, []).append(address)
    return table


def port_answers(address: str, port: int, timeout: float = 2.0) -> bool:
    """Tell whether a TCP port accepts a connection."""
    try:
        with socket.create_connection((address, port), timeout):
            return True
    except OSError:
        return False


def local_networks() -> list[ipaddress.IPv4Network]:
    """List the IPv4 networks this host sits on, without the loopback."""
    output = subprocess.run(
        ["ifconfig"], capture_output=True, text=True, encoding="UTF-8", check=False
    ).stdout
    networks = []
    for address, netmask in re.findall(
        r"inet (\d+\.\d+\.\d+\.\d+) netmask (0x[0-9a-f]+)", output
    ):
        if address.startswith(UNSWEEPABLE_PREFIXES):
            continue
        # Count the set bits through `bin()`: `int.bit_count()` needs Python 3.10.
        bits = bin(int(netmask, 16)).count("1")  # noqa: FURB161
        prefix = max(bits, WIDEST_SWEEPABLE_PREFIX)
        network = ipaddress.IPv4Network(f"{address}/{prefix}", strict=False)
        if network not in networks:
            networks.append(network)
    return networks


def populate_arp_table() -> None:
    """Ping every address on the local networks, to fill the ARP table.

    A guest quiet for long enough that its ARP entry expired is invisible
    until something talks to it again.
    """
    targets = [str(host) for network in local_networks() for host in network.hosts()]
    with ThreadPoolExecutor(max_workers=256) as pool:
        list(
            pool.map(
                lambda ip: subprocess.run(
                    ["ping", "-c", "1", "-W", "300", "-t", "1", ip],
                    capture_output=True,
                    check=False,
                ),
                targets,
            )
        )


def known_host_keys(alias: str) -> set[str]:
    """The host keys recorded for an alias, each as `type base64`."""
    found = subprocess.run(
        ["ssh-keygen", "-F", alias, "-f", str(KNOWN_HOSTS)],
        capture_output=True,
        text=True,
        encoding="UTF-8",
        check=False,
    ).stdout
    keys = set()
    for line in found.splitlines():
        fields = line.split()
        if len(fields) >= 3 and not line.startswith("#"):
            keys.add(f"{fields[1]} {fields[2]}")
    return keys


def presents_key(address: str, port: int, keys: set[str]) -> bool:
    """Tell whether the SSH server at an address presents one of `keys`."""
    scan = subprocess.run(
        ["ssh-keyscan", "-T", "3", "-p", str(port), address],
        capture_output=True,
        text=True,
        encoding="UTF-8",
        check=False,
    ).stdout
    for line in scan.splitlines():
        fields = line.split()
        if len(fields) >= 3 and f"{fields[1]} {fields[2]}" in keys:
            return True
    return False


def cached_addresses() -> dict[str, str]:
    """The last address each alias answered at."""
    try:
        return json.loads(ADDRESS_CACHE.read_text(encoding="UTF-8"))
    except (OSError, ValueError):
        return {}


def remember(alias: str, address: str) -> None:
    """Cache the address an alias answered at, for `find_by_host_key` to try
    first."""
    cache = cached_addresses()
    if cache.get(alias) == address:
        return
    cache[alias] = address
    try:
        ADDRESS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        ADDRESS_CACHE.write_text(json.dumps(cache, indent=2) + "\n", encoding="UTF-8")
    except OSError:
        pass


def find_by_host_key(alias: str, port: int) -> str | None:
    """Find the address presenting the host key recorded for an alias.

    Tries the cached address, then every host of the local networks that
    answers on the port.
    """
    keys = known_host_keys(alias)
    if not keys:
        return None
    cached = cached_addresses().get(alias)
    if cached and port_answers(cached, port) and presents_key(cached, port, keys):
        return cached
    targets = [str(host) for network in local_networks() for host in network.hosts()]
    with ThreadPoolExecutor(max_workers=256) as pool:
        answers = list(pool.map(lambda ip: port_answers(ip, port, 0.5), targets))
    for address, answered in zip(targets, answers):
        if answered and address != cached and presents_key(address, port, keys):
            remember(alias, address)
            return address
    return None


def resolve(alias: str, port: int = 22) -> str:
    """Return the IP address of the virtual machine known under an alias.

    The port decides between competing entries, and catches a stale one: an
    address that no longer answers is worth less than a fresh sweep.
    """
    machines = virtual_machines()
    if alias not in machines:
        known = ", ".join(sorted(machines)) or "none"
        fail(f"utm-host: unknown virtual machine {alias!r}. Known: {known}.")
    mac = machines[alias]["mac"]

    seen: list[str] = []
    for sweep_first in (False, True):
        if sweep_first:
            populate_arp_table()
        arp = arp_table()
        seen = list(dict.fromkeys(arp.get(mac, []) + dhcp_leases().get(mac, [])))
        for address in seen:
            if port_answers(address, port):
                remember(alias, address)
                return address
        # A hidden table stays hidden: a sweep cannot help.
        if not arp:
            break

    if not arp:
        address = find_by_host_key(alias, port)
        if address:
            return address
        fail(
            f"utm-host: no address for {alias!r} ({mac}). macOS hides the ARP "
            "table from this process, as it does under an ad-hoc signed ssh "
            "like Homebrew's, and no local host on port "
            f"{port} presents the host key known for {alias!r}. Is the virtual "
            "machine started? A rebuilt guest has a new key: connect once "
            "with /usr/bin/ssh to record it."
        )

    if seen:
        fail(
            f"utm-host: {alias!r} ({mac}) is known at {', '.join(seen)}, but "
            f"nothing answers on port {port} there. The guest is stopped, or "
            "its service is down and the address is a stale ARP entry."
        )
    fail(
        f"utm-host: no address for {alias!r} ({mac}). "
        "Is the virtual machine started, and has it taken a DHCP address yet?"
    )


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    command = sys.argv[1]

    if command == "list":
        populate_arp_table()
        table = dhcp_leases()
        for mac, addresses in arp_table().items():
            table[mac] = list(dict.fromkeys(addresses + table.get(mac, [])))
        for alias, machine in sorted(virtual_machines().items()):
            addresses = table.get(machine["mac"], [])
            reachable = [a for a in addresses if port_answers(a, 22, timeout=1.0)]
            address = (
                reachable[0] if reachable else (addresses[0] if addresses else "-")
            )
            state = "ssh" if reachable else ("no ssh" if addresses else "stopped")
            print(
                f"{alias:<12} {machine['name']:<20} {machine['mac']:<18} "
                f"{address:<15} {state}"
            )

    elif command == "ip":
        print(resolve(sys.argv[2]))

    elif command == "connect":
        # `nc` moves the bytes. Replacing this process with it keeps ssh in
        # direct control of the connection it owns.
        port = sys.argv[3]
        os.execvp("nc", ["nc", resolve(sys.argv[2], int(port)), port])

    else:
        sys.exit(f"utm-host: unknown command {command!r}.")


if __name__ == "__main__":
    main()
