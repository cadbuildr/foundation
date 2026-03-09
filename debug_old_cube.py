import json
from cadbuildr.foundation import Part, Sketch, Point, Line, Polygon, Extrusion
from cadbuildr.foundation.utils import show_dag

def get_cube(size=1):
    cube = Part()
    # Operation 1
    s = Sketch(cube.xy())
    p1 = Point(s, 0, 0)
    p2 = Point(s, size, 0)
    p3 = Point(s, size, size)
    p4 = Point(s, 0, size)

    l1 = Line(p1, p2)
    l2 = Line(p2, p3)
    l3 = Line(p3, p4)
    l4 = Line(p4, p1)
    square = Polygon([l1, l2, l3, l4])

    e = Extrusion(square, size)
    cube.add_operation(e)
    return cube

print("Generating DAG from old foundation...")
try:
    cube = get_cube()
    dag = show_dag(cube)
    print(json.dumps(dag, indent=2))
except Exception as e:
    print(f"Execution failed: {e}")
    import traceback
    traceback.print_exc()
