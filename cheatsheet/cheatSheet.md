# Foundation Sketch Cheatsheet

This cheatsheet covers the Foundation Sketch library, which provides classes and functions for creating and manipulating 2D sketches. The library includes classes for points, lines, arcs, circles, ellipses, polygons, and more.

## Arc

The `Arc` class represents an arc in a 2D sketch. It is defined by a center point, a start point, and an end point.

### Methods

- `calculate_radius() -> float`: Calculate the radius of the arc.
- `calculate_start_and_end_angles() -> tuple[float, float]`: Calculate the start and end angles of the arc.
- `get_points(n_points: int = 20) -> list[Point]`: Get a list of points along the arc.
- `rotate(angle: float, center: Point | None = None) -> "Arc"`: Rotate the arc around a specified center point.
- `translate(dx: float, dy: float) -> "Arc"`: Translate the arc by a specified distance.
- `from_three_points(p1: Point, p2: Point, p3: Point) -> "Arc"`: Create an arc that starts at p1, goes through p2, and ends at p3.
- `from_point_with_tangent_and_point(tangent: Line, p2: Point)`: Create an arc with a specified tangent line and end point (not implemented).

### Example

```python
center = Point(sketch, 0, 0)
p1 = Point(sketch, 1, 0)
p2 = Point(sketch, 0, 1)
arc = Arc(center, p1, p2)
points = arc.get_points(10)
```

## EllipseArc

The `EllipseArc` class represents an elliptical arc in a 2D sketch. It is defined by a center point, a major axis length, a minor axis length, a start angle, and an end angle.

### Methods

- `get_points(n_points: int = 20) -> list[Point]`: Get a list of points along the elliptical arc.
- `rotate(angle: float, center: Point | None = None) -> "Arc"`: Rotate the elliptical arc around a specified center point.
- `translate(dx: float, dy: float) -> "Arc"`: Translate the elliptical arc by a specified distance.

### Example

```python
center = Point(sketch, 0, 0)
a = 2
b = 1
start_angle = 0
end_angle = math.pi
ellipse_arc = EllipseArc(center, a, b, start_angle, end_angle)
points = ellipse_arc.get_points(10)
```

## Axis

The `Axis` class represents an axis in a 2D sketch. It is defined by a line.

### Methods

- `get_axis_rotation() -> float`: Get the rotation angle of the axis compared to the y-axis.
- `get_axis_translation() -> float`: Get the distance from the origin to the axis.
- `get_axis_perpendicular_normed_vector() -> tuple[float, float]`: Get the normalized perpendicular vector to the axis line.
- `transform_point(point: Point) -> Point`: Transform a point based on the axis.
- `get_new_frame() -> Frame`: Get a new frame with the axis as the origin.

### Example

```python
line = Line(Point(sketch, 0, 0), Point(sketch, 1, 1))
axis = Axis(line)
rotation = axis.get_axis_rotation()
translation = axis.get_axis_translation()
```

## SketchShape

The `SketchShape` class is a base class for all shapes in a 2D sketch. It provides a common interface for getting the plane and frame of a shape.

### Methods

- `get_plane() -> PlaneFromFrame`: Get the plane of the shape.
- `get_frame() -> Frame`: Get the frame of the shape.

## ClosedSketchShape

The `ClosedSketchShape` class is a base class for all closed shapes in a 2D sketch. It provides a common interface for getting the points of a shape.

### Methods

- `get_points() -> list[Point]`: Get the points of the shape.

## CustomClosedSketchShape

The `CustomClosedSketchShape` class represents a custom closed shape in a 2D sketch. It is defined by a list of primitives (lines, arcs, circles, etc.).

### Methods

- `get_points() -> list[Point]`: Get the points of the shape.
- `rotate(angle: float, center: Point | None = None) -> "CustomClosedSketchShape"`: Rotate the custom closed shape around a specified center point.
- `translate(dx: float, dy: float) -> "CustomClosedSketchShape"`: Translate the custom closed shape by a specified distance.

### Example

```python
line1 = Line(Point(sketch, 0, 0), Point(sketch, 1, 0))
line2 = Line(Point(sketch, 1, 0), Point(sketch, 1, 1))
line3 = Line(Point(sketch, 1, 1), Point(sketch, 0, 1))
line4 = Line(Point(sketch, 0, 1), Point(sketch, 0, 0))
shape = CustomClosedSketchShape([line1, line2, line3, line4])
points = shape.get_points()
```

## Polygon

