from foundation.types.component import Component
from foundation.types.assembly import Assembly
from foundation.types.serializable import serializable_nodes
from foundation.geometry.plane import PlaneFromFrame, PlaneFactory
import numpy as np
import sys

DAG_VERSION_FORMAT = "1.0"


# TODO clean this code to remove copy paste


def start_component() -> Component:
    """
    Start a component with an origin frame and 3 planes

    """
    # TODO remove the extra planes if they are not necessary and create on call.
    component = Component()
    # Add the 2 other frames
    o = component.head.get_frame()
    yz = o.get_rotated_frame_from_axis(o.get_y_axis(), np.pi / 2, "yz_f")
    xz = o.get_rotated_frame_from_axis(o.get_x_axis(), np.pi / 2, "xz_f")

    pxy = PlaneFromFrame(o, component.id + "_pxy")
    pyz = PlaneFromFrame(yz, component.id + "_pyz")
    pxz = PlaneFromFrame(xz, component.id + "_pxz")

    component.head.children.set_origin_planes([pxy, pyz, pxz])
    return component


def start_assembly() -> Assembly:
    """
    Start an assembly with an origin frame and 3 planes
    """
    # TODO remove the extra planes if they are not necessary and create on call.
    assembly = Assembly()
    o = assembly.head.get_frame()
    yz = o.get_rotated_frame_from_axis(o.get_y_axis(), np.pi / 2, "yz_f")
    xz = o.get_rotated_frame_from_axis(o.get_x_axis(), np.pi / 2, "xz_f")

    pxy = PlaneFromFrame(o, assembly.id + "_pxy")
    pyz = PlaneFromFrame(yz, assembly.id + "_pyz")
    pxz = PlaneFromFrame(xz, assembly.id + "_pxz")

    assembly.head.children.set_origin_planes([pxy, pyz, pxz])

    return assembly


def check_dict(d) -> None:
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


def format_dag(dag: dict):
    """Format the DAG to include extra information :
    - the serializable nodes
    - format version
    - root node id

    @param dag: the DAG to format ( see to_dag functions.)
    """
    # first of the key :

    return {
        "version": DAG_VERSION_FORMAT,
        "rootNodeId": next(iter(dag.keys())),
        "DAG": dag,
        "serializableNodes": serializable_nodes,
    }


def show(component: Component) -> None:
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
