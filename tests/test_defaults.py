"""Exercise first-boot/upgrade paths with fake UCI and a temporary filesystem.

Run: python -m unittest discover -s tests -p test_defaults.py -v
No commands in this test access a router or the host's /etc configuration.
"""

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
DEFAULTS = REPO / "files/etc/uci-defaults/99-r3s-optimize"
PREINIT = REPO / "files/lib/preinit/81-r3s-upgrade-state"
BASH = os.environ.get("TEST_BASH") or (
    "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")
)

FAKE_UCI = r'''
import json, os, sys
from pathlib import Path

path = Path(os.environ['MOCK_UCI_STATE'])
data = json.loads(path.read_text())
args = sys.argv[1:]
if args and args[0] == '-q':
    args.pop(0)
data['calls'].append(args)
command, key = args[0], args[1]
if ' '.join(args) == os.environ.get('MOCK_UCI_FAIL'):
    path.write_text(json.dumps(data))
    sys.exit(1)
pkg = key.split('.')[0].split('=')[0]
values = data['staged'].get(pkg, data['committed'].get(pkg, {}))
code = 0
if command == 'get':
    name = key[len(pkg) + 1:]
    if name not in values:
        code = 1
    else:
        value = values[name]
        print(' '.join(value) if isinstance(value, list) else value)
elif command in ('set', 'add_list', 'delete'):
    values = data['staged'].setdefault(pkg, dict(values))
    name, _, value = key[len(pkg) + 1:].partition('=')
    parent = name.rsplit('.', 1)[0]
    if '.' in name and parent not in values:
        code = 1
    elif command == 'set':
        values[name] = value
    elif command == 'delete':
        if name in values:
            del values[name]
        else:
            code = 1
    else:
        old = values.get(name, [])
        if not isinstance(old, list):
            old = [old]
        # UCI list operations preserve existing entries, avoiding duplicates.
        values[name] = old if value in old else old + [value]
elif command == 'commit':
    if pkg in data['staged']:
        data['committed'][pkg] = data['staged'].pop(pkg)
    target = Path(os.environ['MOCK_ROOT']) / 'etc/config' / pkg
    target.write_text('config mock\n')
elif command == 'revert':
    data['staged'].pop(pkg, None)
elif command == 'export':
    print('package ' + pkg)
    for name, value in values.items():
        if '.' not in name:
            print('\nconfig ' + value)
            for option, val in values.items():
                if option.startswith(name + '.'):
                    field = option[len(name) + 1:]
                    for item in val if isinstance(val, list) else [val]:
                        print('\t' + ('list' if isinstance(val, list) else 'option')
                              + ' ' + field + " '" + item + "'")
else:
    raise RuntimeError(args)
path.write_text(json.dumps(data))
sys.exit(code)
'''


def base_config():
    return {
        "network": {
            "lan": "interface", "lan.ipaddr": ["192.168.1.1/24"],
            "lan.netmask": "255.255.255.0", "lan.ip6assign": "60",
            "globals": "globals", "globals.packet_steering": "0",
        },
        "dhcp": {
            "lan": "dhcp", "lan.start": "100", "lan.limit": "150",
            "lan.leasetime": "12h", "@dnsmasq[0]": "dnsmasq",
            "@dnsmasq[0].cachesize": "1000",
        },
        "system": {
            "@system[0]": "system", "@system[0].hostname": "OpenWrt",
            "@system[0].timezone": "GMT0", "@system[0].zonename": "UTC",
            "ntp": "timeserver", "ntp.server": ["0.openwrt.pool.ntp.org"],
        },
        "firewall": {"@defaults[0]": "defaults", "@defaults[0].flow_offloading": "0"},
        "nlbwmon": {
            "@nlbwmon[0]": "nlbwmon",
            "@nlbwmon[0].local_network": ["192.168.0.0/16", "lan", "fc00::/7"],
            "@nlbwmon[0].database_directory": "/var/lib/nlbwmon",
        },
        "cpufreq": {"@settings[0]": "settings", "@settings[0].governor0": "schedutil"},
    }


def rooted_script(script, root):
    # Replace original router paths once. A Linux fixture root itself starts
    # with /tmp/, so sequential replacements would also rewrite inserted text.
    return re.sub(r"/etc/|/tmp/|/sysupgrade\.tgz\b",
                  lambda match: root.rstrip("/") + match.group(0), script)


