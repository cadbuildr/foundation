from foundation.utils import format_dag
from typing import Union
from foundation import Sketch, Assembly, Part, Frame, Plane

DISPLAY_TYPE = Union[Sketch, Assembly, Part, Frame, Plane]

try:
    import json
    import websocket
except ImportError:
    # mock the websocket module for environments where it is not available
    from types import ModuleType

    class MockWebSocket(ModuleType):
        @staticmethod
        def create_connection(*args, **kwargs):
            raise ImportError("websocket not available")

    websocket = MockWebSocket("websocket")


def showExt(
    component: DISPLAY_TYPE,
) -> None:

    dic = component.to_dag()
    dic = format_dag(dic)
    try:
        ws = websocket.create_connection("ws://127.0.0.1:3000")
        json_str = json.dumps(dic)
        ws.send(json_str)
    except Exception:
        print("WebSocket not available")
