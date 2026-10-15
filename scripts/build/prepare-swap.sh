#!/usr/bin/env bash
# Reuse sufficient runner swap; never resize or reformat an existing swap file.
set -euo pipefail

swapfile=/swapfile-r3s-build
required_kib=8388608
swap_kib=$(awk '$1 == "SwapTotal:" {print $2; found++} END {if (found != 1) exit 1}' /proc/meminfo)
[[ "$swap_kib" =~ ^[0-9]+$ ]] || { echo "Cannot determine existing swap capacity" >&2; exit 1; }
if (( swap_kib >= required_kib )); then
    echo "Reusing existing swap ($swap_kib KiB)."
    exit 0
fi

[[ -r /proc/swaps ]] || { echo "Cannot read active swap devices" >&2; exit 1; }
if awk -v path="$swapfile" '$1 == path {found=1} END {exit !found}' /proc/swaps; then
    echo "$swapfile is already active; insufficient total swap cannot be expanded safely here." >&2
    exit 1
fi
if [[ -e "$swapfile" || -L "$swapfile" ]]; then
    echo "Refusing to overwrite an existing file: $swapfile" >&2
    exit 1
fi

# noclobber reserves a new path even if another process creates it after the check.
umask 077
(set -o noclobber; : > "$swapfile")
chmod 600 "$swapfile"
fallocate -l 8G "$swapfile" || dd if=/dev/zero of="$swapfile" bs=1M count=8192
mkswap "$swapfile"
swapon "$swapfile"
echo "Added dedicated build swap: $swapfile"
