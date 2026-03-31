from cadbuildr.foundation.gen.models import Part, Sketch, Square, Extrusion
from cadbuildr.foundation.dag_utils import pydantic_to_dag, show_dag
from cadbuildr.foundation.foundation_hooks import setup_foundation_hooks


def test_cube():
    class Cube(Part):
        def __init__(self, size=30):
            self.size = size
            # Create a Sketch from XY Plane
            s = Sketch(self.xy())
            square = Square.from_center_and_side(s.origin, self.size)
            e = Extrusion(square, self.size)
            self.add_operation(e)
            self.paint("pink")

    cube = Cube()
    memo = {}
    type_registry = {}
    hooks = setup_foundation_hooks()
    root_hash = pydantic_to_dag(
        cube, memo=memo, type_registry=type_registry, hooks=hooks
    )

    # Validate that the dag is correct
    # Find nodes in memo
    sketch_nodes = [
        node for node in memo.values() if node["type"] == type_registry["Sketch"]
    ]
    extrusion_nodes = [
        node for node in memo.values() if node["type"] == type_registry["Extrusion"]
    ]

    assert (
        len(sketch_nodes) >= 1
    ), f"Expected at least 1 Sketch node, found {len(sketch_nodes)}"
    assert (
        len(extrusion_nodes) >= 1
    ), f"Expected at least 1 Extrusion node, found {len(extrusion_nodes)}"

    sketch_node = sketch_nodes[0]
    extrusion_node = extrusion_nodes[0]

    # Check sketch elements
    # Sketch should have elements (Square/Polygon)
    assert "elements" in sketch_node["deps"]
    assert len(sketch_node["deps"]["elements"]) > 0

    # Check extrusion shape
    assert "shape" in extrusion_node["deps"]

    extrusion_node = extrusion_nodes[0]

    # Check that 'sketch' is present in deps
    assert (
        "sketch" in extrusion_node["deps"]
    ), "Extrusion node missing 'sketch' dependency"
    print("DAG validation passed!")

    print(f"Total nodes: {len(memo)}")


def test_cube_planes_registered_in_part():
    """CRITICAL: Planes must be registered in Part node for frontend to find them.

    Catches bug: TypeError: Cannot read properties of undefined (reading 'getPlane')
    at ExtrusionReplicad.toReplicadSingle (Extrusion.tsx:56:27)
    """
    cube = Part()
    s = Sketch(cube.xy())
    square = Square.from_center_and_side(s.origin, 30)
    e = Extrusion(square, 30)
    cube.add_operation(e)

    dag = show_dag(cube)
    root_node = dag["DAG"][dag["rootNodeId"]]
    plane_ids = [
        nid
        for nid, n in dag["DAG"].items()
        if n["type"] == dag["serializableNodes"]["Plane"]
    ]

    registered_planes = root_node.get("deps", {}).get("planes", []) + root_node.get(
        "params", {}
    ).get("planes", [])

    assert len(plane_ids) > 0, "No planes found in DAG"
    assert plane_ids[0] in registered_planes, (
        f"Plane {plane_ids[0]} not registered! "
        f"deps.planes={root_node.get('deps', {}).get('planes', [])} "
        f"This causes: TypeError: Cannot read properties of undefined (reading 'getPlane')"
    )


def test_no_frame_plane_name_collision():
    """CRITICAL: Frame and Plane names must not collide.

    Catches bug: Infinite loop in rc-tree UI component when plane name equals its frame name.
    The construction tree builder adds planes as children of their frames by name lookup.
    If a plane has the same name as its frame, it becomes its own child → infinite loop.

    Error manifests as:
    - Infinite loop in processNode() in rc-tree/es/utils/treeUtil.js
    - Stack overflow with repeated getPosition() calls
    """
    # Test all standard planes
    cube = Part()

    # Get planes for all directions
    planes_to_test = [
        ("xy", cube.xy()),
        ("yx", cube.yx()),
        ("xz", cube.xz()),
        ("zx", cube.zx()),
        ("yz", cube.yz()),
        ("zy", cube.zy()),
    ]

    dag = show_dag(cube)

    # Collect all frame names
    frame_type = dag["serializableNodes"]["Frame"]
    frame_names = set()
    for node_id, node in dag["DAG"].items():
        if node["type"] == frame_type:
            name_id = node.get("deps", {}).get("name")
            if name_id and name_id in dag["DAG"]:
                name = dag["DAG"][name_id]["params"]["value"]
                frame_names.add(name)

    # Collect all plane names
    plane_type = dag["serializableNodes"]["Plane"]
    plane_names = set()
    for node_id, node in dag["DAG"].items():
        if node["type"] == plane_type:
            name_id = node.get("deps", {}).get("name")
            if name_id and name_id in dag["DAG"]:
                name = dag["DAG"][name_id]["params"]["value"]
                plane_names.add(name)

    # Check for collision
    collision = frame_names & plane_names

    assert not collision, (
        f"Frame and Plane name collision detected: {collision}\n"
        f"Frame names: {sorted(frame_names)}\n"
        f"Plane names: {sorted(plane_names)}\n"
        f"This causes infinite loop in construction tree UI:\n"
        f"  - Plane references its frame by name\n"
        f"  - Tree builder adds plane as child of frame (by name lookup)\n"
        f"  - If names match, plane becomes child of itself\n"
        f"  - rc-tree processNode() loops forever traversing children\n"
        f"Fix: Ensure frame names have suffix like '_frame' to distinguish from plane names"
    )
