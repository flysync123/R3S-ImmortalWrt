"""Exercise the installer only against ordinary files in an isolated directory.

The test copy redirects every hardware path to fixtures and changes its block
device predicate to a regular-file predicate. No test opens a real disk.
"""
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = shutil.which("dash") or shutil.which("sh")
if os.name == "nt":
    SHELL = r"C:\Program Files\Git\usr\bin\dash.exe"


def shell_path(path):
    value = Path(path).resolve().as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


@unittest.skipUnless(SHELL and Path(SHELL).is_file(), "A POSIX shell is required")
class EmmcInstallTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix=".test-emmc-", dir=ROOT)
        self.addCleanup(self.scratch.cleanup)
        self.tree = Path(self.scratch.name)
        self.bin = self.tree / "bin"
        self.bin.mkdir()
        (self.tree / "var/lock").mkdir(parents=True)
        self.device = self.tree / "dev/mmcblk1"
        self.image = self.tree / "firmware.img.gz"
        self.env = os.environ.copy()
        self.env["FIXTURE"] = shell_path(self.tree)
        self.write("dev/null", "")
        self.device.touch()
        self.write("proc/self/mountinfo", "1 0 179:2 / /rom ro - squashfs /dev/root ro\n2 1 0:1 / / rw - overlay overlayfs:/overlay rw\n")
        self.write("proc/swaps", "Filename Type Size Used Priority\n")
        self.write("sys/class/block/mmcblk1/device/type", "MMC\n")
        self.write("sys/class/block/mmcblk1/ro", "0\n")
        self.write("sys/class/block/mmcblk1/dev", "179:8\n")
        self.write("sys/class/block/mmcblk1/size", "65536\n")
        self.write("sys/class/block/mmcblk1p2/dev", "179:10\n")
        self.write("tmp/sysinfo/board_name", "friendlyarm,nanopi-r3s\n")
        self.write("bin/id", "#!/bin/sh\nprintf '0\\n'\n")
        self.write("bin/fwtool", r'''#!/bin/sh
if [ "${TEST_METADATA_FAIL:-0}" = 1 ]; then exit 1; fi
if [ "$2" = -T ]; then
    cat "$5"
    exit "${TEST_PRODUCER_STATUS:-0}"
fi
printf '{"supported_devices":["friendlyarm,nanopi-r3s"]}\n' > "$3"
''')
        self.write("bin/jsonfilter", "#!/bin/sh\nprintf '%s\\n' \"${TEST_SUPPORTED:-friendlyarm,nanopi-r3s}\"\n")
        self.write("bin/dd", r'''#!/bin/sh
for arg in "$@"; do
    if [ "$arg" = "of=$FIXTURE/dev/mmcblk1" ]; then
        printf 'write\n' >> "$FIXTURE/write.log"
        [ "${TEST_DD_FAIL:-0}" = 0 ] || exit 1
        if [ "${TEST_DD_SLOW:-0}" = 1 ]; then
            trap 'printf stopped > "$FIXTURE/stopped.log"; exit 143' TERM INT HUP
            printf '%s' "$$" > "$FIXTURE/writer.pid"
            while :; do :; done
        fi
    fi
    case "$arg" in count=*) reading=1 ;; of=*) output=1 ;; esac
done
if [ "${reading:-0}" = 1 ] && [ "${output:-0}" = 0 ] && [ "${TEST_READBACK_CORRUPT:-0}" = 1 ]; then
    printf 'wrong readback\n'
    exit 0
fi
exec /usr/bin/dd "$@"
''')
        original = (ROOT / "files/usr/bin/emmc-install").read_text(encoding="utf-8")
        self.assertEqual(original.count('[ -b "$1" ]'), 1)
        script = original.replace('[ -b "$1" ]', '[ -f "$1" ]')
        for prefix in ("/sys/class/block", "/proc/self/mountinfo", "/proc/swaps", "/tmp/sysinfo", "/var/lock"):
            script = script.replace(prefix, shell_path(self.tree / prefix.lstrip("/")))
        script = script.replace("/dev/", shell_path(self.tree / "dev") + "/")
        script = script.replace("/tmp/emmc-", shell_path(self.tree / "tmp/emmc-"))
        self.assertNotRegex(script, r'(?<![A-Za-z0-9_/])/(?:dev/mmc|sys/class/block)')
        self.script = self.write("installer.sh", script)
        raw = bytearray(512)
        raw[510:512] = b"\x55\xaa"
        for offset, start, count in ((446, 32768, 32), (462, 32800, 32)):
            raw[offset + 4] = 0x83
            struct.pack_into("<II", raw, offset + 8, start, count)
        self.raw = bytes(raw) + b"\0" * (32832 * 512 - 512)
        self.set_image(self.raw)

    def write(self, name, content):
        path = self.tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        path.chmod(0o755)
        return path

    def set_image(self, raw, compressed=None):
        self.image.write_bytes(gzip.compress(raw, mtime=0) if compressed is None else compressed)
        self.digest = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.write("sha256sums.txt", f"{self.digest}  {self.image.name}\n")

    def run_installer(self, yes=True, explicit_digest=None, trace=False, **env):
        variables = dict(self.env, **env)
        args = [shell_path(self.script)]
        if yes:
            args.append("--yes")
        args.append(shell_path(self.image))
        if explicit_digest is not None:
            args.append(explicit_digest)
        return subprocess.run(
            [SHELL, "-c", 'export PATH="$1:/usr/bin:/bin:$PATH"; shift; exec /usr/bin/dash ' + ('-x ' if trace else '') + '"$@"',
             "test-installer", shell_path(self.bin), *args],
            env=variables, input="", capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def assert_rejected_before_write(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.tree / "write.log").exists(), result.stdout + result.stderr)

    def test_valid_image_is_written_and_verified(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.device.read_bytes(), self.raw)
        self.assertIn("写入及回读校验成功", result.stdout)
        self.assertFalse((self.tree / "var/lock/emmc-install.lock").exists())

    def test_explicit_digest_does_not_require_sidecar(self):
        (self.tree / "sha256sums.txt").unlink()
        result = self.run_installer(explicit_digest=self.digest.upper())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_checksum(self):
        (self.tree / "sha256sums.txt").unlink()
        self.assert_rejected_before_write(self.run_installer())

    def test_checksum_mismatch(self):
        self.assert_rejected_before_write(self.run_installer(explicit_digest="0" * 64))

    def test_duplicate_checksum_entry(self):
        self.write("sha256sums.txt", f"{self.digest}  firmware.img.gz\n" * 2)
        self.assert_rejected_before_write(self.run_installer())

    def test_checksum_for_other_file_is_not_accepted(self):
        self.write("sha256sums.txt", f"{self.digest}  other-firmware.img.gz\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_no_mmc_does_not_fall_back_to_numbered_device(self):
        self.write("sys/class/block/mmcblk1/device/type", "SD\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_multiple_mmc_devices(self):
        self.write("sys/class/block/mmcblk0/device/type", "MMC\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_dev_root_alias_on_target_partition(self):
        self.write("proc/self/mountinfo", "1 0 179:10 / / ro - ext4 /dev/root ro\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_overlay_root_with_target_rom(self):
        self.write("proc/self/mountinfo", "1 0 179:10 / /rom ro - squashfs /dev/root ro\n2 1 0:1 / / rw - overlay overlayfs:/overlay rw\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_mounted_overlay_partition(self):
        self.write("proc/self/mountinfo", "1 0 179:10 / /overlay rw - ext4 /dev/loop0 rw\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_active_swap(self):
        self.write("dev/mmcblk1p2", "")
        self.write("proc/swaps", "Filename Type Size Used Priority\n" + shell_path(self.tree / "dev/mmcblk1p2") + " partition 100 0 -2\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_device_mapper_holder(self):
        self.write("sys/class/block/mmcblk1p2/holders/dm-0", "")
        self.assert_rejected_before_write(self.run_installer())

    def test_loop_backed_by_target_partition(self):
        self.write("dev/mmcblk1p2", "")
        self.write("sys/class/block/loop0/loop/backing_file", shell_path(self.tree / "dev/mmcblk1p2") + "\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_unknown_loop_block_alias_is_rejected(self):
        self.write("dev/root", "")
        self.write("sys/class/block/loop0/loop/backing_file", shell_path(self.tree / "dev/root") + "\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_readonly_target(self):
        self.write("sys/class/block/mmcblk1/ro", "1\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_wrong_running_board(self):
        self.write("tmp/sysinfo/board_name", "friendlyarm,nanopi-r4s\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_wrong_image_board(self):
        self.assert_rejected_before_write(self.run_installer(TEST_SUPPORTED="friendlyarm,nanopi-r4s"))

    def test_metadata_required(self):
        self.assert_rejected_before_write(self.run_installer(TEST_METADATA_FAIL="1"))

    def test_corrupt_gzip_is_rejected_even_with_matching_checksum(self):
        self.set_image(self.raw, gzip.compress(self.raw)[:-8])
        self.assert_rejected_before_write(self.run_installer())

    def test_producer_error_is_not_hidden_by_successful_decoder(self):
        self.assert_rejected_before_write(self.run_installer(TEST_PRODUCER_STATUS="1"))

    def test_bad_partition_signature(self):
        raw = bytearray(self.raw)
        raw[510] = 0
        self.set_image(raw)
        self.assert_rejected_before_write(self.run_installer())

    def test_partition_extending_past_image(self):
        raw = bytearray(self.raw)
        struct.pack_into("<I", raw, 462 + 12, 100000)
        self.set_image(raw)
        self.assert_rejected_before_write(self.run_installer())

    def test_too_small_emmc(self):
        self.write("sys/class/block/mmcblk1/size", "1024\n")
        self.assert_rejected_before_write(self.run_installer())

    def test_missing_confirmation(self):
        self.assert_rejected_before_write(self.run_installer(yes=False))

    def test_failed_write_never_reports_success(self):
        result = self.run_installer(TEST_DD_FAIL="1")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("写入及回读校验成功", result.stdout)

    def test_readback_mismatch_never_reports_success(self):
        result = self.run_installer(TEST_READBACK_CORRUPT="1")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("回读校验失败", result.stderr)
        self.assertNotIn("写入及回读校验成功", result.stdout)

    def test_existing_lock_is_not_removed(self):
        (self.tree / "var/lock/emmc-install.lock").mkdir()
        self.assert_rejected_before_write(self.run_installer())
        self.assertTrue((self.tree / "var/lock/emmc-install.lock").is_dir())

    def test_terminating_parent_stops_writer_before_releasing_lock(self):
        variables = dict(self.env, TEST_DD_SLOW="1")
        process = subprocess.Popen(
            [SHELL, "-c", 'printf "%s" "$$" > "$FIXTURE/parent.pid"; export PATH="$1:/usr/bin:/bin:$PATH"; shift; exec /usr/bin/dash "$@"',
             "test-installer", shell_path(self.bin), shell_path(self.script), "--yes", shell_path(self.image)],
            env=variables, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=(os.name != "nt"),
        )
        try:
            deadline = time.monotonic() + 10
            while not (self.tree / "writer.pid").exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    self.fail("Installer stopped before the simulated slow write")
                time.sleep(0.02)
            self.assertTrue((self.tree / "writer.pid").exists())
            self.assertTrue((self.tree / "var/lock/emmc-install.lock").exists())
            # MSYS has POSIX process IDs/signals of its own. Its shell kill also
            # exercises the production signal handler on Windows.
            parent_pid = (self.tree / "parent.pid").read_text()
            subprocess.run([SHELL, "-c", 'kill -TERM "$1"', "signal-installer", parent_pid], check=True)
            process.communicate(timeout=10)
            self.assertNotEqual(process.returncode, 0)
            self.assertTrue((self.tree / "stopped.log").exists())
            self.assertFalse((self.tree / "var/lock/emmc-install.lock").exists())
        finally:
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                for name in ("writer.pid", "parent.pid"):
                    if (self.tree / name).exists():
                        subprocess.run([SHELL, "-c", 'kill -TERM "$1"', "cleanup-installer",
                                        (self.tree / name).read_text()], check=False, capture_output=True)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
