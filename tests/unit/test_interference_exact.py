"""check_interference(exact=True): real solids, not bounding boxes.

Requested by the Foundation library projects review: two meshed gears whose
rectangular teeth interpenetrated (~1.5 mm³) were reported clean, because the
check compared bounding volumes and treated jointed pairs as intended contact.

Meshes come from a test mesher (manifold3d prisms of the same outlines the
parts are extruded from), so these tests need no kernel.
"""

import math

import numpy as np
import pytest

m3d = pytest.importorskip("manifold3d")

from cadbuildr.foundation import Assembly, Extrusion, Part, Polygon, Sketch
from cadbuildr.foundation import make_anchor
from cadbuildr.foundation.gen.models import BoolParameter, RigidJoint
from cadbuildr.foundation.interference import solid_overlap

_MESH_ATTR = "_test_outline"


def prism(name, outline, height=10.0):
    """A Part extruded from ``outline`` (2D points) by ``height``; the test
    mesher meshes the same outline."""
    part = Part()
    part.name.value = name
    sketch = Sketch(part.xy())
    part.add_operation(Extrusion(Polygon.from_points(sketch, outline), height))
    object.__setattr__(part, _MESH_ATTR, (outline, height))
    return part


def mesher(root):
    source = getattr(root, "_source_component", None) or root
    solid = getattr(source, "_test_solid", None)
    if solid is not None:
        mesh = solid.to_mesh()
        return np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts)
    outline, height = getattr(source, _MESH_ATTR)
    solid = m3d.CrossSection([np.asarray(outline, dtype=float)]).extrude(height)
    mesh = solid.to_mesh()
    return np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts)


def square(cx=0.0, cy=0.0, s=10.0):
    h = s / 2
    return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]


def gear(n_teeth=12, r_root=20.0, r_tip=24.0, phase=0.0):
    """Rectangular-tooth gear outline (CCW)."""
    pts = []
    step = 2 * math.pi / n_teeth
    for k in range(n_teeth):
        a = phase + k * step
        for ang, r in (
            (a, r_root),
            (a + 0.2 * step, r_root),
            (a + 0.2 * step, r_tip),
            (a + 0.6 * step, r_tip),
            (a + 0.6 * step, r_root),
        ):
            pts.append((r * math.cos(ang), r * math.sin(ang)))
    return pts


def jointed_pair(offset_x, rot_deg=None):
    """Two 10 mm cubes, B rigidly jointed to A with its centre ``offset_x`` mm away."""
    a, b = prism("a", square()), prism("b", square())
    a.add_anchor(make_anchor("mate", [offset_x / 2, 0.0, 0.0]))
    b.add_anchor(make_anchor("mate", [-offset_x / 2, 0.0, 0.0]))
    asm = Assembly()
    asm.add_component(a, at=[3.0, -2.0, 1.0], rot_deg=rot_deg)
    asm.add_joint(
        RigidJoint(
            parent_anchor=a.anchor("mate"),
            child_anchor=b.anchor("mate"),
            flip=BoolParameter(value=False),
        )
    )
    return asm, a, b


def test_jointed_overlap_is_reported_in_exact_mode_only():
    asm, a, b = jointed_pair(9.0)  # 1 mm interpenetration
    assert asm.check_interference() == []  # bbox mode: joint = intended contact
    found = asm.check_interference(exact=True, mesher=mesher)
    assert len(found) == 1
    hit = found[0]
    assert hit.status == "overlap"
    assert hit.volume == pytest.approx(100.0, rel=1e-3)  # 1 x 10 x 10
    assert hit.depth == pytest.approx(1.0, rel=1e-3)


def test_depth_is_measured_in_the_part_frame():
    asm, _, _ = jointed_pair(9.0, rot_deg=[0, 0, 30])
    hit = asm.check_interference(exact=True, mesher=mesher)[0]
    assert hit.volume == pytest.approx(100.0, rel=1e-3)
    assert hit.depth == pytest.approx(1.0, rel=1e-3)


def test_touching_is_not_an_overlap():
    asm, _, _ = jointed_pair(10.0)
    assert asm.check_interference(exact=True, mesher=mesher) == []


def test_allow_exempts_a_pair():
    asm, a, b = jointed_pair(9.0)
    assert asm.check_interference(exact=True, mesher=mesher, allow=[(a, b)]) == []


def test_volume_tol():
    asm, _, _ = jointed_pair(9.95)  # 0.05 x 10 x 10 = 5 mm³
    assert len(asm.check_interference(exact=True, mesher=mesher)) == 1
    assert asm.check_interference(exact=True, mesher=mesher, volume_tol=6.0) == []