The `Polygon` class represents a polygon in a 2D sketch. It is defined by a list of lines.

### Methods

- `check_if_closed()`: Check if the polygon is closed.
- `get_points() -> list[Point]`: Get the points of the polygon.
- `rotate(angle: float, center: Point | None = None) -> "Polygon"`: Rotate the polygon around a specified center point.
- `translate(dx: float, dy: float) -> "Polygon"`: Translate the polygon by a specified distance.

### Example

```python
line1 = Line(Point(sketch, 0, 0), Point(sketch, 1, 0))
line2 = Line(Point(sketch, 1, 0), Point(sketch, 1, 1))
line3 = Line(Point(sketch, 1, 1), Point(sketch, 0, 1))
line4 = Line(Point(sketch, 0, 1), Point(sketch, 0, 0))
polygon = Polygon(sketch, [line1, line2, line3, line4])
points = polygon.get_points()
```

## Circle

The `Circle` class represents a circle in a 2D sketch. It is defined by a center point and a radius.

### Methods

- `get_center() -> Point`: Get the center of the circle.
- `get_points() -> list[Point]`: Get a list of points along the circle.
- `rotate(angle: float, center: Point | None = None) -> "Circle"`: Rotate the circle around a specified center point.
- `translate(dx: float, dy: float) -> "Circle"`: Translate the circle by a specified distance.

### Example

```python
center = Point(sketch, 0, 0)
radius = 1
circle = Circle(center, radius)
points = circle.get_points()
```

## Ellipse

The `Ellipse` class represents an ellipse in a 2D sketch. It is defined by a center point, a major axis length, and a minor axis length.

### Methods

- `get_focal_points()`: Get the focal points of the ellipse.
- `get_points() -> list[Point]`: Get a list of points along the ellipse.
- `rotate(angle: float, center: Point | None = None) -> "Ellipse"`: Rotate the ellipse around a specified center point.
- `translate(dx: float, dy: float) -> "Ellipse"`: Translate the ellipse by a specified distance.

### Example

```python
center = Point(sketch, 0, 0)
a = 2
b = 1
ellipse = Ellipse(center, a, b)
points = ellipse.get_points()
```

## Hexagon

The `Hexagon` class represents a regular hexagon in a 2D sketch. It is defined by a center point and a radius.

### Methods

- `get_points() -> list[Point]`: Get a list of points along the hexagon.

### Example

```python
center = Point(sketch, 0, 0)
radius = 1
hexagon = Hexagon(center, radius)
points = hexagon.get_points()
```

## Draw

The `Draw` class provides a simple interface for drawing points and lines in a 2D sketch.

### Methods

- `move_to(x: float, y: float)`: Move to an absolute position.
- `move(dx: float, dy: float)`: Move by a relative distance.
- `add_point()`: Add a point at the current position.
- `line_to(x: float, y: float)`: Draw a line to an absolute position.
- `line(dx: float, dy: float)`: Draw a line by a relative distance.
- `back_one_point()`: Move back to the previous point.
- `get_closed_polygon() -> Polygon`: Get a closed polygon from the drawn points.

### Example

```python
sketch = Sketch(plane)
draw = Draw(sketch)
draw.move_to(0, 0)
draw.line_to(1, 0)
draw.line_to(1, 1)
draw.line_to(0, 1)
draw.line_to(0, 0)
polygon = draw.get_closed_polygon()
```

## Line

The `Line` class represents a line in a 2D sketch. It is defined by two points.

### Methods

- `rotate(angle: float, center: Point | None = None) -> "Line"`: Rotate the line around a specified center point.
- `translate(dx: float, dy: float) -> "Line"`: Translate the line by a specified distance.
- `dx() -> float`: Get the change in x-coordinate between the two points.
- `dy() -> float`: Get the change in y-coordinate between the two points.
- `length() -> float`: Get the length of the line.
- `angle_to_other_line(line_b: "Line") -> float`: Get the angle between the line and another line.
- `distance_to_point(p1: Point, absolute: bool = True) -> float`: Get the distance from the line to a point.
- `line_equation() -> float`: Get the equation of the line in the form ax + by + c = 0.
- `closest_point_on_line(p0: Point) -> tuple[float, float]`: Get the closest point on the line to a given point.

### Example

```python
p1 = Point(sketch, 0, 0)
p2 = Point(sketch, 1, 1)
line = Line(p1, p2)
length = line.length()
angle = line.angle_to_other_line(Line(p1, Point(sketch, 1, 0)))
```