class DefaultsTest(unittest.TestCase):
    def test_linux_tmp_fixture_prefix_is_not_rewritten_twice(self):
        source = "cat /etc/config/r3s /tmp/r3s-boot-state /sysupgrade.tgz"
        self.assertEqual(
            rooted_script(source, "/tmp/r3s-fixture"),
            "cat /tmp/r3s-fixture/etc/config/r3s "
            "/tmp/r3s-fixture/tmp/r3s-boot-state /tmp/r3s-fixture/sysupgrade.tgz",
        )

    def test_initialization_marker_is_explicitly_preserved(self):
        keep = (REPO / 'files/lib/upgrade/keep.d/r3s-defaults').read_text().splitlines()
        self.assertIn('/etc/config/r3s', keep)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="r3s-defaults-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for directory in ("etc/config", "etc/uci-defaults", "tmp", "bin"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        self.state = self.root / "state.json"
        self.write_config(base_config())
        (self.root / "fake_uci.py").write_text(FAKE_UCI)
        wrapper = "#!/bin/sh\nexec " + shlex.quote(Path(sys.executable).as_posix())
        wrapper += " " + shlex.quote((self.root / "fake_uci.py").as_posix()) + ' "$@"\n'
        (self.root / "bin/uci").write_text(wrapper)
        (self.root / "bin/uci").chmod(0o755)
        (self.root / "bin/logger").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$MOCK_ROOT/log"\n')
        (self.root / "bin/logger").chmod(0o755)
        # Native Python creates the test directory on Windows; this also lets
        # the mock reject any attempt to create directories outside this root.
        (self.root / "fake_mkdir.py").write_text(
            "import os, pathlib, sys\n"
            "root = pathlib.Path(os.environ['MOCK_ROOT']).resolve()\n"
            "for name in sys.argv[1:]:\n"
            "    if name == '-p': continue\n"
            "    target = pathlib.Path(name).resolve()\n"
            "    assert target.is_relative_to(root), target\n"
            "    target.mkdir(parents=True, exist_ok=True)\n"
        )
        mkdir = "#!/bin/sh\nexec " + shlex.quote(Path(sys.executable).as_posix())
        mkdir += " " + shlex.quote((self.root / "fake_mkdir.py").as_posix()) + ' "$@"\n'
        (self.root / "bin/mkdir").write_text(mkdir)
        (self.root / "bin/mkdir").chmod(0o755)
        self.env = os.environ.copy()
        self.env.update({
            "MOCK_UCI_STATE": str(self.state), "MOCK_ROOT": self.root.as_posix(),
            "PATH": str(self.root / "bin") + os.pathsep + self.env["PATH"],
            "MSYS_NO_PATHCONV": "1",
        })

    def write_config(self, config):
        self.state.write_text(json.dumps({"committed": config, "staged": {}, "calls": []}))

    def data(self):
        return json.loads(self.state.read_text())

    def root_script(self, path):
        script = rooted_script(path.read_text(encoding="utf-8"), self.root.as_posix())
        target = self.root / path.name
        target.write_text(script, encoding="utf-8", newline="\n")
        return target

    def shell(self, text, fail=None):
        env = self.env.copy()
        if fail:
            env["MOCK_UCI_FAIL"] = fail
        # Git Bash may prepend its own utilities when it starts. Put the mocks
        # first inside the shell, after that startup processing has completed.
        prefix = ('export PATH="$(/usr/bin/cygpath -u "$MOCK_ROOT")/bin:/usr/bin:$PATH"; '
                  if os.name == "nt" else 'export PATH="$MOCK_ROOT/bin:$PATH"; ')
        result = subprocess.run([BASH, "--noprofile", "--norc", "-c", prefix + text],
                                env=env, text=True, capture_output=True)
        return result

    def preinit(self):
        target = self.root_script(PREINIT)
        result = self.shell("boot_hook_add() { :; }; . " + shlex.quote(target.as_posix())
                            + "; r3s_capture_boot_state")
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.root / "tmp/r3s-boot-state").read_text().strip()

    def run_defaults(self, fail=None):
        target = self.root_script(DEFAULTS)
        return self.shell(". " + shlex.quote(target.as_posix()), fail=fail)

    def fresh(self):
        self.assertEqual(self.preinit(), "fresh")
        result = self.run_defaults()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fresh_defaults_and_ipv6(self):
        self.fresh()
        config = self.data()["committed"]
        self.assertEqual(config["network"]["lan.ipaddr"], ["10.0.0.1/24"])
        self.assertEqual(config["network"]["lan.ip6assign"], "60")
        self.assertEqual(config["nlbwmon"]["@nlbwmon[0].local_network"], ["lan", "fc00::/7"])
        self.assertEqual(config["cpufreq"]["@settings[0].governor0"], "schedutil")
        self.assertEqual(config["r3s"]["state.defaults_version"], "1")
        self.assertNotIn("passwd", DEFAULTS.read_text())

    def test_fresh_lan_without_address_is_initialized(self):
        config = base_config()
        del config['network']['lan.ipaddr']
        config['network']['lan.proto'] = 'none'
        self.write_config(config)
        self.fresh()
        network = self.data()['committed']['network']
        self.assertEqual(network['lan.ipaddr'], ['10.0.0.1/24'])
        self.assertEqual(network['lan.proto'], 'static')

    def test_repeated_defaults_preserve_user_changes(self):
        self.fresh()
        config = self.data()["committed"]
        config["network"]["lan.ipaddr"] = ["172.20.0.1/24"]
        config["system"]["ntp.server"] = ["time.example.org"]
        config["dhcp"]["lan.limit"] = "42"
        self.write_config(config)
        self.assertEqual(self.preinit(), "existing")
        self.assertEqual(self.run_defaults().returncode, 0)
        self.assertEqual(self.data()["committed"], config)

    def test_legacy_backup_without_marker_keeps_user_settings(self):
        config = base_config()
        config["network"]["lan.ipaddr"] = ["192.168.1.1/24"]
        config["dhcp"]["lan.leasetime"] = "2h"
        config["system"]["@system[0].hostname"] = "My Router"
        config["nlbwmon"]["@nlbwmon[0].local_network"] = "10.0.0.0/24 fc00::/7 172.20.0.0/16"
        config["nlbwmon"]["@nlbwmon[0].database_directory"] = "/mnt/stats"
        config["cpufreq"]["@settings[0].governor"] = "performance"
        self.write_config(config)
        (self.root / "sysupgrade.tgz").touch()
        self.assertEqual(self.preinit(), "restored")
        (self.root / "sysupgrade.tgz").unlink()  # Another defaults script cleaned up.
        self.assertEqual(self.run_defaults().returncode, 0)
        after = self.data()["committed"]
        for package in ("network", "dhcp", "system", "firewall"):
            self.assertEqual(after[package], config[package])
        self.assertEqual(after["nlbwmon"]["@nlbwmon[0].local_network"],
                         ["lan", "fc00::/7", "172.20.0.0/16"])
        self.assertEqual(after["nlbwmon"]["@nlbwmon[0].database_directory"], "/mnt/stats")
        self.assertNotIn("@settings[0].governor", after["cpufreq"])
        self.assertEqual(after["cpufreq"]["@settings[0].governor0"], "schedutil")

    def test_missing_boot_state_keeps_settings(self):
        original = base_config()
        self.assertEqual(self.run_defaults().returncode, 0)
        for package, values in original.items():
            self.assertEqual(self.data()["committed"][package], values)

    def test_existing_config_without_markers_is_not_fresh(self):
        (self.root / "etc/config/network").write_text("config interface lan\n")
        self.assertEqual(self.preinit(), "existing")
        self.assertEqual(self.run_defaults().returncode, 0)
        self.assertEqual(self.data()["committed"]["network"], base_config()["network"])

    def test_restore_markers_are_recorded(self):
        for marker in ("tmp/sysupgrade.tar", "etc/.updated", "etc/uci-defaults/10_disable_services"):
            with self.subTest(marker=marker):
                target = self.root / marker
                target.touch()
                self.assertEqual(self.preinit(), "restored")
                target.unlink()

    def test_missing_optional_packages_are_skipped(self):
        config = base_config()
        for package in ("nlbwmon", "cpufreq", "firewall"):
            del config[package]
        self.write_config(config)
        self.fresh()
        self.assertNotIn("nlbwmon", self.data()["committed"])

    def test_valid_custom_nlbwmon_list_is_unchanged(self):
        config = base_config()
        config["nlbwmon"]["@nlbwmon[0].local_network"] = ["10.0.0.0/24", "guest", "fd42::/48"]
        config["nlbwmon"]["@nlbwmon[1]"] = "nlbwmon"
        config["nlbwmon"]["@nlbwmon[1].local_network"] = "192.0.2.0/24"
        self.write_config(config)
        self.assertEqual(self.run_defaults().returncode, 0)
        self.assertEqual(self.data()["committed"]["nlbwmon"], config["nlbwmon"])

    def test_critical_failure_rolls_back_and_preserves_user_changes_after_restart(self):
        self.assertEqual(self.preinit(), "fresh")
        original = base_config()
        result = self.run_defaults(fail="commit dhcp")
        self.assertNotEqual(result.returncode, 0)
        failed = self.data()["committed"]
        self.assertNotIn("state.defaults_version", failed["r3s"])
        self.assertEqual(failed["dhcp"], original["dhcp"])
        self.assertEqual(failed["r3s"]["state.network_done"], "1")
        self.assertIn("ERROR:", (self.root / "log").read_text())
        failed["network"]["lan.ipaddr"] = ["172.31.0.1/24"]
        self.write_config(failed)
        self.assertEqual(self.preinit(), "existing")
        self.assertEqual(self.run_defaults().returncode, 0)
        self.assertEqual(self.data()["committed"]["network"]["lan.ipaddr"], ["172.31.0.1/24"])
        self.assertEqual(self.data()["committed"]["dhcp"], original["dhcp"])
        self.assertEqual(self.data()["committed"]["r3s"]["state.mode"], "existing")
        self.assertEqual(self.data()["committed"]["r3s"]["state.defaults_version"], "1")

    def test_checkpoint_failure_does_not_commit_or_reapply_lan(self):
        self.assertEqual(self.preinit(), 'fresh')
        original = base_config()
        result = self.run_defaults(fail='set r3s.state.network_done=1')
        self.assertNotEqual(result.returncode, 0)
        failed = self.data()['committed']
        self.assertEqual(failed['network'], original['network'])
        self.assertNotIn('state.network_done', failed['r3s'])
        failed['network']['lan.ipaddr'] = ['172.31.0.1/24']
        self.write_config(failed)
        self.assertEqual(self.preinit(), 'existing')
        self.assertEqual(self.run_defaults().returncode, 0)
        self.assertEqual(self.data()['committed']['network']['lan.ipaddr'], ['172.31.0.1/24'])
        self.assertIn('Check LAN, DHCP and system defaults manually', (self.root / 'log').read_text())

    def test_checkpoint_commit_failure_rolls_back_network(self):
        config = base_config()
        config['r3s'] = {'state': 'r3s', 'state.mode': 'fresh'}
        self.write_config(config)
        (self.root / 'tmp/r3s-boot-state').write_text('fresh\n')
        result = self.run_defaults(fail='commit r3s')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.data()['committed']['network'], config['network'])
        self.assertNotIn('state.network_done', self.data()['committed']['r3s'])

    def test_unknown_boot_state_does_not_resume_incomplete_fresh_setup(self):
        config = base_config()
        config['r3s'] = {'state': 'r3s', 'state.mode': 'fresh'}
        self.write_config(config)
        self.assertEqual(self.run_defaults().returncode, 0)
        for package in ('network', 'dhcp', 'system'):
            self.assertEqual(self.data()['committed'][package], config[package])
        self.assertEqual(self.data()['committed']['r3s']['state.mode'], 'existing')

    def test_backup_of_unfinished_setup_does_not_resume_fresh_defaults(self):
        config = base_config()
        config["r3s"] = {"state": "r3s", "state.mode": "fresh"}
        self.write_config(config)
        (self.root / "tmp/sysupgrade.tar").touch()
        self.assertEqual(self.preinit(), "restored")
        self.assertEqual(self.run_defaults().returncode, 0)
        self.assertEqual(self.data()["committed"]["network"], config["network"])
        self.assertEqual(self.data()["committed"]["r3s"]["state.mode"], "existing")


if __name__ == "__main__":
    unittest.main()
