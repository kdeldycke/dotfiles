#!/usr/bin/env python3
"""Resolve a UTM virtual machine to its current IP address, by MAC address.

A UTM guest takes its address from DHCP, whether it sits on the host's shared
network or bridges onto the LAN, and that address moves. The MAC address does
not: UTM pins it in the guest's own `config.plist`. So this script reads the
MAC from there, finds the matching entry in the host ARP table, and prints the
address.

That indirection keeps addresses out of `~/.ssh/config`, which is a public
file. It also survives a move to a different network.

Usage:
    utm-host.py list                     Show every virtual machine and address.
    utm-host.py ip {alias}               Print one address.
    utm-host.py connect {alias} {port}   Open a connection, for `ProxyCommand`.

An alias is the first word of the virtual machine name, in lower case:
"Ubuntu 26.06 LTS" answers to `ubuntu`.
"""

from __future__ import annotations

import ipaddress
import os
import plistlib
import re
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import NoReturn

UTM_DOCUMENTS = Path.home() / "Library/Containers/com.utmapp.UTM/Data/Documents"

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
        prefix = max(int(netmask, 16).bit_count(), WIDEST_SWEEPABLE_PREFIX)
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
        seen = arp_table().get(mac, [])
        for address in seen:
            if port_answers(address, port):
                return address

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
        table = arp_table()
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
