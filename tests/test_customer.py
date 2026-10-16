"""Exercise Customer setup without downloading packages or building firmware."""
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


def shell_path(path):
    value = Path(path).resolve().as_posix()
    if os.name == "nt":
        return "/" + value[0].lower() + value[2:]
    return value


@unittest.skipUnless(BASH and Path(BASH).is_file(), "Bash is required")
class CustomerScriptsTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="customer-test-")
        self.addCleanup(self.scratch.cleanup)
        self.tree = Path(self.scratch.name)
        self.bin = self.tree / "test-bin"
        self.bin.mkdir()
        self.dependencies = []
        for line in (ROOT / "scripts/customer/00-dependencies.sh").read_text(encoding="utf-8").splitlines():
            if line.startswith(("feed|", "package|", "toolchain|")):
                self.dependencies.append(line.split("|"))

    def write(self, relative, content):
        path = self.tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        path.chmod(0o755)
        return path

    def run_script(self, script, **extra):
        env = os.environ.copy()
        for key in ("TARGET", "SUBTARGET", "PROFILE", "ROOTFS_PARTSIZE", "GITHUB_WORKSPACE", "BUILD_MODE"):
            env.pop(key, None)
        env.update(extra)
        return subprocess.run(
            [BASH, "--noprofile", "--norc", "-c",
             'export PATH="$1:/usr/bin:/bin:$PATH"; exec bash "$2"', "test-customer",
             shell_path(self.bin), shell_path(ROOT / "scripts/customer" / script)],
            cwd=self.tree, env=env, capture_output=True, text=True, encoding="utf-8",
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def symlink(self, path, target):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.symlink_to(target, target_is_directory=True)
        except OSError as error:
            if os.name == "nt" and getattr(error, "winerror", None) == 1314:
                self.skipTest("Windows requires permission to create directory symlinks")
            raise
        self.assertTrue(path.is_symlink())

    def prepare_packages(self, modern_go=True):
        for kind, name, url, revision, relative in self.dependencies:
            if kind == "feed":
                self.write(relative + "/.test-revision", revision + "\n")
        if modern_go:
            self.write("feeds/packages/lang/golang/golang-version.mk", "# upstream Go 1.26 structure\n")
            self.write("feeds/packages/lang/golang/golang-values.mk", "GO_DEFAULT_VERSION:=1.26\n")
            self.write("feeds/packages/lang/golang/golang/Makefile", "# upstream default compiler wrapper\n")
            self.write("feeds/packages/lang/golang/golang1.26/Makefile", "GO_VERSION_MAJOR_MINOR:=1.26\nGO_VERSION_PATCH:=4\n")
        else:
            self.write("feeds/packages/lang/golang/Makefile", "# legacy structure\n")
        official = "test-fixtures/official-packages/lang/golang/"
        for relative in (
            "golang-version.mk", "golang-package.mk", "golang-host-build.mk",
            "golang-compiler.mk", "golang-build.sh", "go-gcc-helper", "go-strip-helper",
            "golang-bootstrap/Makefile", "golang-bootstrap/Config.in", "golang/Makefile",
        ):
            self.write(official + relative, "# pinned official Go support: " + relative + "\n")
        self.write(official + "golang-values.mk", "GO_DEFAULT_VERSION:=1.27\n")
        self.write(official + "golang1.27/Makefile", "PKG_NAME:=golang1.27\nGO_VERSION_MAJOR_MINOR:=1.27\nGO_VERSION_PATCH:=2\n")
        self.write("test-fixtures/official-packages/net/unrelated/Makefile", "# package outside Go subtree\n")
        self.write("feeds/nikki/mihomo-alpha/Makefile", "PROVIDES:=mihomo\nCONFLICTS:=mihomo-meta\n")
        self.write("feeds/nikki/mihomo-meta/Makefile", "PROVIDES:=mihomo\nCONFLICTS:=mihomo-alpha\n")
        self.write("scripts/feeds", r'''#!/bin/bash
set -eu
printf '%s\n' "$*" >> feeds-commands.log
[ "${TEST_FEEDS_STATUS:-0}" -eq 0 ] || exit "$TEST_FEEDS_STATUS"
if [ "$*" = 'update -i packages luci nikki' ]; then
    : > feeds/nikki.index
    for makefile in feeds/nikki/*/Makefile; do
        [ -f "$makefile" ] || continue
        package=${makefile%/Makefile}
        printf '%s\n' "${package##*/}" >> feeds/nikki.index
    done
fi
''')
        self.write("package/base-files/files/etc/shadow", "root:*:0:0:99999:7:::\n")
        self.write("package/base-files/files/bin/config_generate", "192.168.1.1 OpenWrt 'UTC'\n")
        self.write("feeds/luci/collections/luci/Makefile", "+luci-theme-bootstrap\n")
        self.write("test-bin/git", r'''#!/bin/bash
set -eu
if [ "$1" = clone ]; then
    path=${@: -1}
    mkdir -p "$path"
    exit 0
fi
[ "$1" = -C ] || exit 90
path=$2
shift 2
if [ "$1" = -c ]; then shift 2; fi
case "$1" in
    fetch) printf '%s\n' "${@: -1}" > "$path/.test-revision" ;;
    checkout)
        test -f "$path/.test-revision"
        if [ "$path" = customer-sources/golang ]; then
            cp -R test-fixtures/official-packages/. "$path/"
        fi
        ;;
    rev-parse) cat "$path/.test-revision" ;;
    *) exit 91 ;;
esac
''')

    def test_feeds_are_pinned_and_idempotent(self):
        self.write("feeds.conf.default", "# mosdns reference\nsrc-git packages https://example.test/packages\nsrc-git nikki https://old.test;main\n")
        self.assert_success(self.run_script("01-diy-feeds.sh"))
        once = (self.tree / "feeds.conf.default").read_text(encoding="utf-8")
        self.assert_success(self.run_script("01-diy-feeds.sh"))
        self.assertEqual(once, (self.tree / "feeds.conf.default").read_text(encoding="utf-8"))
        self.assertIn("# mosdns reference", once)
        self.assertIn("src-git packages https://example.test/packages", once)
        for kind, name, url, revision, path in self.dependencies:
            if kind == "feed":
                self.assertEqual(once.count(f"src-git {name} {url}^{revision}\n"), 1)

    def test_active_feeds_conf_takes_precedence(self):
        self.write("feeds.conf", "src-git packages https://example.test/active\n")
        self.write("feeds.conf.default", "default unchanged\n")
        self.assert_success(self.run_script("01-diy-feeds.sh"))
        self.assertIn("^", (self.tree / "feeds.conf").read_text())
        self.assertEqual((self.tree / "feeds.conf.default").read_text(), "default unchanged\n")

    def test_missing_feeds_configuration_fails(self):
        self.assertNotEqual(self.run_script("01-diy-feeds.sh").returncode, 0)

    def assert_pinned_official_go(self):
        source = self.tree / "test-fixtures/official-packages/lang/golang"
        installed = self.tree / "feeds/packages/lang/golang"
        expected = {path.relative_to(source).as_posix(): path.read_bytes()
                    for path in source.rglob("*") if path.is_file()}
        actual = {path.relative_to(installed).as_posix(): path.read_bytes()
                  for path in installed.rglob("*") if path.is_file()}
        self.assertEqual(actual, expected)
        self.assertFalse((installed / "golang1.26").exists())

    def test_modern_go_126_is_upgraded_and_base_settings_are_preserved(self):
        self.prepare_packages()
        before = {relative: (self.tree / relative).read_bytes() for relative in (
            "package/base-files/files/etc/shadow",
            "package/base-files/files/bin/config_generate",
        )}
        self.assert_success(self.run_script("02-diy-packages.sh"))
        for relative, content in before.items():
            self.assertEqual((self.tree / relative).read_bytes(), content)
        self.assert_pinned_official_go()
        manifest = (self.tree / "customer-dependencies.tsv").read_text()
        self.assertEqual(len(manifest.splitlines()), 10)
        self.assertIn("luci-theme-argon", (self.tree / "feeds/luci/collections/luci/Makefile").read_text())
        for kind, name, url, revision, path in self.dependencies:
            self.assertIn(f"{name}\t{url}\t{revision}\n", manifest)
        golang = next(row for row in self.dependencies if row[1] == "golang")
        source_path = Path(golang[4])
        self.assertNotIn(source_path.parts[0], ("package", "feeds"))
        self.assertTrue((self.tree / source_path / "net/unrelated/Makefile").is_file())
        self.assertFalse((self.tree / "feeds/packages/net/unrelated").exists())
        self.assertFalse((self.tree / "package/custom/golang").exists())
        commands = (self.tree / "feeds-commands.log").read_text().splitlines()
        self.assertTrue(any(command.startswith("update -i ") and "packages" in command.split()
                            for command in commands))

    def test_legacy_go_is_upgraded_to_the_same_pinned_official_compiler(self):
        self.prepare_packages(modern_go=False)
        self.assert_success(self.run_script("02-diy-packages.sh"))
        self.assert_pinned_official_go()
        manifest = (self.tree / "customer-dependencies.tsv").read_text()
        self.assertEqual(len(manifest.splitlines()), 10)
        golang = next(row for row in self.dependencies if row[1] == "golang")
        self.assertIn("\t".join(golang[1:4]) + "\n", manifest)

    def test_pinned_official_go_setup_is_repeatable(self):
        self.prepare_packages()
        for _ in range(2):
            self.assert_success(self.run_script("02-diy-packages.sh"))
            self.assert_pinned_official_go()
            manifest = (self.tree / "customer-dependencies.tsv").read_text().splitlines()
            self.assertEqual(len(manifest), 10)
            self.assertEqual(sum(line.startswith("golang\t") for line in manifest), 1)

    def test_missing_or_incompatible_official_go_preserves_installed_compiler(self):
        cases = (
            (None, None),
            ("golang-bootstrap/Makefile", None),
            ("golang-values.mk", "GO_DEFAULT_VERSION:=1.26\n"),
            ("golang1.27/Makefile", "PKG_NAME:=golang1.27\nGO_VERSION_MAJOR_MINOR:=1.27\nGO_VERSION_PATCH:=1\n"),
        )
        for relative, replacement in cases:
            with self.subTest(source=relative, content=replacement):
                self.prepare_packages()
                installed = self.tree / "feeds/packages/lang/golang"
                before = {path.relative_to(installed): path.read_bytes()
                          for path in installed.rglob("*") if path.is_file()}
                source = self.tree / "test-fixtures/official-packages/lang/golang"
                if relative is None:
                    shutil.rmtree(source)
                elif replacement is None:
                    source = source / relative
                    source.unlink()
                else:
                    source = source / relative
                    source.write_text(replacement, encoding="utf-8")
                result = self.run_script("02-diy-packages.sh")
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                after = {path.relative_to(installed): path.read_bytes()
                         for path in installed.rglob("*") if path.is_file()}
                self.assertEqual(after, before)
                self.assertFalse((self.tree / "package/custom").exists())

    def test_incompatible_official_go_preserves_old_install_link(self):
        self.prepare_packages()
        link = self.tree / "package/feeds/packages/golang1.26"
        self.symlink(link, "../../../feeds/packages/lang/golang/golang1.26")
        source_version = self.tree / "test-fixtures/official-packages/lang/golang/golang-values.mk"
        source_version.write_text("GO_DEFAULT_VERSION:=1.26\n", encoding="utf-8")
        result = self.run_script("02-diy-packages.sh")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertTrue((link / "Makefile").is_file())

    def test_old_official_go_install_links_are_removed(self):
        self.prepare_packages()
        links = []
        for name in ("golang", "golang1.26"):
            link = self.tree / "package/feeds/packages" / name
            self.symlink(link, "../../../feeds/packages/lang/golang/" + name)
            links.append(link)
        self.assert_success(self.run_script("02-diy-packages.sh"))
        self.assert_pinned_official_go()
        for link in links:
            self.assertFalse(os.path.lexists(link))
        self.assertTrue((self.tree / "customer-sources/golang/lang/golang/golang1.27/Makefile").is_file())

    def test_non_symlink_go_install_is_preserved_and_rejected(self):
        self.prepare_packages()
        local = self.write("package/feeds/packages/golang1.26/Makefile", "# local package\n")
        result = self.run_script("02-diy-packages.sh")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(local.read_text(), "# local package\n")
        self.assertTrue((self.tree / "feeds/packages/lang/golang/golang1.26/Makefile").is_file())

    def test_go_install_link_outside_the_old_go_subtree_is_preserved_and_rejected(self):
        self.prepare_packages()
        other = self.write("feeds/packages/lang/unrelated/Makefile", "# unrelated compiler\n")
        link = self.tree / "package/feeds/packages/golang-other"
        self.symlink(link, "../../../feeds/packages/lang/unrelated")
        result = self.run_script("02-diy-packages.sh")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertEqual(other.read_text(), "# unrelated compiler\n")
        self.assertTrue((self.tree / "feeds/packages/lang/golang/golang1.26/Makefile").is_file())

    def test_packages_keep_only_mihomo_meta_and_refresh_nikki_index(self):
        self.prepare_packages()
        meta = self.tree / "feeds/nikki/mihomo-meta/Makefile"
        before = meta.read_bytes()
        for _ in range(2):
            self.assert_success(self.run_script("02-diy-packages.sh"))
            self.assertFalse((self.tree / "feeds/nikki/mihomo-alpha").exists())
            self.assertEqual(meta.read_bytes(), before)
            self.assertEqual((self.tree / "feeds/nikki.index").read_text(), "mihomo-meta\n")
        commands = (self.tree / "feeds-commands.log").read_text().splitlines()
        self.assertEqual(commands.count("update -i packages luci nikki"), 2)

    def test_packages_remove_existing_mihomo_alpha_feed_symlink(self):
        self.prepare_packages()
        installed = self.tree / "package/feeds/nikki/mihomo-alpha"
        self.symlink(installed, "../../../feeds/nikki/mihomo-alpha")
        self.assert_success(self.run_script("02-diy-packages.sh"))
        self.assertFalse(os.path.lexists(installed))
        self.assertTrue((self.tree / "feeds/nikki/mihomo-meta/Makefile").is_file())

    def test_missing_mihomo_meta_fails_before_package_changes(self):
        self.prepare_packages()
        (self.tree / "feeds/nikki/mihomo-meta/Makefile").unlink()
        result = self.run_script("02-diy-packages.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mihomo-meta/Makefile", result.stderr)
        self.assertTrue((self.tree / "feeds/nikki/mihomo-alpha/Makefile").is_file())
        self.assertFalse((self.tree / "feeds-commands.log").exists())
        self.assertFalse((self.tree / "package/custom").exists())

    def test_packages_reject_non_symlink_mihomo_alpha_install(self):
        self.prepare_packages()
        installed = self.write("package/feeds/nikki/mihomo-alpha/Makefile", "# preserve local package\n")
        result = self.run_script("02-diy-packages.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a feed symlink", result.stderr)
        self.assertEqual(installed.read_text(), "# preserve local package\n")

    def test_unexpected_feed_commit_fails_before_package_changes(self):
        self.prepare_packages()
        self.write("feeds/nikki/.test-revision", "0" * 40 + "\n")
        result = self.run_script("02-diy-packages.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected", result.stderr)
        self.assertFalse((self.tree / "package/custom").exists())

    def test_failed_feed_index_update_stops_setup(self):
        self.prepare_packages()
        result = self.run_script("02-diy-packages.sh", TEST_FEEDS_STATUS="42")
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        self.assertFalse((self.tree / "package/custom").exists())

    def test_generated_config_uses_wireguard_protocol_and_requested_partition_size(self):
        self.write("test-bin/make", "#!/bin/bash\nprintf '%s\\n' \"$@\" > make-args.log\n")
        self.assert_success(self.run_script("03-generate-config.sh", ROOTFS_PARTSIZE="2048"))
        self.assertEqual((self.tree / "make-args.log").read_text().splitlines(),
                         ["defconfig", "RECURSIVE_DEP_IS_ERROR=1"])
        config = (self.tree / ".config").read_text(encoding="utf-8")
        self.assertIn("CONFIG_PACKAGE_luci-proto-wireguard=y", config)
        self.assertIn("CONFIG_PACKAGE_fwtool=y", config)
        self.assertIn("CONFIG_PACKAGE_jsonfilter=y", config)
        self.assertIn("CONFIG_PACKAGE_mihomo-meta=y", config)
        self.assertIn("CONFIG_CCACHE=y", config)
        self.assertNotIn("CONFIG_PACKAGE_shadowsocks-rust-sslocal=n", config)
        self.assertNotIn("CONFIG_PACKAGE_kmod-bpf=", config)
        self.assertNotIn("luci-app-wireguard", config)
        self.assertNotIn("luci-i18n-wireguard", config)
        self.assertIn("CONFIG_TARGET_ROOTFS_PARTSIZE=2048", config)
        self.assertIn("CONFIG_TARGET_rockchip_armv8_DEVICE_friendlyarm_nanopi-r3s=y", config)

    def test_dropped_required_package_fails_config_generation(self):
        self.write("test-bin/make", "#!/bin/bash\nsed -i '/^CONFIG_PACKAGE_luci-proto-wireguard=y$/d' .config\n")
        result = self.run_script("03-generate-config.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("luci-proto-wireguard", result.stdout + result.stderr)

    def test_lite_disables_rust_shadowsocks_and_retains_proxy_apps(self):
        self.write("test-bin/make", "#!/bin/bash\nexit 0\n")
        self.assert_success(self.run_script("03-generate-config.sh", BUILD_MODE="lite"))
        config = (self.tree / ".config").read_text(encoding="utf-8")
        for suffix in ("Client", "Server"):
            self.assertIn(f"CONFIG_PACKAGE_luci-app-passwall_INCLUDE_Shadowsocks_Rust_{suffix}=n\n", config)
        for variant in ("sslocal", "ssserver", "ssmanager", "ssservice", "ssurl"):
            self.assertIn(f"CONFIG_PACKAGE_shadowsocks-rust-{variant}=n\n", config)
        for package in ("luci-app-homeproxy", "luci-app-nikki", "luci-app-passwall", "luci-app-mosdns", "mihomo-meta", "sing-box"):
            self.assertIn(f"CONFIG_PACKAGE_{package}=y\n", config)
        self.assertEqual(config, (self.tree / ".config.requested").read_text(encoding="utf-8"))

    def test_lite_rejects_rust_shadowsocks_reselected_by_dependencies(self):
        for selected in ("shadowsocks-rust-sslocal=y", "shadowsocks-rust-ssserver=m",
                         "luci-app-passwall_INCLUDE_Shadowsocks_Rust_Client=y"):
            with self.subTest(selected=selected):
                self.write("test-bin/make", f"#!/bin/bash\nprintf '%s\\n' 'CONFIG_PACKAGE_{selected}' >> .config\n")
                result = self.run_script("03-generate-config.sh", BUILD_MODE="lite")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Rust Shadowsocks", result.stderr)

    def test_unknown_build_mode_is_rejected_before_writing_config(self):
        self.assertNotEqual(self.run_script("03-generate-config.sh", BUILD_MODE="typo").returncode, 0)
        self.assertFalse((self.tree / ".config").exists())

    def test_invalid_target_input_is_rejected(self):
        self.write("test-bin/make", "#!/bin/bash\nexit 0\n")
        self.assertNotEqual(self.run_script("03-generate-config.sh", PROFILE="r3s\nCONFIG_BAD=y").returncode, 0)
        self.assertFalse((self.tree / ".config").exists())


if __name__ == "__main__":
    unittest.main()
