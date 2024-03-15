from foundation.types.node import Orphan
from foundation.types.node_interface import NodeInterface


class Parameter(NodeInterface):
    """a Parameter has one value defining the parameter"""

    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = value


class FloatParameter(Parameter, Orphan):
    """Store a float value as a parameter"""

    def __init__(self, value: float):
        Parameter.__init__(self, value)
        Orphan.__init__(self)
        self.params = {"value": value}


class IntParameter(Parameter, Orphan):
    """Store an int value as a parameter"""

    def __init__(self, value: int):
        Parameter.__init__(self, value)
        Orphan.__init__(self)
        self.params = {"value": value}


class BoolParameter(Parameter, Orphan):
    """Store a boolean value as a parameter"""

    def __init__(self, value: bool):
        Parameter.__init__(self, value)
        Orphan.__init__(self)
        self.params = {"value": value}


class StringParameter(Parameter, Orphan):
    """Store a string value as a parameter"""

    def __init__(self, value: str):
        Parameter.__init__(self, value)
        Orphan.__init__(self)
        self.params = {"value": value}


def cast_to_float_parameter(value):
    if isinstance(value, float):
        p = FloatParameter(value)
        return p
    if isinstance(value, int):
        p = FloatParameter(float(value))
        return p
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


UnCastFloat = float | FloatParameter
UnCastInt = int | IntParameter
UnCastBool = bool | BoolParameter
UnCastString = str | StringParameter
