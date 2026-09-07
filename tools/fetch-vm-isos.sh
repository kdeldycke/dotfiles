#!/usr/bin/env bash
#
# Download the installer images for the distributions that meta-package-manager
# cannot exercise anywhere else. Its CI covers Ubuntu, macOS and Windows only,
# so every distribution-native package manager needs a local UTM guest.
#
# Each entry prefers an arm64 image: an arm64 guest runs at native speed on
# Apple Silicon, where an x86_64 guest is emulated and slow. Speed wins over
# size here, so a larger arm64 image beats a small emulated one. Two projects
# publish no arm64 image at all, and fall back to x86_64.
#
# Versions are read from each project's own pointer file or index wherever one
# exists, so this script keeps working after a release.
#
# Usage:
#   fetch-vm-isos.sh [--dry-run] [--only {manager}] [destination]
#
# Options:
#   --dry-run       Resolve and print every URL, download nothing.
#   --only {name}   Act on one package manager only, such as `dnf`.
#   -h, --help      Print this help.
#
# The destination defaults to ~/Downloads/mpm-isos. Downloads resume, and an
# image already complete is left alone, so re-running costs nothing.

set -o errexit -o nounset -o pipefail

dry_run=false
only=""
destination="${HOME}/Downloads/mpm-isos"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) dry_run=true ;;
        --only)
            shift
            only="${1:-}"
            [ -n "${only}" ] || {
                printf -- '--only needs a package manager name\n' >&2
                exit 2
            }
            ;;
        -h | --help)
            # Print the header comment, up to the first blank line, so the help
            # text cannot drift out of range as the comment grows.
            sed -n '3,/^$/p' "$0" | cut -c 3-
            exit 0
            ;;
        -*)
            printf 'Unknown option: %s\n' "$1" >&2
            exit 2
            ;;
        *) destination="$1" ;;
    esac
    shift
done

# Fail on an HTTP error rather than saving an error page, follow redirects, and
# never let one slow mirror hang the whole run.
curl_base=(--location --fail --show-error --connect-timeout 20)
curl_meta=("${curl_base[@]}" --silent --max-time 90)
curl_get=("${curl_base[@]}" --progress-bar --retry 3 --retry-delay 5
    --continue-at - --remote-time)

# dnf. The build suffix moves with every release, so read the current image out
# of the release index instead of pinning one.
resolve_fedora() {
    curl "${curl_meta[@]}" https://fedoraproject.org/releases.json |
        grep -oE 'https://[^"]+Fedora-Server-netinst-aarch64-[0-9]+-[0-9.]+\.iso' |
        sort --version-sort | tail -1
}

# xbps. x86_64 despite the arm64 preference, because `void-installer` is x86
# only: the aarch64 live image boots but cannot install itself, leaving a
# ROOTFS tarball unpacked by hand in a chroot as the only arm64 route. An
# emulated guest beats a manual install here. "base" carries no desktop, and
# the glibc build is the default one; swap "x86_64" for "x86_64-musl" to test
# against musl instead.
resolve_void() {
    local base=https://repo-default.voidlinux.org/live/current
    local file
    file=$(curl "${curl_meta[@]}" "${base}/" |
        grep -oE 'void-live-x86_64-[0-9]{8}-base\.iso' | sort -u | tail -1)
    [ -n "${file}" ] || return 1
    printf '%s/%s\n' "${base}" "${file}"
}

# nix. Each channel redirects to its current build, so only the channel number
# needs walking, newest first.
resolve_nixos() {
    local channel url
    for channel in 27.05 26.11 26.05 25.11; do
        url="https://channels.nixos.org/nixos-${channel}/latest-nixos-minimal-aarch64-linux.iso"
        if curl "${curl_meta[@]}" --head --output /dev/null "${url}" 2>/dev/null; then
            printf '%s\n' "${url}"
            return 0
        fi
    done
    return 1
}

