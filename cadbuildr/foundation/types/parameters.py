from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.node_interface import NodeInterface
from cadbuildr.foundation.types.node_children import NodeChildren


# Parameters don't have children.
class ParameterChildren(NodeChildren):
    pass


class Parameter(NodeInterface):
    """a Parameter has one value defining the parameter"""

    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = value

    def __repr__(self):
        return f"{self.__class__.__name__}({self.value})"


class FloatParameter(Parameter, Node):
    """Store a float value as a parameter"""

    def __init__(self, value: float):
        Parameter.__init__(self, value)
        Node.__init__(self)
        self.params = {"value": value}


class IntParameter(Parameter, Node):
    """Store an int value as a parameter"""

    def __init__(self, value: int):
        Parameter.__init__(self, value)
        Node.__init__(self)
        self.params = {"value": value}


class BoolParameter(Parameter, Node):
    """Store a boolean value as a parameter"""

    def __init__(self, value: bool):
        Parameter.__init__(self, value)
        Node.__init__(self)
        self.params = {"value": value}


class StringParameter(Parameter, Node):
    """Store a string value as a parameter"""

    def __init__(self, value: str):
        Parameter.__init__(self, value)
        Node.__init__(self)
        self.params = {"value": value}


def cast_to_float_parameter(value: int | float | FloatParameter) -> FloatParameter:
    if isinstance(value, float):
        p = FloatParameter(value)
        return p
    if isinstance(value, int):
        p = FloatParameter(float(value))
        return p
    elif isinstance(value, FloatParameter):
        return value
    else:
        raise TypeError("value must be a float or a Parameter")


def cast_to_int_parameter(value: int | IntParameter) -> IntParameter:
    if isinstance(value, int):
        return IntParameter(value)
    elif isinstance(value, IntParameter):
        return value
    else:
        raise TypeError("value must be an int or a Parameter")


def cast_to_bool_parameter(value: bool | BoolParameter) -> BoolParameter:
    if isinstance(value, bool):
        return BoolParameter(value)
    elif isinstance(value, BoolParameter):
        return value
    else:
        raise TypeError("value must be a bool or a Parameter")


def cast_to_string_parameter(value: str | StringParameter) -> StringParameter:
    if isinstance(value, str):
        return StringParameter(value)
    elif isinstance(value, StringParameter):
        return value
    else:
        raise TypeError("value must be a str or a Parameter")


UnCastFloat = float | FloatParameter
UnCastInt = int | IntParameter
UnCastBool = bool | BoolParameter
UnCastString = str | StringParameter
