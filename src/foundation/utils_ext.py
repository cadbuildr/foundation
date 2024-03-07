from foundation.types.component import Component
from foundation.types.serializable import serializable_nodes


try:
    import json
    import websocket
except ImportError:
    pass


def showExt(component: Component) -> None:
    dic = component.to_dict(serializable_nodes=serializable_nodes)

    try:
        ws = websocket.create_connection("ws://127.0.0.1:3000")
        json_str = json.dumps(dic)
        ws.send(json_str)
    except Exception:
        print("WebSocket not available")
