"""Resolve user-supplied release names without downloading or cloning upstream.

The remote Git commands use local fixtures; Git's ref-name validation stays local.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
GIT = shutil.which("git")
if os.name == "nt":
    BASH = r"C:\Program Files\Git\usr\bin\bash.exe"
URL = "https://example.invalid/upstream.git"
REVISION = "0123456789abcdef0123456789abcdef01234567"


def shell_path(path):
    value = Path(path).resolve().as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


@unittest.skipUnless(BASH and Path(BASH).is_file() and GIT,
                     "Bash and Git are required")
class ResolveRefTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="r3s-resolve-ref-test-")
        self.addCleanup(self.scratch.cleanup)
        self.tree = Path(self.scratch.name)
        self.bin = self.tree / "bin"
        self.bin.mkdir()
        self.refs = self.tree / "remote-refs"
        self.log = self.tree / "git-calls"
        self.refs.write_text("", encoding="utf-8")
        mock = self.bin / "git"
        mock.write_text(r'''#!/bin/bash
{
    printf '%s' "$1"
    shift_argument=0
    for argument in "$@"; do
        if [ "$shift_argument" = 1 ]; then
            printf '\t%s' "$argument"
        fi
        shift_argument=1
    done
    printf '\n'
} >> "$MOCK_GIT_LOG"
case "$1" in
    check-ref-format)
        exec "$REAL_GIT" "$@"
        ;;
    ls-remote)
        if [ "$#" -ne 6 ] || [ "$2" != --refs ] ||
           [ "$3" != --exit-code ] || [ "$4" != "$MOCK_REMOTE_URL" ]; then
            printf '%s\n' 'Unexpected remote Git command' >&2
            exit 90
        fi
        if [ "$MOCK_NETWORK_FAILURE" = all ] ||
           [ "$MOCK_NETWORK_FAILURE" = "$5" ]; then
            printf '%s\n' 'fatal: upstream network failure (fixture)' >&2
            exit 128
        fi
        found=0
        for ref in "$5" "$6"; do
            if grep -Fxq -- "$ref" "$MOCK_REMOTE_REFS"; then
                printf '%s\t%s\n' "$MOCK_REVISION" "$ref"
                found=1
            fi
        done
        [ "$found" = 1 ] && exit 0
        exit 2
        ;;
    *)
        printf '%s\n' 'Unexpected Git subcommand' >&2
        exit 90
        ;;
esac
''', encoding="utf-8", newline="\n")
        mock.chmod(0o755)
        self.env = dict(os.environ,
                        REAL_GIT=shell_path(GIT),
                        MOCK_GIT_LOG=shell_path(self.log),
                        MOCK_REMOTE_REFS=shell_path(self.refs),
                        MOCK_REMOTE_URL=URL,
                        MOCK_REVISION=REVISION,
                        MOCK_NETWORK_FAILURE="")

    def available(self, *refs):
        self.refs.write_text("".join(ref + "\n" for ref in refs),
                             encoding="utf-8", newline="\n")

    def resolve(self, request=None, url=URL):
        # Environment values preserve literal braces/newlines through Git Bash's
        # Windows command-line parsing, so invalid input reaches the helper intact.
        env = dict(self.env, MOCK_REQUEST_URL=url,
                   MOCK_REQUEST=request or "",
                   MOCK_REQUEST_PRESENT="0" if request is None else "1")
        return subprocess.run(
            [BASH, "--noprofile", "--norc", "-c",
             'export PATH="$1:/usr/bin:/bin:$PATH"; '
             'if [ "$MOCK_REQUEST_PRESENT" = 1 ]; then '
             'exec bash "$2" "$MOCK_REQUEST_URL" "$MOCK_REQUEST"; '
             'else exec bash "$2" "$MOCK_REQUEST_URL"; fi',
             "test-resolve-ref", shell_path(self.bin),
             shell_path(ROOT / "scripts/build/resolve-ref.sh")],
            cwd=self.tree, env=env, capture_output=True,
            text=True, encoding="utf-8", timeout=20,
        )

    def git_calls(self):
        if not self.log.exists():
            return []
        return [line.split("\t") for line in
                self.log.read_text(encoding="utf-8").splitlines()]

    def assert_resolved(self, result, ref):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, ref + "\n")

    def assert_rejected(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.strip(), "Failure must explain the problem")

    def test_existing_series_branch_preserves_name(self):
        self.available("refs/heads/openwrt-25.12")
        self.assert_resolved(self.resolve("openwrt-25.12"), "openwrt-25.12")

    def test_existing_release_tag_preserves_name(self):
        self.available("refs/tags/v25.12.2")
        self.assert_resolved(self.resolve("v25.12.2"), "v25.12.2")

    def test_other_existing_branch_preserves_name(self):
        self.available("refs/heads/release/experimental")
        self.assert_resolved(self.resolve("release/experimental"),
                             "release/experimental")

    def test_bare_version_resolves_to_existing_release_tag(self):
        self.available("refs/tags/v25.12.2")
        self.assert_resolved(self.resolve("25.12.2"), "v25.12.2")

    def test_patch_branch_style_resolves_to_existing_release_tag(self):
        self.available("refs/tags/v25.12.2", "refs/heads/openwrt-25.12")
        self.assert_resolved(self.resolve("openwrt-25.12.2"), "v25.12.2")

    def test_actual_patch_branch_takes_precedence_over_release_alias(self):
        self.available("refs/heads/openwrt-25.12.2", "refs/tags/v25.12.2")
        self.assert_resolved(self.resolve("openwrt-25.12.2"), "openwrt-25.12.2")
        remotes = [call for call in self.git_calls() if call[0] == "ls-remote"]
        self.assertEqual(len(remotes), 1)

    def test_actual_bare_version_tag_takes_precedence_over_release_alias(self):
        self.available("refs/tags/25.12.2", "refs/tags/v25.12.2")
        self.assert_resolved(self.resolve("25.12.2"), "25.12.2")

    def test_unknown_patch_does_not_fall_back_to_series_branch(self):
        self.available("refs/heads/openwrt-25.12")
        result = self.resolve("openwrt-25.12.99")
        self.assert_rejected(result)
        self.assertIn("openwrt-25.12.99", result.stderr)
        requested = [ref for call in self.git_calls() if call[0] == "ls-remote"
                     for ref in call[4:]]
        self.assertNotIn("refs/heads/openwrt-25.12", requested)

    def test_unknown_ref_fails_with_diagnostic(self):
        result = self.resolve("missing-branch")
        self.assert_rejected(result)
        self.assertIn("missing-branch", result.stderr)

    def test_invalid_ref_names_are_rejected_before_remote_access(self):
        for name in ("", "bad ref", "bad..ref", "bad:ref", "bad*ref",
                     "branch@{1}", "branch\nsecond", "bad//ref", "bad/ref.lock"):
            with self.subTest(name=name):
                if self.log.exists():
                    self.log.unlink()
                self.assert_rejected(self.resolve(name))
                self.assertFalse(any(call[0] == "ls-remote"
                                     for call in self.git_calls()))

    def test_missing_argument_fails_with_usage(self):
        self.assert_rejected(self.resolve())

    def test_empty_repository_url_is_rejected(self):
        self.assert_rejected(self.resolve("v25.12.2", url=""))

    def test_network_error_is_not_treated_as_a_missing_ref(self):
        self.available("refs/tags/v25.12.2")
        self.env["MOCK_NETWORK_FAILURE"] = "all"
        result = self.resolve("openwrt-25.12.2")
        self.assert_rejected(result)
        self.assertRegex(result.stderr.lower(), "network|remote|upstream|网络|上游")
        self.assertEqual(sum(call[0] == "ls-remote" for call in self.git_calls()), 1)

    def test_alias_lookup_network_error_fails(self):
        self.available("refs/heads/openwrt-25.12")
        self.env["MOCK_NETWORK_FAILURE"] = "refs/heads/v25.12.2"
        result = self.resolve("openwrt-25.12.2")
        self.assert_rejected(result)
        self.assertRegex(result.stderr.lower(), "network|remote|upstream|网络|上游")

    def test_remote_queries_are_exact_branch_and_tag_refs(self):
        self.available("refs/tags/v25.12.2")
        self.assert_resolved(self.resolve("openwrt-25.12.2"), "v25.12.2")
        remotes = [call for call in self.git_calls() if call[0] == "ls-remote"]
        self.assertEqual(remotes, [
            ["ls-remote", "--refs", "--exit-code", URL,
             "refs/heads/openwrt-25.12.2", "refs/tags/openwrt-25.12.2"],
            ["ls-remote", "--refs", "--exit-code", URL,
             "refs/heads/v25.12.2", "refs/tags/v25.12.2"],
        ])
        self.assertIn(["check-ref-format", "refs/heads/openwrt-25.12.2"],
                      self.git_calls())


if __name__ == "__main__":
    unittest.main()
