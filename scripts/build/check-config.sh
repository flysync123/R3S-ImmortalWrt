#!/usr/bin/env bash
# Fail before compilation if dependency resolution drops requested features.
set -euo pipefail

requested=${1:?Usage: check-config.sh requested.config final.config}
resolved=${2:?Usage: check-config.sh requested.config final.config}
[[ -s "$requested" && -s "$resolved" ]] || { echo "Missing configuration input" >&2; exit 1; }
missing=0
while IFS= read -r option; do
    case "$option" in
        CONFIG_*=y|CONFIG_TARGET_ROOTFS_PARTSIZE=*)
            if ! grep -Fqx -- "$option" "$resolved"; then
                printf 'Required configuration was dropped or changed: %s\n' "$option" >&2
                missing=1
            fi
            ;;
    esac
done < "$requested"
exit "$missing"
