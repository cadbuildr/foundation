import asyncio
import threading
import time
from typing import Any, Dict
import json
from cadbuildr.foundation.utils import reset_ids

try:
    import websockets

    is_websockets_available = True
except ImportError:
    is_websockets_available = False


# Global variables to manage the server and clients
server_instance = None
connected_clients = set()
message_buffer: list[str] = []  # Buffer to store messages when no clients are connected
server_event_loop = None  # Event loop for the server

PORT = 3001


def set_port(port: int):
    global PORT
    PORT = port


async def handle_connection(websocket, path):
    """Handle incoming WebSocket connections."""
    connected_clients.add(websocket)
    print(f"Client connected: {websocket.remote_address}")

    # Send buffered messages to the newly connected client
    for message in message_buffer:
        try:
            await websocket.send(message)
        except Exception as e:
            print(f"Error sending buffered message to {websocket.remote_address}: {e}")

    # Clear the buffer after sending
    message_buffer.clear()

    try:
        # Keep the connection open to send multiple messages
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)
        print(f"Client disconnected: {websocket.remote_address}")


async def start_server():
    """Start the WebSocket server if not already running."""
    global server_instance
    if server_instance is None:
        server_instance = await websockets.serve(handle_connection, "127.0.0.1", PORT)
        print(f"WebSocket server started on ws://127.0.0.1:{PORT}")


def start_server_in_background():
    global server_event_loop
    server_event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(server_event_loop)
    server_event_loop.run_until_complete(start_server())
    server_event_loop.run_forever()


def send_to_clients(data: Dict):
    """Send data to all connected WebSocket clients. If no clients, buffer the data."""
    message = json.dumps(data)
    if connected_clients and server_event_loop is not None:
        asyncio.run_coroutine_threadsafe(_send_all_clients(message), server_event_loop)
    else:
        print("No clients connected to send data. Buffering message.")
        message_buffer.append(message)  # Store serialized message


async def _send_all_clients(message: str):
    """Helper coroutine to send messages to all clients."""
    if connected_clients:
        await asyncio.gather(
            *(client.send(message) for client in connected_clients),
            return_exceptions=True,
        )


def show_ext(dag: Any) -> None:
    """Function to generate DAG data and send it via WebSocket."""
    if not is_websockets_available:
        print("Websockets are not available")
        return
    try:
        global server_instance
        if server_instance is None:
            # Start the server in a background thread
            threading.Thread(target=start_server_in_background, daemon=True).start()
            # Give the server time to start
            time.sleep(0.1)
        # Send the data
        send_to_clients(dag)
        reset_ids()
    except Exception as e:
        print(f"WebSocket error: {e}")
