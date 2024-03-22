from foundation.types.component import Component
from foundation.types.serializable import serializable_nodes


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


def showExt(component: Component) -> None:
    dic = component.to_dag()

    try:
        ws = websocket.create_connection("ws://127.0.0.1:3000")
        json_str = json.dumps(dic)
        ws.send(json_str)
    except Exception:
        print("WebSocket not available")
