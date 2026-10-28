"""KiCad EDA app definition."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from .registry import App, install, launch, uninstall

if TYPE_CHECKING:
    from .registry import BoundApp

_SPICE_TYPE_MAP = {
    "R": "resistor",
    "C": "capacitor",
    "L": "inductor",
    "V": "voltage_source",
    "I": "current_source",
    "D": "diode",
    "Q": "bjt",
    "M": "mosfet",
    "X": "subcircuit",
}


def _output_tail(result, limit: int = 800) -> str:
    """The end of a run_command result's stdout and stderr, for errors."""
    if not isinstance(result, dict):
        return str(result)[-limit:]
    text = "\n".join(p for p in (result.get("stdout"), result.get("stderr")) if p).strip()
    return text[-limit:] or f"exit code {result.get('return_code')}"


def _stdout(result) -> str:
    """Extract stdout string from a run_command result."""
    return (result.get("stdout", "") if isinstance(result, dict) else str(result)).strip()


def _parse_spice_components(netlist: str) -> List[dict]:
    """Parse SPICE netlist text into a list of component dicts."""
    components = []
    for line in netlist.splitlines():
        line = line.strip()
        if not line or line.startswith(("*", ".", "#")):
            continue
        parts = line.split()
        ref = parts[0]
        ctype = _SPICE_TYPE_MAP.get(ref[0].upper(), "unknown")
        components.append({"ref": ref, "type": ctype, "value": parts[-1], "nodes": parts[1:-1]})
    return components


