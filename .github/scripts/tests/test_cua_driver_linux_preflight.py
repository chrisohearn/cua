"""The Linux readiness preflight must reject a driver that cannot run, and show why."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT = REPO_ROOT / "scripts/ci/linux/preflight-rust-e2e.sh"

# Every other prerequisite passes, so the driver check alone decides the exit status.
HEALTHY_TOOLS = {
    "xdpyinfo": "exit 0\n",
    "ffmpeg": "exit 0\n",
    "ffprobe": "exit 0\n",
    "gdbus": "exit 0\n",
    # Stands in for `jq -r '.build.git_sha // empty'` on the driver's doctor JSON.
    "jq": "exec python3 -c 'import json, sys; print(json.load(sys.stdin).get(\"build\", {}).get(\"git_sha\", \"\"))'\n",
}


def write_executable(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)


@unittest.skipUnless(sys.platform.startswith("linux"), "the Linux preflight requires a Linux host")
class TestLinuxPreflightDriverCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.source_sha = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                                         capture_output=True, text=True, check=True).stdout.strip()

    def run_preflight(self, driver_script: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as home:
            stubs = Path(home) / "bin"
            stubs.mkdir()
            for tool, body in HEALTHY_TOOLS.items():
                write_executable(stubs / tool, body)
            driver = Path(home) / "cua-driver"
            write_executable(driver, driver_script)
            env = {
                "PATH": f"{stubs}:{os.environ['PATH']}",
                "HOME": home,
                "DISPLAY": ":99",
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent/fixture-bus",
                "CUA_TEST_DRIVER_BIN": str(driver),
            }
            return subprocess.run(["bash", str(PREFLIGHT)], env=env, capture_output=True, text=True, timeout=60)

    def test_failed_version_rejects_readiness_and_shows_why(self) -> None:
        result = self.run_preflight("echo 'loader: libfixture.so.9: cannot open shared object file' >&2\nexit 127\n")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("1 required preflight check(s) failed", result.stderr)
        self.assertIn("source driver cannot run --version", result.stderr)
        self.assertIn("(exit 127)", result.stderr)
        self.assertIn("version output: loader: libfixture.so.9: cannot open shared object file", result.stderr)

    def test_silent_version_failure_rejects_readiness(self) -> None:
        result = self.run_preflight("exit 1\n")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("1 required preflight check(s) failed", result.stderr)
        self.assertIn("(exit 1)", result.stderr)
        self.assertIn("version output: <none>", result.stderr)

    def test_working_driver_with_exact_identity_is_ready(self) -> None:
        result = self.run_preflight(
            'case "$1" in\n'
            "  --version) echo 'cua-driver 9.9.9' ;;\n"
            f"  doctor) echo '{{\"build\":{{\"git_sha\":\"{self.source_sha}\"}}}}' ;;\n"
            "esac\n"
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("[ready] driver version: cua-driver 9.9.9", result.stdout)
        self.assertIn(f"[ready] driver built from the source under test: {self.source_sha}", result.stdout)
        self.assertEqual("", result.stderr)


if __name__ == "__main__":
    unittest.main()
