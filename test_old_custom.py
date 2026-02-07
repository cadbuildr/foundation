from cadbuildr.foundation import (
    Part, Sketch, Point, Line, Arc, CustomClosedShape
)
from cadbuildr.foundation.utils import show_dag
import json

# custom closed sketch shape with one arc
comp = Part()
s = Sketch(comp.xy())

# create a square
p1 = Point(s, 0, 0)
p2 = Point(s, 100, 0)
p3 = Point(s, 100, 10)
p4 = Point(s, 80, 15)
p5 = Point(s, 0, 10)

l1 = Line(p1, p2)
l2 = Line(p2, p3)
a1 = Arc(p3, p4, p5)
l3 = Line(p5, p1)

# create a custom closed sketch shape
custom = CustomClosedShape([l1, l2, a1, l3])

dag = show_dag(s)

# Find CustomClosedShape node
for node_id, node_data in dag['DAG'].items():
    if dag['serializableNodes'].get('CustomClosedShape') == node_data.get('type'):
        print(f'OLD FOUNDATION - CustomClosedShape node {node_id}:')
        print(json.dumps(node_data, indent=2))
        break
