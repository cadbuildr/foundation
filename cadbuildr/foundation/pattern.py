"""Pattern classes for creating repeated geometric elements."""

import math
import numpy as np
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from.gen.models import Point, Sketch


def _make_point(sketch: "Sketch", x: float, y: float) -> "Point":
    """Construct a Point on the given sketch.

    Done lazily inside the function so importing pattern.py before the
    generated models are registered (codegen-time) doesn't blow up."""
    from.gen.models import Point, FloatParameter

    return Point(sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y))


class GridLocations:
    """Rectangular grid of sketch-anchored positions.

        The grid is centered on the anchor point, so for x_count=3, y_count=3 the
    points sit at (-x_pitch, -y_pitch), (0, -y_pitch), ..., (+x_pitch, +y_pitch).

        positions = GridLocations(s.origin, 10, 10, 3, 3).positions()
        for p in positions:
            self.add_operation(Hole(p, radius=1, depth=5))
    """

    def __init__(
        self,
        center: "Point",
        x_pitch: float,
        y_pitch: float,
        n_x: int,
        n_y: int,
    ):
        if n_x < 1 or n_y < 1:
            raise ValueError("GridLocations requires n_x >= 1 and n_y >= 1")
        self.center = center
        self.x_pitch = float(x_pitch)
        self.y_pitch = float(y_pitch)
        self.n_x = int(n_x)
        self.n_y = int(n_y)

    def positions(self) -> list["Point"]:
        """Return n_x * n_y Points centered on `self.center`."""
        cx = self.center.x.value
        cy = self.center.y.value
        sketch = self.center.sketch
        # Center the grid so the anchor is the geometric centroid.
        x0 = cx - (self.n_x - 1) * self.x_pitch / 2.0
        y0 = cy - (self.n_y - 1) * self.y_pitch / 2.0
        out: list["Point"] = []
        for j in range(self.n_y):
            for i in range(self.n_x):
                out.append(
                    _make_point(
                        sketch,
                        x0 + i * self.x_pitch,
                        y0 + j * self.y_pitch,
                    )
                )
        return out




# List of supported sketch components for patterns
# This will be populated with actual types when needed


class HexLocations:
    """Hexagonal close-pack grid of sketch-anchored positions.

    emits a hex-shaped
    cluster of points laid out on a triangular lattice with `pitch` between
    nearest neighbors. `n_radial` is the number of rings around the anchor:

        n_radial=1 → 1 point  (just the anchor)
        n_radial=2 → 7 points (anchor + 6-around)
        n_radial=3 → 19 points
        n_radial=k → 3·k² - 3·k + 1 points (centered hexagonal numbers)
    """

    def __init__(self, center: "Point", pitch: float, n_radial: int):
        if n_radial < 1:
            raise ValueError("HexLocations requires n_radial >= 1")
        self.center = center
        self.pitch = float(pitch)
        self.n_radial = int(n_radial)

    def positions(self) -> list["Point"]:
        cx = self.center.x.value
        cy = self.center.y.value
        sketch = self.center.sketch
        n = self.n_radial - 1  # ring index range is [-n, n]
        out: list["Point"] = []
        # Axial coords (q, r). Cube-coord constraint: |q + r| ≤ n.
        sqrt3_2 = math.sqrt(3) / 2.0
        for q in range(-n, n + 1):
            r_min = max(-n, -q - n)
            r_max = min(n, -q + n)
            for r in range(r_min, r_max + 1):
                x = self.pitch * (q + r / 2.0)
                y = self.pitch * r * sqrt3_2
                out.append(_make_point(sketch, cx + x, cy + y))
        return out


class PolarLocations:
    """Angular distribution of points on a circle.

    Mirrors the `PolarLocations(radius, count, start_angle=0,
    angular_range=360)`. Emits `count` points evenly distributed on a circle
    of `radius` around `center`, beginning at `start_angle` (degrees).
    Full-circle ranges use `range/count` spacing (no duplicate endpoints);
    partial arcs use `range/(count-1)` (both endpoints included).
    """

    def __init__(
        self,
        center: "Point",
        radius: float,
        count: int,
        start_angle_deg: float = 0.0,
        angular_range_deg: float = 360.0,
    ):
        if count < 1:
            raise ValueError("PolarLocations requires count >= 1")
        self.center = center
        self.radius = float(radius)
        self.count = int(count)
        self.start_angle_deg = float(start_angle_deg)
        self.angular_range_deg = float(angular_range_deg)

    def positions(self) -> list["Point"]:
        cx = self.center.x.value
        cy = self.center.y.value
        sketch = self.center.sketch
        if math.isclose(abs(self.angular_range_deg), 360.0):
            step = self.angular_range_deg / self.count
        else:
            step = self.angular_range_deg / max(self.count - 1, 1)
        out: list["Point"] = []
        for i in range(self.count):
            theta = math.radians(self.start_angle_deg + i * step)
            out.append(
                _make_point(
                    sketch,
                    cx + self.radius * math.cos(theta),
                    cy + self.radius * math.sin(theta),
                )
            )
        return out


class Locations:
    """Explicit list of (x, y) offsets relative to an anchor.

    The simplest pattern: hand
    the user full control over where each point lands."""

    def __init__(self, center: "Point", offsets: Sequence[tuple[float, float]]):
        if not offsets:
            raise ValueError("Locations requires at least one offset")
        self.center = center
        self.offsets = [(float(x), float(y)) for x, y in offsets]

    def positions(self) -> list["Point"]:
        cx = self.center.x.value
        cy = self.center.y.value
        sketch = self.center.sketch
        return [_make_point(sketch, cx + dx, cy + dy) for dx, dy in self.offsets]


class CircularPattern:
    """Create circular pattern of sketch components around a center point."""

    def __init__(self, center: "Point", n_instances: int):
        """
        Initialize circular pattern.

        Args:
            center: Center point for rotation
            n_instances: Total number of instances (including original)
        """
        self.center = center
        self.n_instances = n_instances

    def run(self, sketch_component: Any) -> list[Any]:
        """
        Create circular pattern by rotating sketch component.

        Args:
            sketch_component: The component to pattern (must have rotate method)

        Returns:
            List of rotated copies (excluding the original)
        """
        output: list[Any] = []
        d_angle = 2 * np.pi / self.n_instances

        for i in range(1, self.n_instances):
            # Rotate around center point
            rotated = sketch_component.rotate(i * d_angle, center=self.center)
            output.append(rotated)

        return output


class RectangularPattern:
    """Create rectangular pattern of sketch components."""

    def __init__(self, width: float, height: float, n_rows: int, n_cols: int):
        """
        Initialize rectangular pattern.

        Args:
            width: Spacing between columns
            height: Spacing between rows
            n_rows: Number of rows
            n_cols: Number of columns
        """
        self.width = width
        self.height = height
        self.n_rows = n_rows
        self.n_cols = n_cols

    def run(self, sketch_component: Any) -> list[list[Any]]:
        """
        Create rectangular pattern by translating sketch component.

        Args:
            sketch_component: The component to pattern (must have translate method)

        Returns:
            2D list of translated copies
        """
        output: list[list[Any]] = []

        for i in range(self.n_rows):
            row: list[Any] = []
            for j in range(self.n_cols):
                translated = sketch_component.translate(self.width * j, self.height * i)
                row.append(translated)
            output.append(row)

        return output
