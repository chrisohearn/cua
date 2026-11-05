"""The Linux readiness preflight must show why the source driver failed to run."""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT = REPO_ROOT / "scripts/ci/linux/preflight-rust-e2e.sh"


@unittest.skipIf(sys.platform == "win32", "bash preflight")
class TestLinuxPreflightDriverCheck(unittest.TestCase):
    def run_preflight(self, driver_script: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as home:
            driver = Path(home) / "cua-driver"
            driver.write_text("#!/bin/sh\n" + driver_script)
            driver.chmod(0o755)
            # No display or session bus, so only the driver lines vary between runs.
            env = {"PATH": os.environ["PATH"], "HOME": home, "CUA_TEST_DRIVER_BIN": str(driver)}
            return subprocess.run(["bash", str(PREFLIGHT)], env=env, capture_output=True, text=True, timeout=60)

    def test_failed_version_shows_exit_status_and_output_and_still_fails(self) -> None:
        result = self.run_preflight("echo 'loader: libfixture.so.9: cannot open shared object file' >&2\nexit 127\n")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("source driver cannot run --version", result.stderr)
        self.assertIn("(exit 127)", result.stderr)
        self.assertIn("version output: loader: libfixture.so.9: cannot open shared object file", result.stderr)
        self.assertNotIn("[ready] driver version", result.stdout)

    def test_silent_version_failure_is_reported_as_no_output(self) -> None:
        result = self.run_preflight("exit 1\n")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("(exit 1)", result.stderr)
        self.assertIn("version output: <none>", result.stderr)

    def test_working_driver_keeps_version_and_identity_checks(self) -> None:
        head = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        result = self.run_preflight(
            'case "$1" in\n'
            "  --version) echo 'cua-driver 9.9.9' ;;\n"
            f"  doctor) echo '{{\"build\":{{\"git_sha\":\"{head}\"}}}}' ;;\n"
            "esac\n"
        )
        self.assertIn("[ready] driver version: cua-driver 9.9.9", result.stdout)
        self.assertNotIn("cannot run --version", result.stderr)
        if shutil.which("jq"):
            self.assertIn(f"[ready] driver built from the source under test: {head}", result.stdout)


if __name__ == "__main__":
    unittest.main()
