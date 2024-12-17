import json
from .examples import examples, get_cube
from cadbuildr.foundation.types.serializable import serializable_nodes


def test_serialize_cube():
    cube = get_cube()
    ser_cube = cube.to_dag()
    print(json.dumps(ser_cube))


def test_serialize_all_examples():
    for ex, func in examples.items():
        print(f"Serializing {ex}")
        part = func()
        ser_part = part.to_dag()
        # print(json.dumps(ser_example))
