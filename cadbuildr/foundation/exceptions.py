from __future__ import annotations

import numpy as np
from typing import Any, Optional


class FoundationException(Exception):
    """Base Exception class, returned when nothing more specific applies"""

    def __init__(self, message: Optional[str] = None) -> None:
        super(FoundationException, self).__init__(message)

        self.message = message

    def __str__(self) -> str:
        msg = self.message or "<empty message>"
        return msg

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={str(self)})"


class NotAUnitVectorException(FoundationException):
    """Raised when a vector is not a unit vector"""

    def __init__(self, vector: np.ndarray, name: str = "") -> None:
        super(NotAUnitVectorException, self).__init__(
            f"Vector: {name},  {vector} is not a unit vector it has a norm of {np.linalg.norm(vector)}"
        )


class GeometryException(FoundationException):
    """Raised when a geometry operation fails"""

    def __init__(self, message: str) -> None:
        super(GeometryException, self).__init__(message)


class InvalidParameterTypeException(FoundationException):
    def __init__(self, parameter_name: str, value: Any, expected_type: str) -> None:
        message = f"Invalid type for parameter '{parameter_name}': {value}. Expected type: {expected_type}."
        super().__init__(message)


class InvalidParameterValueException(FoundationException):
    def __init__(self, parameter_name: str, value: Any, msg: str) -> None:
        message = f"Invalid value for parameter '{parameter_name}': {value} - {msg}"
        super().__init__(message)


class TraceLessThanZeroException(GeometryException):
    def __init__(self, matrix: np.ndarray) -> None:
        message = f"Trace of the matrix is less than zero. Matrix: \n{matrix}"
        super().__init__(message)


class NaNInMatrixException(GeometryException):
    def __init__(self, matrix: np.ndarray) -> None:
        message = f"Matrix contains NaN values. Matrix: \n{matrix}"
        super().__init__(message)


class ZeroQuaternionNormException(GeometryException):
    def __init__(self) -> None:
        message = "The quaternion norm is zero, cannot normalize."
        super().__init__(message)


class ZeroLengthVectorException(GeometryException):
    def __init__(self, vector: np.ndarray, name: str = "") -> None:
        message = f"Vector: {name}, {vector} has a length of zero."
        super().__init__(message)


class InternalStateException(FoundationException):
    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(message)


class ElementsNotOnSameSketchException(FoundationException):
    def __init__(self, message: str) -> None:
        super().__init__(message)