# emerge. distfiles.gentoo.org answers a non-browser client with an empty body,
# so the pointer file has to come from a mirror that serves it.
resolve_gentoo() {
    local base=https://gentoo.osuosl.org/releases/arm64/autobuilds
    local path
    path=$(curl "${curl_meta[@]}" "${base}/latest-install-arm64-minimal.txt" |
        grep -oE '[0-9]{8}T[0-9]{6}Z/install-arm64-minimal-[0-9]{8}T[0-9]{6}Z\.iso' |
        tail -1)
    [ -n "${path}" ] || return 1
    printf '%s/%s\n' "${base}" "${path}"
}

# guix. Release 1.5.0 was the first to ship an arm64 image.
resolve_guix() {
    local base=https://ftp.gnu.org/gnu/guix
    local file
    file=$(curl "${curl_meta[@]}" "${base}/" |
        grep -oE 'guix-system-install-[0-9.]+\.aarch64-linux\.iso' |
        sort -u --version-sort | tail -1)
    [ -n "${file}" ] || return 1
    printf '%s/%s\n' "${base}" "${file}"
}

# eopkg. Solus publishes x86_64 only, and only as desktop editions. Xfce is the
# smallest of the four, and the guest runs emulated whichever one is picked.
resolve_solus() {
    printf '%s\n' https://downloads.getsol.us/isos/latest/Solus-Latest-Xfce.iso
}

# tazpkg. SliTaz is x86 only, and "core64" is its x86_64 build. At well under
# 100 MB the emulation cost of running it is small.
resolve_slitaz() {
    printf '%s\n' http://mirror.slitaz.org/iso/rolling/slitaz-rolling-core64.iso
}

# Package manager, image, architecture, resolver.
guests=(
    "dnf|Fedora Server netinst|arm64|resolve_fedora"
    "xbps|Void Linux base|x86_64|resolve_void"
    "nix|NixOS minimal|arm64|resolve_nixos"
    "emerge|Gentoo minimal|arm64|resolve_gentoo"
    "guix|Guix System|arm64|resolve_guix"
    "eopkg|Solus Xfce|x86_64|resolve_solus"
    "tazpkg|SliTaz core64|x86_64|resolve_slitaz"
)

# Read the size the server reports, so a complete image is never fetched twice.
# With redirects followed there is one header block per hop, and the last
# Content-Length is the one that describes the file.
remote_size() {
    curl "${curl_meta[@]}" --head "$1" | tr -d '\r' |
        awk 'tolower($1) == "content-length:" { size = $2 } END { print size + 0 }'
}

human_size() {
    awk -v bytes="$1" 'BEGIN { printf "%.0f MB", bytes / 1048576 }'
}

"${dry_run}" || mkdir -p "${destination}"

total_bytes=0
handled=0
failed=()

for guest in "${guests[@]}"; do
    IFS='|' read -r manager image arch resolver <<<"${guest}"

    if [ -n "${only}" ] && [ "${only}" != "${manager}" ]; then
        continue
    fi
    handled=$((handled + 1))

    printf '\n=== %s (%s, %s) ===\n' "${image}" "${manager}" "${arch}"

    if ! url=$("${resolver}"); then
        printf '    could not resolve a URL\n' >&2
        failed+=("${manager}")
        continue
    fi
    printf '    %s\n' "${url}"

    size=$(remote_size "${url}")
    total_bytes=$((total_bytes + size))
    printf '    %s\n' "$(human_size "${size}")"

    "${dry_run}" && continue

    output="${destination}/${url##*/}"
    if [ -f "${output}" ] && [ "$(wc -c <"${output}" | tr -d ' ')" = "${size}" ]; then
        printf '    already complete\n'
        continue
    fi

    if ! curl "${curl_get[@]}" --output "${output}" "${url}"; then
        printf '    download failed\n' >&2
        failed+=("${manager}")
    fi
done

if [ "${handled}" -eq 0 ]; then
    printf 'No package manager matches --only %s\n' "${only}" >&2
    exit 2
fi

printf '\n%s across %d images' "$(human_size "${total_bytes}")" "${handled}"
"${dry_run}" && printf ' (resolved only, nothing downloaded)'
printf '\n'
"${dry_run}" || printf 'Saved under %s\n' "${destination}"

if [ "${#failed[@]}" -gt 0 ]; then
    printf 'Failed: %s\n' "${failed[*]}" >&2
    exit 1
fi
