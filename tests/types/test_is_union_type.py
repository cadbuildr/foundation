import pytest
from typing import Union, List
from cadbuildr.foundation.types.node_children import is_union_type

# Assuming the is_union_type function is defined here as provided earlier


def test_is_union_type_with_typing_union():
    assert is_union_type(
        Union[int, str]
    ), "Union[int, str] should be recognized as a union type"


def test_is_union_type_with_pep_604_union():
    assert is_union_type(int | str), "int | str should be recognized as a union type"


def test_is_union_type_with_single_type():
    assert not is_union_type(
        int
    ), "Single type int should not be recognized as a union type"


def test_is_union_type_with_generic_list():
    assert not is_union_type(
        List[int]
    ), "List[int] should not be recognized as a union type"


def test_is_union_type_with_complex_union():
    assert is_union_type(
        Union[int, List[str]]
    ), "Union[int, List[str]] should be recognized as a union type"


def test_is_union_type_with_nested_pep_604_union():
    assert is_union_type(
        int | List[str]
    ), "int | List[str] should be recognized as a union type"


def test_is_union_type_with_none_type_union():
    assert is_union_type(
        type(None) | int
    ), "type(None) | int should be recognized as a union type"


def test_is_union_type_with_optional_typing_union():
    assert is_union_type(
        Union[int, None]
    ), "Union[int, None] should be recognized as a union type"


def test_is_union_type_with_direct_none_union():
    assert is_union_type(int | None), "int | None should be recognized as a union type"