## Rectangle

The `Rectangle` class represents a rectangle in a 2D sketch. It is defined by four points.

### Methods

- `rotate(angle: float, center: Point | None = None) -> "Rectangle"`: Rotate the rectangle around a specified center point.
- `translate(dx: float, dy: float) -> "Rectangle"`: Translate the rectangle by a specified distance.
- `from_2_points(p1: Point, p3: Point) -> "Rectangle"`: Create a rectangle from two points assuming they are on the diagonal of the rectangle.
- `from_center_and_point(center: Point, p1: Point) -> "Rectangle"`: Create a rectangle from a center point and a point.
- `from_3_points(p1: Point, p2: Point, opposed: Point) -> "Rectangle"`: Create a rectangle using one side as [p1, p2] and the opposite side going through opposed.
- `from_center_and_sides(center: Point, lenght: float, width: float) -> "Rectangle"`: Create a rectangle from a center point and its length and width.

### Example

```python
p1 = Point(sketch, 0, 0)
p2 = Point(sketch, 1, 0)
p3 = Point(sketch, 1, 1)
p4 = Point(sketch, 0, 1)
rectangle = Rectangle(sketch, p1, p2, p3, p4)
rectangle_from_2_points = Rectangle.from_2_points(p1, p3)
rectangle_from_center_and_point = Rectangle.from_center_and_point(Point(sketch, 0.5, 0.5), p1)
rectangle_from_3_points = Rectangle.from_3_points(p1, p2, p3)
rectangle_from_center_and_sides = Rectangle.from_center_and_sides(Point(sketch, 0.5, 0.5), 1, 1)
```

## Square

The `Square` class represents a square in a 2D sketch. It is a subclass of the `Rectangle` class.

### Methods

- `from_center_and_side(center: Point, size: float) -> "Square"`: Create a square from a center point and a size.

### Example

```python
center = Point(sketch, 0.5, 0.5)
size = 1
square = Square.from_center_and_side(center, size)
```

## Sketch

The `Sketch` class represents a 2D sketch. It is defined by a plane.

### Methods

- `__init__(plane: PlaneFromFrame)`: Create a sketch with a specified plane.

### Example

```python
plane = PlaneFromFrame(frame)
sketch = Sketch(plane)
```

## Point

The `Point` class represents a point in a 2D sketch. It is defined by x and y coordinates.

### Methods

- `rotate(angle: float, center=None) -> "Point"`: Rotate the point around a specified center point.
- `translate(dx: float, dy: float) -> "Point"`: Translate the point by a specified distance.
- `distance_to_other_point(p2: "Point") -> float`: Get the distance between the point and another point.

### Example

```python
sketch = Sketch(plane)
point = Point(sketch, 0, 0)
rotated_point = point.rotate(math.pi / 2)
translated_point = point.translate(1, 1)
distance = point.distance_to_other_point(Point(sketch, 1, 1))
```

## PointWithTangent

The `PointWithTangent` class represents a point in a 2D sketch with a tangent angle. It is defined by a point and an angle.

### Methods

- `__init__(p: Point, angle: UnCastFloat)`: Create a point with a tangent angle.

### Example

```python
point = Point(sketch, 0, 0)
angle = 0
point_with_tangent = PointWithTangent(point, angle)
```

## Spline

The `Spline` class represents a spline in a 2D sketch. It is defined by a list of points with tangents.

### Methods

- `get_points(n_points: int = None) -> list[Point]`: Get a list of points along the spline.

### Example

```python
points_with_tangent = [PointWithTangent(Point(sketch, 0, 0), 0), PointWithTangent(Point(sketch, 1, 1), math.pi / 2)]
spline = Spline(points_with_tangent)
points = spline.get_points(10)
```

## TwoPointsSpline

The `TwoPointsSpline` class represents a spline in a 2D sketch defined by two points with tangents.

### Methods

- `get_xy_coeffs(smooth_factor: float | None = None) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]`: Get the coefficients of the cubic spline curves for the x and y coordinates.
- `get_points(n_points: int) -> list[Point]`: Get a list of points along the spline.

### Example

```python
p1 = PointWithTangent(Point(sketch, 0, 0), 0)
p2 = PointWithTangent(Point(sketch, 1, 1), math.pi / 2)
two_points_spline = TwoPointsSpline(p1, p2)
coeffs = two_points_spline.get_xy_coeffs()
points = two_points_spline.get_points(10)
```