def test_depth_tol_ignores_sheet_thin_overlaps():
    asm, _, _ = jointed_pair(9.99)  # 0.01 mm deep: below DEFAULT_DEPTH_TOL
    assert asm.check_interference(exact=True, mesher=mesher) == []
    assert len(asm.check_interference(exact=True, mesher=mesher, depth_tol=0.0)) == 1


def shaft_in_bore(shaft_r, bore_r=4.0):
    """A 20 mm cube with a bore, and a shaft through it — tessellated with
    different segment counts, as two parts meshed separately would be."""
    block = prism("block", square(s=20.0), height=20.0)
    shaft = prism("shaft", square(s=2 * shaft_r), height=30.0)
    hole = m3d.Manifold.cylinder(40.0, bore_r, bore_r, circular_segments=40).translate(
        [0, 0, -10]
    )
    object.__setattr__(
        block,
        "_test_solid",
        m3d.Manifold.cube([20.0, 20.0, 20.0], center=True).translate([0, 0, 10]) - hole,
    )
    object.__setattr__(
        shaft,
        "_test_solid",
        m3d.Manifold.cylinder(30.0, shaft_r, shaft_r, circular_segments=48).translate(
            [0, 0, -5]
        ),
    )
    asm = Assembly()
    asm.add_component(block)
    asm.add_component(shaft)
    return asm


def test_line_to_line_fit_is_clean():
    asm = shaft_in_bore(4.0)
    # Different tessellations of the same circle cross: a sliver is there...
    slivers = asm.check_interference(exact=True, mesher=mesher, depth_tol=0.0)
    assert len(slivers) == 1 and slivers[0].volume < 5.0
    # ...but it is a sheet thinner than the chord error, not an interference.
    assert asm.check_interference(exact=True, mesher=mesher) == []


def test_interference_fit_is_reported():
    hits = shaft_in_bore(4.1).check_interference(
        exact=True, mesher=mesher
    )  # 0.1 mm press fit
    assert len(hits) == 1 and hits[0].volume > 10.0


def test_concave_parts_with_overlapping_boxes_are_clean():
    # Two interlocking L shapes: bounding boxes overlap, solids don't.
    l1 = prism("l1", [(0, 0), (20, 0), (20, 4), (4, 4), (4, 20), (0, 20)])
    l2 = prism("l2", [(6, 6), (26, 6), (26, 26), (22, 26), (22, 10), (6, 10)])
    asm = Assembly()
    asm.add_component(l1)
    asm.add_component(l2)
    assert [i.status for i in asm.check_interference()] == [
        "overlap"
    ]  # bbox false positive
    assert asm.check_interference(exact=True, mesher=mesher) == []


def test_mis_phased_gears_overlap_phased_gears_dont():
    # Tips reach 1 mm past the other gear's TIP circle (well short of its root):
    # a tooth in the other's gap is clean, tooth on tooth interpenetrates.
    centre = 24.0 + 24.0 - 1.0
    step = 2 * math.pi / 12
    # g1's teeth span [k + 0.2, k + 0.6] x step; at the contact line (angle 0)
    # g1 has a gap centred at -0.1 step and tooth k=0 centred at +0.4 step.
    # g2 faces -X (angle pi); its tooth k=0 is centred at phase + 0.4 step.
    # Mirror across the contact line: angle a on g1 meets pi - a on g2.

    def pair(g1_angle_to_meet):
        phase_b = math.pi - g1_angle_to_meet - 0.4 * step
        g1 = prism("g1", gear())
        g2 = prism("g2", gear(phase=phase_b))
        asm = Assembly()
        asm.add_component(g1)
        asm.add_component(g2, at=[centre, 0.0, 0.0])
        return asm

    meshed = pair(-0.1 * step)  # g2 tooth into g1's gap
    clashing = pair(0.4 * step)  # g2 tooth onto g1's tooth
    assert meshed.check_interference(exact=True, mesher=mesher) == []
    clash = clashing.check_interference(exact=True, mesher=mesher)
    assert len(clash) == 1 and clash[0].volume > 1.0


def test_unmeshable_part_is_unknown():
    asm, _, _ = jointed_pair(9.0)

    def broken(root):
        raise RuntimeError("kernel unavailable")

    found = asm.check_interference(exact=True, mesher=broken)
    assert [i.status for i in found] == ["unknown"]
    assert "kernel unavailable" in found[0].reason
    assert (
        asm.check_interference(exact=True, mesher=broken, include_unknown=False) == []
    )


def test_solid_overlap_helper():
    a = mesher_for(square())
    b = mesher_for(square(cx=9.0))
    volume, depth = solid_overlap(a, b)
    assert volume == pytest.approx(100.0, rel=1e-3)
    assert depth == pytest.approx(1.0, rel=1e-3)


def mesher_for(outline, height=10.0):
    mesh = (
        m3d.CrossSection([np.asarray(outline, dtype=float)]).extrude(height).to_mesh()
    )
    return np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts)