class KiCad(App):
    """KiCad - Open source electronics design automation.

    KiCad is a free software suite for schematic capture and PCB layout.

    Install options:
        - with_shortcut: Create desktop shortcut (default True)

    Launch options:
        - project_path: Path to project directory (optional)
    """

    name = "kicad"
    description = "KiCad - Open source electronics design automation"

    # =========================================================================
    # Linux
    # =========================================================================

    @install("linux")
    async def install_linux(
        self: "BoundApp",
        *,
        with_shortcut: bool = True,
    ) -> None:
        """Ensure KiCad is available on Linux and optionally create a shortcut."""
        verify = await self.session.run_command(
            "command -v kicad >/dev/null 2>&1 && echo FOUND || echo NOT_FOUND",
            check=False,
        )
        if _stdout(verify) != "FOUND":
            # The canonical desktop image has no add-apt-repository
            # (software-properties-common): install it first when missing.
            result = await self.session.run_command(
                "export DEBIAN_FRONTEND=noninteractive; "
                "{ command -v add-apt-repository >/dev/null 2>&1 || "
                "{ sudo -E apt-get update && "
                "sudo -E apt-get install -y software-properties-common; }; } && "
                "sudo -E add-apt-repository --yes ppa:kicad/kicad-9.0-releases && "
                "sudo -E apt-get update && "
                "sudo -E apt-get install -y --install-recommends kicad",
                check=False,
                timeout=1800,
            )
            verify = await self.session.run_command(
                "command -v kicad >/dev/null 2>&1 && echo FOUND || echo NOT_FOUND",
                check=False,
            )
        if _stdout(verify) != "FOUND":
            raise RuntimeError(f"KiCad install failed: {_output_tail(result)}")

        if with_shortcut:
            await self.session.run_command(
                "mkdir -p ~/Desktop ~/.local/share/applications && "
                "printf '%s\n' "
                "'[Desktop Entry]' "
                "'Name=KiCad' "
                "'Comment=Electronic Design Automation Suite' "
                "'Exec=kicad' "
                "'Icon=kicad' "
                "'Type=Application' "
                "'Categories=Development;Electronics;' "
                "'Terminal=true' "  # currently requires terminal otherwise the gui crashes when opening the file explorer, not sure why
                "> ~/Desktop/KiCad.desktop && "
                "chmod +x ~/Desktop/KiCad.desktop && "
                "cp ~/Desktop/KiCad.desktop ~/.local/share/applications/KiCad.desktop",
                check=False,
            )

    @launch("linux")
    async def launch_linux(
        self: "BoundApp",
        *,
        project_path: Optional[str] = None,
    ) -> None:
        """Launch KiCad on Linux."""
        kicad_args = ["/usr/bin/kicad"]
        if project_path:
            kicad_args.append(project_path)
        kicad_args_repr = repr(kicad_args)
        launch_script = (
            "import subprocess, os; "
            f"subprocess.Popen({kicad_args_repr}, "
            "env={**os.environ, 'DISPLAY': ':1'}, "
            "close_fds=True, start_new_session=True, "
            "stdin=open('/dev/null'), "
            "stdout=open('/dev/null', 'w'), "
            "stderr=open('/dev/null', 'w'))"
        )
        await self.session.run_command(f'python3 -c "{launch_script}"', check=False)
        await asyncio.sleep(15)

    @uninstall("linux")
    async def uninstall_linux(self: "BoundApp", **kwargs) -> None:
        """Uninstall KiCad from Linux."""
        await self.session.run_command(
            "sudo apt remove -y kicad && "
            "rm -f ~/Desktop/KiCad.desktop && "
            "rm -f ~/.local/share/applications/KiCad.desktop",
            check=False,
        )

    # =========================================================================
    # Windows
    # =========================================================================

    @install("windows")
    async def install_windows(
        self: "BoundApp",
        *,
        with_shortcut: bool = True,
    ) -> None:
        """Install KiCad on Windows via winget."""
        await self.session.run_command(
            "winget install -e --id KiCad.KiCad --accept-package-agreements --accept-source-agreements",
            check=False,
        )
        await asyncio.sleep(30)  # Installer may take a while

    @launch("windows")
    async def launch_windows(
        self: "BoundApp",
        *,
        project_path: Optional[str] = None,
    ) -> None:
        """Launch KiCad on Windows."""
        if project_path:
            # Launch KiCad with project path (opens project)
            await self.session.run_command(
                f'start "" "C:\\Program Files\\KiCad\\8.0\\bin\\kicad.exe" "{project_path}"',
                check=False,
            )
        else:
            await self.session.run_command(
                'start "" "C:\\Program Files\\KiCad\\8.0\\bin\\kicad.exe"',
                check=False,
            )
        await asyncio.sleep(5)

    @uninstall("windows")
    async def uninstall_windows(self: "BoundApp", **kwargs) -> None:
        """Uninstall KiCad from Windows."""
        await self.session.run_command(
            "winget uninstall -e --id KiCad.KiCad",
            check=False,
        )

    # =========================================================================
    # macOS
    # =========================================================================

    @install("macos")
    async def install_macos(
        self: "BoundApp",
        *,
        with_shortcut: bool = True,
    ) -> None:
        """Install KiCad on macOS via Homebrew."""
        await self.session.run_command(
            "brew install --cask kicad",
            check=False,
        )

    @launch("macos")
    async def launch_macos(
        self: "BoundApp",
        *,
        project_path: Optional[str] = None,
    ) -> None:
        """Launch KiCad on macOS."""
        cmd = 'open -a "KiCad"'
        if project_path:
            cmd += f' --args "{project_path}"'
        await self.session.run_command(cmd, check=False)
        await asyncio.sleep(3)

    @uninstall("macos")
    async def uninstall_macos(self: "BoundApp", **kwargs) -> None:
        """Uninstall KiCad from macOS."""
        await self.session.run_command("brew uninstall --cask kicad", check=False)

    # =========================================================================
    # Netlist helpers (cross-platform)
    # =========================================================================

    async def export_netlist(
        self: "BoundApp",
        *,
        schematic_path: str,
        output_path: str,
    ) -> str:
        """Export a SPICE netlist from a .kicad_sch using kicad-cli.

        Args:
            schematic_path: Path to the .kicad_sch schematic on the VM.
            output_path: Destination path for the .cir netlist on the VM.

        Returns:
            The output_path on success.

        Raises:
            RuntimeError: If the output file was not created.
        """
        result = await self.session.run_command(
            f'kicad-cli sch export spice -o "{output_path}" "{schematic_path}"',
            check=False,
        )
        verify = await self.session.run_command(
            f'test -f "{output_path}" && echo FOUND || echo NOT_FOUND',
            check=False,
        )
        if _stdout(verify) != "FOUND":
            raise RuntimeError(f"Netlist export failed: {_stdout(result)}")
        return output_path

    async def read_netlist(self: "BoundApp", *, netlist_path: str) -> str:
        """Read a netlist file from the VM (SPICE .cir or KiCad .net).

        Args:
            netlist_path: Path to the netlist file on the VM.

        Returns:
            Raw text content of the netlist.
        """
        result = await self.session.run_command(
            f'cat "{netlist_path}"',
            check=False,
        )
        return _stdout(result)

    async def get_components(self: "BoundApp", *, netlist_path: str) -> List[dict]:
        """Read and parse a netlist into structured components.

        Supports SPICE (.cir) and KiCad (.net) formats.

        Args:
            netlist_path: Path to the .cir or .net file on the VM.

        Returns:
            List of dicts with keys ``ref``, ``type``, ``value``, ``lib``,
            ``part``, ``nodes``.
        """
        netlist = await self.read_netlist(netlist_path=netlist_path)
        if netlist_path.rstrip("/").endswith(".net"):
            from cua_bench.netlist_compare import parse_kicad_netlist

            return parse_kicad_netlist(netlist)["components"]
        return _parse_spice_components(netlist)

    async def compare_netlist(
        self: "BoundApp",
        *,
        candidate_path: str,
        reference_path: str,
        require_same_components: bool = True,
        require_same_nets: bool = True,
    ) -> float:
        """Compare the agent's output netlist against a reference.

        Reads the candidate from the VM and the reference from the local
        filesystem, returning a structural similarity score in [0.0, 1.0].

        Components are matched by (ref_prefix, normalized_value, part) —
        ref numbers and order may differ. Nets are matched by their set of
        (ref, pin) connections — net names are ignored.

        Args:
            candidate_path: Path to the candidate .net file on the VM.
            reference_path: Absolute path to the reference .net file locally.
            require_same_components: Include component-set check (default True).
            require_same_nets: Include net-topology check (default True).

        Returns:
            Score 0.0 (no match) to 1.0 (exact match).
        """
        from cua_bench.netlist_compare import compare_kicad_netlists

        candidate = await self.read_netlist(netlist_path=candidate_path)
        reference = Path(reference_path).read_text(encoding="utf-8", errors="replace")
        return compare_kicad_netlists(
            candidate,
            reference,
            require_same_components=require_same_components,
            require_same_nets=require_same_nets,
            require_same_net_names=False,
        )

    async def simulate_operating_point(
        self: "BoundApp",
        *,
        netlist_path: str,
        ground: int = 0,
    ) -> Dict[str, float]:
        """Run a DC operating-point simulation via PySpice.

        Reads the netlist from the VM, then simulates locally.
        Requires the ``spice`` extra (``pip install cua-bench[spice]``).

        Args:
            netlist_path: Path to the .cir file on the VM.
            ground: Node number to use as ground reference.

        Returns:
            Dict mapping node name to its DC voltage.
        """
        from PySpice.Spice.Parser import SpiceParser

        netlist = await self.read_netlist(netlist_path=netlist_path)
        parser = SpiceParser(source=netlist)
        circuit = parser.build_circuit(ground=ground)
        simulator = circuit.simulator(temperature=25, nominal_temperature=25)
        analysis = simulator.operating_point()
        return {str(node): float(node) for node in analysis.nodes.values()}

    async def simulate_transient(
        self: "BoundApp",
        *,
        netlist_path: str,
        step_time_us: float,
        end_time_us: float,
        ground: int = 0,
    ) -> Dict[str, list]:
        """Run a transient simulation via PySpice.

        Reads the netlist from the VM, then simulates locally.
        Requires the ``spice`` extra (``pip install cua-bench[spice]``).

        Args:
            netlist_path: Path to the .cir file on the VM.
            step_time_us: Simulation step time in microseconds.
            end_time_us: Simulation end time in microseconds.
            ground: Node number to use as ground reference.

        Returns:
            Dict with a ``time`` key (list of seconds) and one key per
            circuit node mapping to a list of voltage samples.
        """
        from PySpice.Spice.Parser import SpiceParser
        from PySpice.Unit import u_us

        netlist = await self.read_netlist(netlist_path=netlist_path)
        parser = SpiceParser(source=netlist)
        circuit = parser.build_circuit(ground=ground)
        simulator = circuit.simulator(temperature=25, nominal_temperature=25)
        analysis = simulator.transient(step_time=step_time_us @ u_us, end_time=end_time_us @ u_us)
        result: Dict[str, list] = {
            "time": [float(t) for t in analysis.time],
        }
        for node in analysis.nodes.values():
            result[str(node)] = [float(v) for v in node]
        return result
