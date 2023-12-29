from foundation.geometry.frame import OriginFrame
from foundation.types.component import Component
from foundation.types.assembly import Assembly
from foundation.geometry.plane import PlaneFromFrame, PlaneFactory
from typing import Union
import numpy as np
import sys

# TODO clean this code to remove copy paste


def start_component():
    component = Component()
    # Add the 2 other frames
    o = component.head.origin_frame
    xz = o.get_rotated_frame_from_axis(o.get_x_axis(), np.pi / 2, "xz_f")
    yz = o.get_rotated_frame_from_axis(o.get_y_axis(), np.pi / 2, "yz_f")

    pxy = PlaneFromFrame(component.head, o, component.id + "_pxy")
    pxz = PlaneFromFrame(component.head, xz, component.id + "_pxz")
    pyz = PlaneFromFrame(component.head, yz, component.id + "_pyz")

    component.pf = PlaneFactory()

    # TODO do we need this ?
    # build_tree.add_construction_element("xy_plane", xy)
    # build_tree.add_construction_element("xz_plane", xz)
    # build_tree.add_construction_element("yz_plane", yz)

    component.set_origin_planes([pxy, pxz, pyz])
    return component


def start_assembly():
    assembly = Assembly()
    o = assembly.head.origin_frame
    xz = o.get_rotated_frame_from_axis(o.get_x_axis(), np.pi / 2, "xz_f")
    yz = o.get_rotated_frame_from_axis(o.get_y_axis(), np.pi / 2, "yz_f")

    pxy = PlaneFromFrame(assembly.head, o, assembly.id + "_pxy")
    pxz = PlaneFromFrame(assembly.head, xz, assembly.id + "_pxz")
    pyz = PlaneFromFrame(assembly.head, yz, assembly.id + "_pyz")

    assembly.pf = PlaneFactory()

    # TODO do we need this ?
    # build_tree.add_construction_element("xy_plane", xy)
    # build_tree.add_construction_element("xz_plane", xz)
    # build_tree.add_construction_element("yz_plane", yz)

    assembly.set_origin_planes([pxy, pxz, pyz])

    return assembly


def check_dict(d):
    """Useful debug tool on dict to see if any value is nan"""
    for k, v in d.items():
        if isinstance(v, dict):
            check_dict(v)
        elif isinstance(v, list):
            for i in v:
                if isinstance(i, dict):
                    check_dict(i)
                elif isinstance(i, float):
                    assert not np.isnan(i)
        elif isinstance(v, float):
            assert not np.isnan(v)
        else:
            if isinstance(v, float):
                if np.isnan(v):
                    print(k, v)


def show(component):
    """Function that is actually mocked on
    server and browser, but not on the tests"""
    if sys.platform == "emscripten":
        pass  # is getting mocked
    else:
        pass


def show_with_params(comp_class, params):
    """Function that is actually mocked on
    server and browser, but not on the tests"""
    pass


def show_from_params(params):
    pass
