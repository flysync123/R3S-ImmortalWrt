#!/usr/bin/env bash
# Collect firmware and the inputs needed to identify a build. Run after compilation.
set -euo pipefail

: "${GITHUB_WORKSPACE:?}"
: "${GITHUB_ENV:?}"
: "${GITHUB_RUN_ID:?}"
: "${GITHUB_RUN_ATTEMPT:?}"
: "${BUILD_DIR:?}"
: "${RELEASE_ROUTE:?}"
: "${RELEASE_VERSION:?}"
: "${TARGET:?}"
: "${SUBTARGET:?}"
: "${PROFILE:?}"
: "${ROOTFS_PARTSIZE:?}"

case "$RELEASE_ROUTE" in
    ImageBuilder|Source) project=ImmortalWrt ;;
    Customer) project=OpenWrt ;;
    *) echo "Unknown release route: $RELEASE_ROUTE" >&2; exit 1 ;;
esac
[[ "$GITHUB_RUN_ID" =~ ^[0-9]+$ && "$GITHUB_RUN_ATTEMPT" =~ ^[0-9]+$ ]] || exit 1
[[ "$TARGET" =~ ^[a-z0-9_-]+$ && "$SUBTARGET" =~ ^[a-z0-9_-]+$ && "$PROFILE" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 1

build_dir=$(cd "$BUILD_DIR" && pwd)
output_dir="$build_dir/bin/targets/$TARGET/$SUBTARGET"
metadata_dir="$output_dir"
if [[ "$RELEASE_ROUTE" == ImageBuilder ]]; then
    metadata_dir="$GITHUB_WORKSPACE/imagebuilder-buildinfo"
fi
release_dir="$GITHUB_WORKSPACE/release_files"
version=$(printf '%s' "$RELEASE_VERSION" | LC_ALL=C tr -cs 'A-Za-z0-9._-' '-' | cut -c1-48)
[[ -n "$version" ]] || { echo "Empty release version" >&2; exit 1; }
upstream_revision=prebuilt
if [[ "$RELEASE_ROUTE" != ImageBuilder ]]; then
    upstream_revision=$(git -C "$build_dir" rev-parse HEAD)
    version="$version-${upstream_revision:0:12}"
fi
release_tag="$project-R3S-$RELEASE_ROUTE-$version-$GITHUB_RUN_ID.$GITHUB_RUN_ATTEMPT"

# A separate name for every route/run/attempt prevents a rerun from replacing assets.
if [[ -d "$release_dir" && -n "$(find "$release_dir" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "Release directory is not empty: $release_dir" >&2
    exit 1
fi
mkdir -p "$release_dir"
shopt -s nullglob
images=("$output_dir/"*"$PROFILE"*.img.gz)
# Full source builds can emit one manifest for the entire target/subtarget.
manifests=("$output_dir/"*.manifest)
(( ${#images[@]} > 0 )) || { echo "No firmware found for $PROFILE" >&2; exit 1; }
(( ${#manifests[@]} > 0 )) || { echo "No package manifest found for $TARGET/$SUBTARGET" >&2; exit 1; }
[[ -s "$metadata_dir/config.buildinfo" ]] || { echo "Missing config.buildinfo" >&2; exit 1; }
for file in "${images[@]}"; do
    cp "$file" "$release_dir/$release_tag-$(basename "$file")"
done
for file in "${manifests[@]}" "$metadata_dir/"*.buildinfo "$output_dir/profiles.json"; do
    [[ ! -f "$file" ]] || cp "$file" "$release_dir/"
done
if [[ -f "$build_dir/.config" ]]; then
    config_name=final.config
    [[ "$RELEASE_ROUTE" != ImageBuilder ]] || config_name=imagebuilder.config
    cp "$build_dir/.config" "$release_dir/$config_name"
elif [[ "$RELEASE_ROUTE" != ImageBuilder ]]; then
    echo "Missing expanded .config" >&2
    exit 1
fi
if [[ -f "$build_dir/feeds.conf.default" ]]; then
    cp "$build_dir/feeds.conf.default" "$release_dir/feeds.conf.default"
fi
if [[ -f "$build_dir/feeds.conf" ]]; then
    cp "$build_dir/feeds.conf" "$release_dir/feeds.conf"
fi
if [[ -f "$build_dir/.config.requested" ]]; then
    cp "$build_dir/.config.requested" "$release_dir/requested.config"
fi
if [[ -f "$build_dir/customer-dependencies.tsv" ]]; then
    cp "$build_dir/customer-dependencies.tsv" "$release_dir/"
fi

{
    printf 'release_tag=%s\nroute=%s\nrequested_version=%s\n' "$release_tag" "$RELEASE_ROUTE" "$RELEASE_VERSION"
    printf 'upstream_revision=%s\ncustomization_revision=%s\n' "$upstream_revision" "${GITHUB_SHA:-unknown}"
    printf 'target=%s/%s\nprofile=%s\nrootfs_partsize_mib=%s\n' "$TARGET" "$SUBTARGET" "$PROFILE" "$ROOTFS_PARTSIZE"
    printf 'run_url=https://github.com/%s/actions/runs/%s\nrun_attempt=%s\n' "${GITHUB_REPOSITORY:-unknown}" "$GITHUB_RUN_ID" "$GITHUB_RUN_ATTEMPT"
    printf 'built_at_utc=%s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    if [[ "$RELEASE_ROUTE" == ImageBuilder ]]; then
        printf 'imagebuilder_url=%s\npackages=%s\n' "${IB_URL:?}" "${PACKAGES:?}"
        printf 'buildinfo_origin=official ImageBuilder baseline; actual packages are recorded in the manifest\n'
    fi
} > "$release_dir/build-info.txt"

# Record standalone plugin repos as well as feeds, including nested toolchain repos.
{
    printf 'path\tcommit\torigin\n'
    record_revision() {
        local path=$1 label=$2 origin revision
        revision=$(git -C "$path" rev-parse HEAD)
        origin=$(git -C "$path" remote get-url origin 2>/dev/null || true)
        origin=$(printf '%s' "$origin" | sed -E 's#(https?://)[^/@]+@#\1[redacted]@#')
        printf '%s\t%s\t%s\n' "$label" "$revision" "$origin"
    }
    record_revision "$GITHUB_WORKSPACE" customization
    if [[ "$RELEASE_ROUTE" != ImageBuilder ]]; then
        record_revision "$build_dir" upstream
        for directory in "$build_dir/feeds" "$build_dir/package"; do
            [[ -d "$directory" ]] || continue
            while IFS= read -r -d '' dotgit; do
                repository=${dotgit%/.git}
                record_revision "$repository" "${repository#"$build_dir/"}"
            done < <(find "$directory" -name .git -prune -print0)
        done
    fi
} > "$release_dir/source-revisions.tsv"

if [[ "$RELEASE_ROUTE" == ImageBuilder ]]; then
    cp "$GITHUB_WORKSPACE/imagebuilder.sha256" "$release_dir/"
    cp "$metadata_dir/sha256sums" "$release_dir/imagebuilder-buildinfo.sha256"
fi
(
    cd "$release_dir"
    sha256sum -- * > sha256sums.txt
)
printf 'RELEASE_TAG=%s\nRELEASE_TITLE=%s for NanoPi R3S (%s)\n' "$release_tag" "$project $RELEASE_ROUTE $version" "$GITHUB_RUN_ID.$GITHUB_RUN_ATTEMPT" >> "$GITHUB_ENV"
