"""Pattern classes for creating repeated geometric elements."""

import numpy as np
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .gen.models import Point

# List of supported sketch components for patterns
# This will be populated with actual types when needed


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
