"""
Helpers for preparing AVL command files and orchestrating viewer setup.

This module contains the :class:`AVLViewerOrchestrator` which coordinates the
generation of geometry, run case, and command files required to launch AVL and
display both geometry and Trefftz plots.
"""

from __future__ import annotations

import csv
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

LOGGER = logging.getLogger("avl_viewer.commands")

DEFAULT_GEOMETRY_NAME = "wing_from_ntop.avl"
DEFAULT_RUN_NAME = "wing_from_ntop.run"
DEFAULT_COMMAND_NAME = "wing_from_ntop.commands"


@dataclass
class AVLViewerOrchestrator:
    """Coordinates geometry preparation and AVL command generation."""

    le_csv: Optional[Path]
    te_csv: Optional[Path]
    avl_geometry: Optional[Path]
    output_dir: Path
    alpha: float
    mach: float
    avl_executable: Optional[Path]

    # Internal state populated during preparation
    geometry_file: Optional[Path] = None
    run_file: Optional[Path] = None
    command_script: Optional[Path] = None
    command_input: Optional[str] = None

    def prepare(self) -> Path:
        """Prepare all assets required to launch AVL."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        LOGGER.debug("Preparing AVL assets in %s", self.output_dir)

        self.geometry_file = self._ensure_geometry_file()
        base_name = self.geometry_file.stem

        self.run_file = self.output_dir / f"{base_name}.run"
        self.command_script = self.output_dir / f"{base_name}.commands"

        self._generate_run_file()
        self.command_input = self._generate_command_script(base_name)

        return self.command_script

    @property
    def working_directory(self) -> Path:
        """Return working directory for the AVL process."""
        return self.output_dir

    def build_avl_launch_command(self, command_script: Path) -> list[str]:
        """Construct the command used to launch AVL."""
        executable = self._detect_avl_executable()
        if self.geometry_file is None:
            raise RuntimeError("Geometry file has not been prepared.")

        return [str(executable), str(self.geometry_file)]

    # ------------------------------------------------------------------
    # Geometry preparation
    # ------------------------------------------------------------------
    def _ensure_geometry_file(self) -> Path:
        """
        Ensure an AVL geometry file is available.

        If ``self.avl_geometry`` is provided it will be copied into the output
        directory (if not already located there). Otherwise a new geometry file
        will be generated from the provided CSV point data.
        """
        if self.avl_geometry is not None:
            if not self.avl_geometry.exists():
                raise FileNotFoundError(
                    f"Specified AVL geometry file does not exist: {self.avl_geometry}"
                )
            destination = self.output_dir / self.avl_geometry.name
            if destination != self.avl_geometry:
                shutil.copy2(self.avl_geometry, destination)
            LOGGER.info("Using existing AVL geometry: %s", destination)
            return destination

        if self.le_csv is None or self.te_csv is None:
            raise ValueError(
                "LE/TE CSV files must be supplied when geometry is not provided."
            )

        geometry_path = self.output_dir / DEFAULT_GEOMETRY_NAME
        self._generate_geometry_from_points(geometry_path)
        LOGGER.info("Generated AVL geometry at %s", geometry_path)
        return geometry_path

    # ------------------------------------------------------------------
    # Geometry generation placeholder (implemented later)
    # ------------------------------------------------------------------
    def _generate_geometry_from_points(self, output_path: Path) -> None:
        """
        Generate an AVL file from nTop point data.

        The implementation mirrors the functionality that was previously housed
        in ``regenerate_wing.py`` but is adapted into reusable helper
        functions so it can be invoked programmatically.
        """
        assert self.le_csv is not None and self.te_csv is not None

        le_points = _read_point_file(self.le_csv)
        te_points = _read_point_file(self.te_csv)

        le_ft = le_points / 12.0
        te_ft = te_points / 12.0

        chords = np.linalg.norm(te_ft - le_ft, axis=1)
        y_coords = le_ft[:, 1]

        span = float(np.max(y_coords) - np.min(y_coords))

        area = 0.0
        mac_sum = 0.0
        for idx in range(len(le_ft) - 1):
            dy = abs(y_coords[idx + 1] - y_coords[idx])
            area += (chords[idx] + chords[idx + 1]) / 2.0 * dy
            mac_sum += (chords[idx] ** 2 + chords[idx + 1] ** 2) / 2.0 * dy

        mac = mac_sum / area if area > 0 else float(np.mean(chords))
        x_ref = float(np.mean(le_ft[:, 0]))
        y_ref = float(np.mean(le_ft[:, 1]))
        z_ref = float(np.mean(le_ft[:, 2]))

        min_panels = 3
        panels_per_ft = 2

        lines = [
            "!***************************************",
            "!AVL input file generated from nTop geometry",
            "!***************************************",
            "nTop Geometry",
            "!Mach",
            " 0.000",
            "!IYsym   IZsym   Zsym",
            " 0       0       0.000",
            "!Sref    Cref    Bref",
            f"{area:.6f}     {mac:.6f}     {span:.6f}",
            "!Xref    Yref    Zref",
            f"{x_ref:.6f}     {y_ref:.6f}     {z_ref:.6f}",
            "",
            "SURFACE",
            "WING",
            "!Nchordwise  Cspace",
            "8            1.0",
            "",
        ]

        for idx, point in enumerate(le_ft):
            lines.append("SECTION")
            lines.append("!Xle    Yle    Zle     Chord   Ainc  Nspanwise  Sspace")

            if idx < len(le_ft) - 1:
                dy = abs(y_coords[idx + 1] - y_coords[idx])
                nspan = max(min_panels, int(dy * panels_per_ft))
            else:
                nspan = 0

            lines.append(
                f"{point[0]:.6f}    {point[1]:.6f}    {point[2]:.6f}    "
                f"{chords[idx]:.6f}   0.000   {nspan}          1.000"
            )
            lines.append("NACA")
            lines.append("2412")
            lines.append("")

        lines.append("END")
        lines.append("")

        output_path.write_text("\n".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------
    # Run file and command script generation
    # ------------------------------------------------------------------
    def _generate_run_file(self) -> None:
        """Generate the AVL run file for the requested operating point."""
        if self.run_file is None:
            raise RuntimeError("Run file path has not been initialised.")

        run_contents = _build_single_case_run_file(alpha=self.alpha, mach=self.mach)
        self.run_file.write_text(run_contents, encoding="utf-8")
        LOGGER.info("Created AVL run file: %s", self.run_file)

    def _generate_command_script(self, base_name: str) -> str:
        """
        Generate the AVL command script that loads the geometry, executes the
        operating case, and displays both plots.
        """
        if self.command_script is None or self.run_file is None:
            raise RuntimeError("Command script/run file not initialised.")

        command_lines = [
            "CASE",
            self.run_file.name,
            "OPER",
            "#",
            "1",
            "X",
            "G",
            "V",
            "90",
            "90",
            "",
            "T",
        ]

        command_text = "\n".join(command_lines) + "\n"
        self.command_script.write_text(command_text, encoding="utf-8")
        LOGGER.info("Generated AVL command script: %s", self.command_script)
        return command_text

    # ------------------------------------------------------------------
    # AVL executable detection
    # ------------------------------------------------------------------
    def _detect_avl_executable(self) -> Path:
        """Attempt to locate the AVL executable."""
        if self.avl_executable is not None:
            if not self.avl_executable.exists():
                raise FileNotFoundError(
                    f"Specified AVL executable does not exist: {self.avl_executable}"
                )
            return self.avl_executable

        candidate_paths = [
            Path("binw32/avl3.51-32.exe"),
            Path("bin/avl.exe"),
            Path("avl.exe"),
        ]
        for path in candidate_paths:
            if path.exists():
                self.avl_executable = path.resolve()
                LOGGER.info("Detected AVL executable at %s", self.avl_executable)
                return self.avl_executable

        raise FileNotFoundError(
            "Could not locate AVL executable. Please specify --avl-exe."
        )


def _build_single_case_run_file(alpha: float, mach: float) -> str:
    """Build a minimal AVL run file for a single operating point."""
    contents = [
        "---------------------------------------------",
        f" Run case  1:  alpha = {alpha:6.2f} deg",
        "",
        f" alpha        ->  alpha       = {alpha:12.5f}",
        " beta         ->  beta        =   0.00000",
        " pb/2V        ->  pb/2V       =   0.00000",
        " qc/2V        ->  qc/2V       =   0.00000",
        " rb/2V        ->  rb/2V       =   0.00000",
        "",
        f" alpha     = {alpha:12.5f}     deg",
        " beta      =   0.00000     deg",
        " pb/2V     =   0.00000",
        " qc/2V     =   0.00000",
        " rb/2V     =   0.00000",
        " CL        =   0.00000",
        " CDo       =   0.00000",
        " bank      =   0.00000     deg",
        " elevation =   0.00000     deg",
        " heading   =   0.00000     deg",
        f" Mach      = {mach:12.5f}",
        " velocity  =   0.00000     ft/s",
        " density   =  0.0023769     slug/ft^3",
        " grav.acc. =  32.17400     ft/s^2",
        " turn_rad. =   0.00000     ft",
        " load_fac. =   1.00000",
        " X_cg      =   0.00000     ft",
        " Y_cg      =   0.00000     ft",
        " Z_cg      =   0.00000     ft",
        " mass      =   1.00000     slug",
        " Ixx       =   1.00000     slug-ft^2",
        " Iyy       =   1.00000     slug-ft^2",
        " Izz       =   1.00000     slug-ft^2",
        " Ixy       =   0.00000     slug-ft^2",
        " Iyz       =   0.00000     slug-ft^2",
        " Izx       =   0.00000     slug-ft^2",
        " visc CL_a =   0.00000",
        " visc CL_u =   0.00000",
        " visc CM_a =   0.00000",
        " visc CM_u =   0.00000",
        "",
    ]
    return "\n".join(contents)


def _read_point_file(csv_path: Path) -> np.ndarray:
    """Load a CSV file containing X, Y, Z coordinates."""
    points = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header_skipped = False
        for row in reader:
            if not header_skipped:
                header_skipped = True
                continue
            if len(row) < 3:
                continue
            try:
                points.append([float(row[0]), float(row[1]), float(row[2])])
            except ValueError:
                continue

    if not points:
        raise ValueError(f"No valid XYZ data found in {csv_path}")

    return np.asarray(points, dtype=float)


__all__ = [
    "AVLViewerOrchestrator",
]

