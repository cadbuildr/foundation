Please generate a CheatSheet for documenting Python classes from a library. The CheatSheet is titled Operation Geometry Classes.

Instructions:
1. Title:Operation Geometry Classes
2. Objective: To document all classes in the library
3. Format: Markdown (.md)
4. Key Points:
   - Each method should be explained with a brief description.
   - Ensure all types of arguments and return values are clearly displayed.
   - I want tests for all classes.
5. Language: English

Class GridXY:
```python
class GridXY:
    """Useful wrapper around a class that has a .get_assy method to generate a grid of them"""

    def __init__(
        self, assy_factory, n_x: int, n_y: int, spacing_x: float, spacing_y: float
    ):
        self.assy_factory = assy_factory
        self.n_x = n_x
        self.n_y = n_y
        self.spacing_x = spacing_x
        self.spacing_y = spacing_y

    def get_assy(self) -> Assembly:
        self.assembly = start_assembly()
        for i in range(self.n_x):
            for j in range(self.n_y):
                tf_helper = TFHelper()
                tf_helper.translate_x(i * self.spacing_x)
                tf_helper.translate_y(j * self.spacing_y)
                self.assembly.add_component(
                    self.assy_factory.get_assy(), tf_helper.get_tf()
                )
        return self.assembly
```

Class Extrusion:
```python
class Extrusion(Operation, Node):
    children_class = ExtrusionChildren

    def __init__(
        self,
        shape: ClosedSketchShapeTypes,
        end: UnCastFloat = 1.0,
        start: UnCastFloat = 0.0,
        cut: UnCastBool = False,
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_shape(shape)
        self.children.set_sketch(shape.sketch)
        self.children.set_start(cast_to_float_parameter(start))
        self.children.set_end(cast_to_float_parameter(end))
        self.children.set_cut(cast_to_bool_parameter(cut))

        # shortcuts
        self.shape = self.children.shape
        self.sketch = self.children.sketch
        self.start = self.children.start
        self.end = self.children.end
        self.cut = self.children.cut

        self.params = {
            # "n_shape": shape.id,
            # "n_start": self.start.id,
            # "n_end": self.end.id,
            # "n_cut": self.cut.id,
            # "n_sketch": shape.sketch.id,
        }

    def get_frame(self):
        # parent 0 is SketchElement
        return self.sketch.frame
```

Class Lathe:
```python
class Lathe(Operation, Node):
    """A Lathe operation is a closed shape,
    that is revolved around an axis, to make as solid"""

    children_class = LatheChildren

    def __init__(
        self, shape: ClosedSketchShapeTypes, axis: Axis, cut: UnCastBool = False
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])

        self.children.set_cut(cast_to_bool_parameter(cut))
        self.children.set_shape(shape)
        self.children.set_axis(axis)
        self.children.set_sketch(shape.sketch)

        # shortcuts
        self.axis = self.children.axis
        self.shape = self.children.shape
        self.cut = self.children.cut

        self.params = {}

    def get_frame(self) -> Frame:
        # parent 0 is SketchElement
        return self.shape.get_frame()
```

