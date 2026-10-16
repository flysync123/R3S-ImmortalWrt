"""Check release collection with fake build outputs and a local Git mock.

No firmware is built, downloaded, published, or written to a device.
Only Python's standard library and Bash/coreutils are needed.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
if os.name == "nt":
    BASH = r"C:\Program Files\Git\usr\bin\bash.exe"
REVISION = "0123456789abcdef0123456789abcdef01234567"


def shell_path(path):
    value = Path(path).resolve().as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


@unittest.skipUnless(BASH and Path(BASH).is_file(), "Bash is required")
class BuildHelpersTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="r3s-build-test-")
        self.addCleanup(self.scratch.cleanup)
        self.tree = Path(self.scratch.name)
        self.bin = self.tree / "bin"
        self.bin.mkdir()
        self.build = self.tree / "build"
        self.output = self.build / "bin/targets/rockchip/armv8"
        self.output.mkdir(parents=True)
        self.release = self.tree / "release_files"
        self.write("bin/git", f'''#!/bin/bash
case "$3" in
    rev-parse) printf '%s\\n' '{REVISION}' ;;
    remote) printf '%s\\n' 'https://example.invalid/fixture.git' ;;
    *) exit 90 ;;
esac
''')
        self.write("build/.config", "CONFIG_PACKAGE_luci=y\n")
        self.write("build/.config.requested", "CONFIG_PACKAGE_luci=y\n")
        self.write("build/customer-dependencies.tsv", "name\turl\trevision\n")
        for name in ("config.buildinfo", "feeds.buildinfo", "version.buildinfo"):
            self.write("build/bin/targets/rockchip/armv8/" + name, "fixture metadata\n")
        self.write("build/bin/targets/rockchip/armv8/profiles.json", "{}\n")
        self.write("build/bin/targets/rockchip/armv8/openwrt-rockchip-armv8.manifest", "luci - fixture\n")
        for filesystem in ("squashfs", "ext4"):
            name = f"openwrt-friendlyarm_nanopi-r3s-{filesystem}-sysupgrade.img.gz"
            (self.output / name).write_bytes(b"fixture " + filesystem.encode())
        for relative in ("feeds/packages", "feeds/packages/lang/golang", "package/custom/example"):
            (self.build / relative / ".git").mkdir(parents=True)
        self.env = dict(os.environ, GITHUB_WORKSPACE=shell_path(self.tree),
                        GITHUB_ENV=shell_path(self.tree / "github.env"),
                        GITHUB_RUN_ID="123456789", GITHUB_RUN_ATTEMPT="1",
                        GITHUB_REPOSITORY="example/fixture", GITHUB_SHA=REVISION,
                        BUILD_DIR=shell_path(self.build), RELEASE_ROUTE="Source",
                        RELEASE_VERSION="openwrt-25.12", TARGET="rockchip",
                        SUBTARGET="armv8", PROFILE="friendlyarm_nanopi-r3s",
                        ROOTFS_PARTSIZE="4096")

    def write(self, relative, content):
        target = self.tree / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        target.chmod(0o755)
        return target

    def run_helper(self, helper, *arguments):
        return subprocess.run(
            [BASH, "--noprofile", "--norc", "-c",
             'export PATH="$1:/usr/bin:/bin:$PATH"; shift; exec bash "$@"',
             "test-build", shell_path(self.bin),
             shell_path(ROOT / "scripts/build" / helper),
             *(shell_path(argument) for argument in arguments)],
            cwd=self.tree, env=self.env, capture_output=True, text=True,
            encoding="utf-8", timeout=20,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def check_config(self, resolved):
        requested = self.write("requested.config", "CONFIG_PACKAGE_luci=y\nCONFIG_TARGET_ROOTFS_PARTSIZE=4096\nCONFIG_PACKAGE_docker=n\n")
        final = self.write("final.config", resolved)
        return self.run_helper("check-config.sh", requested, final)

    def test_config_checker_accepts_dependency_expansion(self):
        result = self.check_config("CONFIG_PACKAGE_luci=y\nCONFIG_TARGET_ROOTFS_PARTSIZE=4096\n# CONFIG_PACKAGE_docker is not set\nCONFIG_PACKAGE_libc=y\n")
        self.assert_success(result)

    def test_config_checker_rejects_missing_required_package(self):
        result = self.check_config("CONFIG_TARGET_ROOTFS_PARTSIZE=4096\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CONFIG_PACKAGE_luci=y", result.stderr)

    def test_config_checker_rejects_module_instead_of_builtin(self):
        result = self.check_config("CONFIG_PACKAGE_luci=m\nCONFIG_TARGET_ROOTFS_PARTSIZE=4096\n")
        self.assertNotEqual(result.returncode, 0)

    def test_config_checker_rejects_changed_rootfs_size(self):
        result = self.check_config("CONFIG_PACKAGE_luci=y\nCONFIG_TARGET_ROOTFS_PARTSIZE=2048\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CONFIG_TARGET_ROOTFS_PARTSIZE=4096", result.stderr)

    def test_source_release_preserves_images_config_and_nested_revisions(self):
        self.assert_success(self.run_helper("collect-release.sh"))
        self.assertEqual(len(list(self.release.glob("*.img.gz"))), 2)
        self.assertEqual((self.release / "final.config").read_bytes(), (self.build / ".config").read_bytes())
        for filename in ("requested.config", "config.buildinfo", "feeds.buildinfo", "version.buildinfo", "profiles.json"):
            self.assertTrue((self.release / filename).is_file(), filename)
        revisions = (self.release / "source-revisions.tsv").read_text()
        for name in ("customization", "upstream", "feeds/packages", "feeds/packages/lang/golang", "package/custom/example"):
            self.assertIn(f"{name}\t{REVISION}\t", revisions)
        tag = (self.tree / "github.env").read_text().splitlines()[0]
        self.assertIn(f"Source-openwrt-25.12-{REVISION[:12]}-123456789.1", tag)

    def test_customer_release_includes_pinned_dependencies(self):
        self.env.update(RELEASE_ROUTE="Customer", RELEASE_VERSION="v25.12.5")
        (self.build / "customer-sources/golang/.git").mkdir(parents=True)
        self.assert_success(self.run_helper("collect-release.sh"))
        self.assertEqual((self.release / "customer-dependencies.tsv").read_bytes(),
                         (self.build / "customer-dependencies.tsv").read_bytes())
        self.assertIn("OpenWrt-R3S-Customer-v25.12.5-", (self.tree / "github.env").read_text())
        self.assertIn(f"customer-sources/golang\t{REVISION}\t",
                      (self.release / "source-revisions.tsv").read_text())

    def test_imagebuilder_uses_official_baseline_not_source_build_outputs(self):
        self.env.update(RELEASE_ROUTE="ImageBuilder", RELEASE_VERSION="25.12.2",
                        IB_URL="https://example.invalid/imagebuilder.tar.zst", PACKAGES="luci sing-box")
        for name in ("config.buildinfo", "feeds.buildinfo", "version.buildinfo"):
            self.write("imagebuilder-buildinfo/" + name, (self.output / name).read_text())
            (self.output / name).unlink()
        self.write("imagebuilder-buildinfo/sha256sums", "fixture official metadata checksum\n")
        self.write("imagebuilder.sha256", "fixture archive checksum\n")
        self.assert_success(self.run_helper("collect-release.sh"))
        self.assertTrue((self.release / "imagebuilder.config").is_file())
        self.assertFalse((self.release / "final.config").exists())
        self.assertTrue((self.release / "imagebuilder-buildinfo.sha256").is_file())
        info = (self.release / "build-info.txt").read_text()
        self.assertIn("official ImageBuilder baseline", info)
        self.assertIn("packages=luci sing-box", info)

    def test_customer_no_passwall_records_metadata_and_preserves_release_naming(self):
        self.env.update(RELEASE_ROUTE="Customer", RELEASE_VERSION="v25.12.5", BUILD_MODE="no-passwall")
        self.assert_success(self.run_helper("collect-release.sh"))
        self.assertIn("build_mode=no-passwall\n", (self.release / "build-info.txt").read_text())
        self.assertIn(f"Customer-v25.12.5-{REVISION[:12]}-123456789.1", (self.tree / "github.env").read_text())
        self.assertNotIn("no-passwall", (self.tree / "github.env").read_text())

    def prepare_compile(self):
        self.write(".config", "CONFIG_TARGET_rockchip=y\n")
        self.env.update(BUILD_JOBS="4", BUILD_LOG_DIR="build-logs")
        self.write("bin/make", '''#!/bin/bash
printf '%s\\n' "$*" >> make-calls.log
echo "stdout: $*"
echo "stderr: $*" >&2
if [ "$1" = -j4 ]; then exit "${PARALLEL_STATUS:-0}"; fi
exit "${SERIAL_STATUS:-0}"
''')

    def test_successful_compile_runs_once_and_captures_stdout_and_stderr(self):
        self.prepare_compile()
        self.assert_success(self.run_helper("compile.sh"))
        self.assertEqual((self.tree / "make-calls.log").read_text().splitlines(), ["-j4"])
        log = (self.tree / "build-logs/parallel.log").read_text()
        self.assertIn("stdout: -j4", log)
        self.assertIn("stderr: -j4", log)
        self.assertFalse((self.tree / "build-logs/retry-verbose.log").exists())

    def test_failed_parallel_compile_retries_once_with_verbose_output(self):
        self.prepare_compile()
        self.env.update(PARALLEL_STATUS="2")
        self.assert_success(self.run_helper("compile.sh"))
        self.assertEqual((self.tree / "make-calls.log").read_text().splitlines(), ["-j4", "-j1 V=s"])
        self.assertIn("stderr: -j1 V=s", (self.tree / "build-logs/retry-verbose.log").read_text())

    def test_failed_serial_retry_preserves_exit_status_despite_tee(self):
        self.prepare_compile()
        self.env.update(PARALLEL_STATUS="2", SERIAL_STATUS="42")
        result = self.run_helper("compile.sh")
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        self.assertEqual(len((self.tree / "make-calls.log").read_text().splitlines()), 2)
        self.assertIn("status=42", result.stdout)

    def test_invalid_jobs_or_missing_config_never_runs_make(self):
        self.prepare_compile()
        self.env.update(BUILD_JOBS="4;echo invalid")
        self.assertNotEqual(self.run_helper("compile.sh").returncode, 0)
        self.env.update(BUILD_JOBS="4")
        (self.tree / ".config").unlink()
        self.assertNotEqual(self.run_helper("compile.sh").returncode, 0)
        self.assertFalse((self.tree / "make-calls.log").exists())

    def test_rerun_attempt_receives_a_different_tag(self):
        self.assert_success(self.run_helper("collect-release.sh"))
        original = (self.tree / "github.env").read_text().splitlines()[0]
        shutil.rmtree(self.release)
        (self.tree / "github.env").unlink()
        self.env["GITHUB_RUN_ATTEMPT"] = "2"
        self.assert_success(self.run_helper("collect-release.sh"))
        rerun = (self.tree / "github.env").read_text().splitlines()[0]
        self.assertNotEqual(original, rerun)
        self.assertTrue(rerun.endswith("123456789.2"))

    def test_checksum_file_covers_every_asset_and_excludes_itself(self):
        self.assert_success(self.run_helper("collect-release.sh"))
        checked = set()
        for entry in (self.release / "sha256sums.txt").read_text().splitlines():
            digest, filename = entry[:64], entry[66:]
            self.assertIn(entry[64:66], ("  ", " *"))
            self.assertEqual(hashlib.sha256((self.release / filename).read_bytes()).hexdigest(), digest)
            checked.add(filename)
        self.assertEqual(checked, {path.name for path in self.release.iterdir()} - {"sha256sums.txt"})

    def test_empty_image_set_is_rejected(self):
        for path in self.output.glob("*.img.gz"):
            path.unlink()
        result = self.run_helper("collect-release.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No firmware found", result.stderr)
        self.assertFalse((self.tree / "github.env").exists())

    def test_missing_package_manifest_is_rejected(self):
        for path in self.output.glob("*.manifest"):
            path.unlink()
        result = self.run_helper("collect-release.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No package manifest", result.stderr)

    def test_missing_build_config_is_rejected(self):
        (self.output / "config.buildinfo").unlink()
        self.assertNotEqual(self.run_helper("collect-release.sh").returncode, 0)

    def test_existing_output_directory_is_never_overwritten(self):
        self.write("release_files/keep.txt", "preserve me\n")
        result = self.run_helper("collect-release.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.release / "keep.txt").read_text(), "preserve me\n")
        self.assertEqual(len(list(self.release.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
