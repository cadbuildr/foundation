**Cheatsheet: Arc and Axis in Python**

**Arc Class**

The `Arc` class is used to create an arc object in a sketch. It has the following methods:

- `calculate_radius()`: Calculate the radius of the arc.
- `calculate_start_and_end_angles()`: Calculate the start and end angles of the arc.
- `get_points(n_points=20)`: Get a list of points along the arc.
- `rotate(angle, center=None)`: Rotate the arc by a given angle.
- `translate(dx, dy)`: Translate the arc by a given distance.
- `from_three_points(p1: Point, p2: Point, p3: Point)`: Create an arc from three points.
- `from_point_with_tangent_and_point(tangent: Line, p2: Point)`: Create an arc from a point, a tangent line, and another point.

**Axis Class**

The `Axis` class is used to create an axis object in a sketch. It has the following methods:

- `get_axis_rotation()`: Get the angle of rotation of the axis compared to the y-axis.
- `get_axis_translation()`: Get the distance from the axis to the origin.
- `get_axis_perpendicular_normed_vector()`: Get the normalized perpendicular vector of the axis.
- `transform_point(point)`: Transform a point by rotating and translating it according to the axis.
- `get_new_frame()`: Create a new frame with the axis as the origin.

**EllipseArc Class**

The `EllipseArc` class is used to create an elliptical arc object in a sketch. It has the following methods:

- `get_points(n_points=20)`: Get a list of points along the elliptical arc.
- `rotate(angle, center=None)`: Rotate the elliptical arc by a given angle.
- `translate(dx, dy)`: Translate the elliptical arc by a given distance.

**Point Class**

The `Point` class is used to create a point object in a sketch. It has the following methods:

- `rotate(angle, center=None)`: Rotate the point by a given angle.
- `translate(dx, dy)`: Translate the point by a given distance.

**Line Class**

The `Line` class is used to create a line object in a sketch. It has the following methods:

- `rotate(angle, center=None)`: Rotate the line by a given angle.
- `translate(dx, dy)`: Translate the line by a given distance.

**Sketch Class**

The `Sketch` class is used to create a sketch object. It has the following methods:

- `add_point(point)`: Add a point to the sketch.
- `add_line(line)`: Add a line to the sketch.
- `add_arc(arc)`: Add an arc to the sketch.
- `add_ellipse_arc(ellipse_arc)`: Add an elliptical arc to the sketch.
- `add_axis(axis)`: Add an axis to the sketch.

**Example Usage**

Here is an example of how to use the `Arc` and `Axis` classes to create an arc and an axis in a sketch:

```
# Create a sketch
sketch = Sketch()

# Create three points
p1 = Point(0, 0)
p2 = Point(1, 0)
p3 = Point(0.5, math.sqrt(3)/2)

# Add the points to the sketch
sketch.add_point(p1)
sketch.add_point(p2)
sketch.add_point(p3)

# Create an arc from the three points
arc = Arc.from_three_points(p1, p2, p3)

# Add the arc to the sketch
sketch.add_arc(arc)

# Create a line
line = Line(p1, p2)

# Add the line to the sketch
sketch.add_line(line)

# Create an axis from the line
axis = Axis(line)

# Add the axis to the sketch
sketch.add_axis(axis)
```

**Cheatsheet: Sketch Shapes**

**SketchShape**

The `SketchShape` class is a base class for all shapes in a sketch. It has the following methods:

- `get_plane()`: Get the plane of the sketch shape.
- `get_frame()`: Get the frame of the sketch shape.

**ClosedSketchShape**

The `ClosedSketchShape` class is a base class for all closed shapes in a sketch. It has the following methods:

- `get_points()`: Get the points of the shape.

**CustomClosedSketchShape**

The `CustomClosedSketchShape` class is used to create a custom closed shape from a list of primitives. It has the following methods:

- `get_points()`: Get the points of the shape.
- `rotate(angle, center=None)`: Rotate the shape by a given angle.
- `translate(dx, dy)`: Translate the shape by a given distance.

**Polygon**

The `Polygon` class is used to create a polygon shape from a list of lines. It has the following methods:

- `check_if_closed()`: Check if the shape is closed.
- `get_points()`: Get the points of the shape.
- `rotate(angle, center=None)`: Rotate the shape by a given angle.
- `translate(dx, dy)`: Translate the shape by a given distance.

**Circle**

The `Circle` class is used to create a circle shape. It has the following methods:

- `get_center()`: Get the center of the circle.
- `get_points()`: Get the points of the circle.
- `rotate(angle, center=None)`: Rotate the circle by a given angle.
- `translate(dx, dy)`: Translate the circle by a given distance.

**Ellipse**

The `Ellipse` class is used to create an ellipse shape. It has the following methods:

- `get_focal_points()`: Get the focal points of the ellipse.
- `get_points()`: Get the points of the ellipse.
- `rotate(angle, center=None)`: Rotate the ellipse by a given angle.
- `translate(dx, dy)`: Translate the ellipse by a given distance.

