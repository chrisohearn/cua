"""The pre-setup desktop wait (cua_bench.runner.desktop)."""

from __future__ import annotations

from io import BytesIO

from cua_bench.runner.desktop import is_blank, is_settled, wait_for_desktop
from PIL import Image, ImageDraw


def _png(color=(0, 0, 0), box=None, box_color=(255, 255, 255)) -> bytes:
    image = Image.new("RGB", (200, 100), color)
    if box:
        ImageDraw.Draw(image).rectangle(box, fill=box_color)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


BLACK = _png()
DESKTOP = _png((30, 60, 90), box=(0, 0, 199, 10))
DESKTOP_WITH_APP = _png((30, 60, 90), box=(20, 20, 180, 90))


class Session:
    def __init__(self, shots):
        self.shots = list(shots)
        self.calls = 0

    async def screenshot(self):
        self.calls += 1
        return self.shots[min(self.calls, len(self.shots)) - 1]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds


def test_blank_and_settled():
    assert is_blank(BLACK) and not is_blank(DESKTOP)
    assert is_settled(DESKTOP, DESKTOP)
    # A clock-sized change is still the same desktop; a new window is not.
    ticked = _png((30, 60, 90), box=(190, 2, 195, 6))
    assert is_settled(_png((30, 60, 90)), ticked)
    assert not is_settled(DESKTOP, DESKTOP_WITH_APP)


async def _wait(session, timeout_s=60.0):
    clock = Clock()
    status = await wait_for_desktop(session, timeout_s=timeout_s, clock=clock, sleep=clock.sleep)
    return status, clock.now


async def test_waits_past_a_blank_screen_and_a_late_app():
    # Blank, desktop, then an autostarted app maps: ready only once it is idle.
    session = Session([BLACK, BLACK, DESKTOP, DESKTOP_WITH_APP] + [DESKTOP_WITH_APP] * 5)
    status, waited = await _wait(session)
    assert status == "ready"
    assert session.calls == 6 and waited == 5.0


async def test_times_out_on_a_screen_that_stays_blank():
    session = Session([BLACK])
    status, waited = await _wait(session, timeout_s=5)
    assert status == "timeout" and waited == 5.0
    assert session.calls <= 8  # bounded


async def test_off_and_no_screen(monkeypatch):
    monkeypatch.setenv("CUA_BENCH_DESKTOP_READY_S", "0")
    session = Session([BLACK])
    assert await wait_for_desktop(session) == "off" and session.calls == 0

    class NoScreen:
        async def screenshot(self):
            raise NotImplementedError

    assert await wait_for_desktop(NoScreen(), timeout_s=5) == "no-screen"


def test_kicad_install_errors_carry_stderr():
    """A failed app install names why (sudo, apt), not an empty string."""
    from cua_bench.apps.kicad import _output_tail

    out = _output_tail({"stdout": "", "stderr": "sudo: effective uid is not 0", "return_code": 1})
    assert out == "sudo: effective uid is not 0"
    assert _output_tail({"stdout": "", "stderr": "", "return_code": 100}) == "exit code 100"


async def test_kicad_public_netlist_methods(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from cua_bench.apps.registry import AppsProxy

    reference = """(export
      (components (comp (ref "R1") (value "1k")
        (libsource (lib "Device") (part "R"))))
      (nets (net (code "1") (name "signal") (node (ref "R1") (pin "1")))))"""
    candidate = reference.replace('"signal"', '"renamed"')
    session = SimpleNamespace(
        os_type="linux", run_command=AsyncMock(return_value={"stdout": candidate})
    )
    app = AppsProxy(session).kicad

    assert await app.get_components(netlist_path="/candidate.net") == [
        {"ref": "R1", "value": "1k", "lib": "Device", "part": "R"}
    ]
    session.run_command.assert_awaited_once_with('cat "/candidate.net"', check=False)

    session.run_command.return_value = {"stdout": "* circuit\nR1 in 0 1k\n.end\n"}
    assert await app.get_components(netlist_path="/circuit.cir") == [
        {"ref": "R1", "type": "resistor", "value": "1k", "nodes": ["in", "0"]}
    ]

    reference_path = tmp_path / "reference.net"
    reference_path.write_text(reference, encoding="utf-8")
    paths = {"candidate_path": "/candidate.net", "reference_path": str(reference_path)}
    session.run_command.return_value = {"stdout": candidate}
    assert await app.compare_netlist(**paths) == 1.0  # Net names are ignored.

    session.run_command.return_value = {"stdout": candidate.replace('"1k"', '"2k"')}
    assert await app.compare_netlist(**paths) == 0.5
    assert await app.compare_netlist(**paths, require_same_components=False) == 1.0

    session.run_command.return_value = {"stdout": candidate.replace('(pin "1")', '(pin "2")')}
    assert await app.compare_netlist(**paths) == 0.5
    assert await app.compare_netlist(**paths, require_same_nets=False) == 1.0
