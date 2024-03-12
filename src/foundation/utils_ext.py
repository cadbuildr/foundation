from foundation.types.component import Component
from foundation.types.serializable import serializable_nodes


try:
    import json
    import websocket
except ImportError:
    # mock the websocket module for environments where it is not available
    class websocket:
        @staticmethod
        def create_connection(*args, **kwargs):
            raise ImportError("websocket not available")


def showExt(component: Component) -> None:
    dic = component.to_dict(serializable_nodes=serializable_nodes)

    try:
        ws = websocket.create_connection("ws://127.0.0.1:3000")
        json_str = json.dumps(dic)
        ws.send(json_str)
    except Exception:
        print("WebSocket not available")
