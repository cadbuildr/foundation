from foundation.types.node import Node, Orphan
from foundation.types.node_interface import NodeInterface
from typing import Union


class Parameter(NodeInterface):
    """a Parameter has one value defining the parameter"""

    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = value


class FloatParameter(Parameter, Orphan):
    # parent_types = [Node] How to deal with a node with many different types of parents
    def __init__(self, value):
        Parameter.__init__(self, value)
        Orphan.__init__(self)
        self.params = {"value": value}

        # print("FloatParameter created", type(self), " with parents ", self.parents)


class IntParameter(Parameter, Orphan):
    # parent_types = [Node] How to deal with a node with many different types of parents
    def __init__(self, value):
        Parameter.__init__(self, value)
        Orphan.__init__(self)
        self.params = {"value": value}


class BoolParameter(Parameter, Orphan):
    # parent_types = [Node] How to deal with a node with many different types of parents
    def __init__(self, value):
        Parameter.__init__(self, value)
        Orphan.__init__(self)
        self.params = {"value": value}


class StringParameter(Parameter, Orphan):
    # parent_types = [Node] How to deal with a node with many different types of parents
    def __init__(self, value):
        Parameter.__init__(self, value)
        Orphan.__init__(self)
        self.params = {"value": value}


def cast_to_float_parameter(value):
    if isinstance(value, float):
        p = FloatParameter(value)
        return p
    if isinstance(value, int):
        return FloatParameter(float(value))
    elif isinstance(value, Parameter):
        return value
    else:
        raise TypeError("value must be a float or a Parameter")


def cast_to_int_parameter(value):
    if isinstance(value, int):
        return IntParameter(value)
    elif isinstance(value, Parameter):
        return value
    else:
        raise TypeError("value must be an int or a Parameter")


def cast_to_bool_parameter(value):
    if isinstance(value, bool):
        return BoolParameter(value)
    elif isinstance(value, Parameter):
        return value
    else:
        raise TypeError("value must be a bool or a Parameter")


def cast_to_string_parameter(value):
    if isinstance(value, str):
        return StringParameter(value)
    elif isinstance(value, Parameter):
        return value
    else:
        raise TypeError("value must be a str or a Parameter")


UnCastFloat = Union[float, FloatParameter]
UnCastInt = Union[int, IntParameter]
UnCastBool = Union[bool, BoolParameter]
UnCastString = Union[str, StringParameter]
