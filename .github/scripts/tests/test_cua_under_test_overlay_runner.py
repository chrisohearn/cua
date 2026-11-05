"""Overlays built from this checkout must run in the sandbox image they are injected into."""

from pathlib import Path
import re

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github/workflows"
TARGET_IMAGE = "ghcr.io/trycua/linux:24.04"
# The build links against the runner's glibc; a newer runner yields GLIBC_x.y not found in the guest.
COMPATIBLE_RUNNER = "ubuntu-24.04"


def overlay_jobs():
    """(workflow, job, runs-on) for each job that injects a build-cua-under-test overlay into the target image."""
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text())
        env = workflow.get("env") or {}
        for name, job in (workflow.get("jobs") or {}).items():
            steps = job.get("steps") or []
            builds = any(step.get("uses") == "./.github/actions/build-cua-under-test" for step in steps)
            for step in steps:
                inputs = step.get("with") or {}
                if step.get("uses") != "./.github/actions/cua-sandbox" or not inputs.get("overlay"):
                    continue
                image = re.sub(r"\$\{\{\s*env\.(\w+)\s*\}\}", lambda m: str(env.get(m.group(1), "")), str(inputs.get("image", "")))
                if builds and image == TARGET_IMAGE:
                    found.append((path.name, name, job.get("runs-on")))
    return found


def test_every_target_overlay_is_built_on_a_compatible_runner():
    jobs = overlay_jobs()
    assert {(workflow, job) for workflow, job, _ in jobs} == {
        ("ci-cua-driver-preflight.yml", "linux"),
        ("ci-cua-sandbox-doctor.yml", "doctor"),
        ("nightly-contrib-doctor.yml", "lane"),
    }, jobs
    for workflow, job, runner in jobs:
        assert runner == COMPATIBLE_RUNNER, f"{workflow}:{job} builds {TARGET_IMAGE} overlays on {runner}"
