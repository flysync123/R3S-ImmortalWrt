#!/usr/bin/env bash
# Run in the configured OpenWrt tree. Retain output and retry once with diagnostics.
set -euo pipefail

[[ -s .config ]] || { echo "Missing .config; run configuration first." >&2; exit 1; }
jobs=${BUILD_JOBS:-$(nproc)}
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo "Invalid BUILD_JOBS: $jobs" >&2; exit 1; }
log_dir=${BUILD_LOG_DIR:-build-logs}
mkdir -p "$log_dir"
SECONDS=0
trap 'status=$?; printf "Compilation finished: status=%s elapsed=%ss\n" "$status" "$SECONDS"' EXIT
printf 'Compiling with %s parallel jobs\n' "$jobs"
if make -j"$jobs" 2>&1 | tee "$log_dir/parallel.log"; then
    exit 0
fi
echo "Parallel compilation failed; retrying once with one job and verbose output."
make -j1 V=s 2>&1 | tee "$log_dir/retry-verbose.log"
