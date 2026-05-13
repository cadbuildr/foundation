"""Unit tests for Text."""

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    Text,
    Extrusion,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_text_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            txt = Text(
                sketch=s,
                text="Hi",
                size=10,
                font_url="https://example.com/font.ttf",
            )
            self.add_operation(Extrusion(txt, end=2))

    dag = show_dag(_Part())
    assert "Text" in dag["serializableNodes"]
    txts = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Text"]]
    assert len(txts) == 1
