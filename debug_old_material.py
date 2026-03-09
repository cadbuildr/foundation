from cadbuildr.foundation import Part, Sketch, Square, Extrusion, show

class PaintedCube(Part):
    def __init__(self):
        s = Sketch(self.xy())
        square = Square.from_center_and_side(s.origin, 10)
        e = Extrusion(square, 10)
        self.add_operation(e)
        self.paint("red", 0.5)

c = PaintedCube()
# The old foundation might not have show_dag exposed directly, 
# but show() usually prints or returns something. 
# Let's try to inspect the internal DAG generation if possible.
# Or just run it and see if it prints the DAG hash/content.

# Assuming show() sends to broker, but we want to see the DAG.
# Let's look at how show works in old foundation.
from cadbuildr.foundation.utils import show_dag
import json
print(json.dumps(show_dag(c), indent=2))