**Hexagon**

The `Hexagon` class is used to create a hexagon shape. It has the following methods:

- `get_points()`: Get the points of the hexagon.
- `rotate(angle, center=None)`: Rotate the hexagon by a given angle.
- `translate(dx, dy)`: Translate the hexagon by a given distance.

**Draw**

The `Draw` class is used to make it easier to draw points and lines in a sketch. It has the following methods:

- `move_to(x, y)`: Move to an absolute position.
- `move(dx, dy)`: Move relative to the current position.
- `add_point()`: Add a point at the current position.
- `line_to(x, y)`: Draw a line to an absolute position.
- `line(dx, dy)`: Draw a line relative to the current position.
- `back_one_point()`: Move back to the previous point.
- `get_closed_polygon()`: Get a closed polygon from the current list of points.

**Line**

The `Line` class is used to create a line in a sketch. It has the following methods:

- `rotate(angle, center=None)`: Rotate the line by a given angle.
- `translate(dx, dy)`: Translate the line by a given distance.
- `dx()`: Get the change in x-coordinate of the line.
- `dy()`: Get the change in y-coordinate of the line.
- `length()`: Get the length of the line.
- `angle_to_other_line(line_b)`: Get the angle between the line and another line.
- `distance_to_point(p1, absolute=True)`: Get the distance from the line to a point.
- `line_equation()`: Get the equation of the line.
- `closest_point_on_line(p0)`: Get the closest point on the line to a point.

**Point**

The `Point` class is used to create a point in a sketch. It has the following methods:

- `rotate(angle, center=None)`: Rotate the point by a given angle.
- `translate(dx, dy)`: Translate the point by a given distance.
- `distance_to_other_point(p2)`: Get the distance between the point and another point.

**Rectangle**

The `Rectangle` class is used to create a rectangle in a sketch. It has the following methods:

- `from_2_points(p1: Point, p3: Point)`: Create a rectangle from two points.
- `rotate(angle, center=None)`: Rotate the rectangle by a given angle.
- `translate(dx, dy)`: Translate the rectangle by a given distance.

**Square**

The `Square` class is used to create a square in a sketch. It has the following methods:

- `from_center_and_side(center, side)`: Create a square from a center point and a side length.
- `rotate(angle, center=None)`: Rotate the square by a given angle.
- `translate(dx, dy)`: Translate the square by a given distance.

**SketchOrigin**

The `SketchOrigin` class is used to create the origin point of a sketch. It inherits from the `Point` class.

**Sketch**

The `Sketch` class is used to create a sketch. It has the following methods:

- `__init__(self, plane)`: Initialize the sketch with a plane.

**Spline**

The `Spline` class is used to create a spline in a sketch. It has the following methods:

- `get_points(n_points=None)`: Get a list of points along the spline.

**TwoPointsSpline**

The `TwoPointsSpline` class is used to create a spline from two points with tangents. It has the following methods:

- `get_xy_coeffs(smooth_factor: float = None)`: Get the coefficients of the spline in the x and y directions.
- `get_points(n_points: int)`: Get a list of points along the spline.

**PointWithTangent**

The `PointWithTangent` class is used to create a point with a tangent in a sketch. It inherits from the `Point` class.

**RectangularPattern**

The `RectangularPattern` class is used to create a rectangular pattern of sketch components. It has the following methods:

- `run(sketch_component)`: Create a rectangular pattern of the given sketch component.

**CircularPattern**

The `CircularPattern` class is used to create a circular pattern of sketch components. It has the following methods:

- `run(sketch_component)`: Create a circular pattern of the given sketch component.

**Usage Examples**

Here are some examples of how to use the classes in this cheatsheet:

- To create a circle with a center point at (0, 0) and a radius of 1:

```
center = Point(0, 0)
circle = Circle(center, 1)
```

- To create a rectangle with two points at (0, 0) and (2, 1):

```
p1 = Point(0, 0)
p3 = Point(2, 1)
rectangle = Rectangle.from_2_points(p1, p3)
```

- To create a square with a center point at (0, 0) and a side length of 2:

```
center = Point(0, 0)
square = Square.from_center_and_side(center, 2)
```

- To create a spline from two points with tangents:

```
p1 = PointWithTangent(Point(0, 0), math.pi/4)
p2 = PointWithTangent(Point(1, 1), math.pi/2)
spline = TwoPointsSpline(p1, p2)
points = spline.get_points(10)
```

- To create a rectangular pattern of circles with 3 rows and 4 columns:

```
circle = Circle(Point(0, 0), 1)
pattern = RectangularPattern(3, 4, 3, 4)
circles = pattern.run(circle)
```

- To create a circular pattern of squares with 6 instances:

```
center = Point(0, 0)
square = Square.from_center_and_side(center, 1)
pattern = CircularPattern(center, 6)
squares = pattern.run(square)
```
