import json
import time
from typing import Any, Dict, Optional

try:
    import requests
    is_requests_available = True
except ImportError:
    is_requests_available = False
    print("Warning: requests library not available. Install with: pip install requests")

from cadbuildr.foundation.utils import reset_ids

# Global configuration for broker URL
BROKER_URL = "http://localhost:5000/send"
_RECORDED_REQUEST_IDS: list[str] = []


def create_dag_message(dag: Dict[str, Any], request_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a typed DAG message for the broker."""
    return {
        "type": "dag",
        "dag": dag,
        "request_id": request_id
    }


def set_broker_url(url: str):
    """
    Set the broker URL for sending DAG data.
    
    Args:
        url: Full URL to the broker's HTTP endpoint (e.g., 'http://localhost:5000/send')
    """
    global BROKER_URL
    BROKER_URL = url


def set_port(port: int):
    """
    Legacy function for backward compatibility.
    With WebRTC broker, this sets the broker's HTTP port.
    
    Args:
        port: HTTP port of the broker (default: 5000)
    """
    global BROKER_URL
    BROKER_URL = f"http://localhost:{port}/send"


def show_ext(dag: Any, request_id: Optional[str] = None) -> Optional[str]:
    """
    Send DAG data to the broker via HTTP POST.
    The broker forwards the data to the viewer via WebRTC.
    
    Args:
        dag: Dictionary containing DAG data to visualize
        request_id: Optional request ID for tracking
    
    Returns:
        The request_id from the broker, or None if failed
    """
    if not is_requests_available:
        print("Error: requests library not available. Install with: pip install requests")
        return None
    
    try:
        # Create typed message
        message = create_dag_message(dag, request_id)
        
        # Send DAG to broker
        response = requests.post(
            BROKER_URL,
            json=message,
            timeout=2.0
        )
        
        if response.status_code == 200:
            result = response.json()
            returned_request_id = result.get('request_id')
            if returned_request_id:
                _RECORDED_REQUEST_IDS.append(returned_request_id)
            print(f"✓ Build submitted with ID: {returned_request_id}")
            reset_ids()
            return returned_request_id
        else:
            print(f"Warning: Broker responded with status {response.status_code}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to broker at {BROKER_URL}")
        print("Make sure the broker is running: cadbuildr-broker")
        return None
    except requests.exceptions.Timeout:
        print(f"Error: Timeout connecting to broker at {BROKER_URL}")
        return None
    except Exception as e:
        print(f"Error sending to broker: {e}")
        return None


def get_build_status(request_id: str, broker_url: str = None) -> Optional[Dict]:
    """
    Query build status from broker.

    Args:
        request_id: The request ID returned by show_ext()
        broker_url: Optional broker base URL (default: derived from BROKER_URL)

    Returns:
        Status dictionary or None if failed
    """
    if not is_requests_available:
        print("Error: requests library not available. Install with: pip install requests")
        return None

    try:
        # Derive base URL from BROKER_URL if not provided
        if broker_url is None:
            broker_url = BROKER_URL.replace('/send', '')

        response = requests.get(
            f"{broker_url}/status/{request_id}",
            timeout=2.0
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print(f"Error: Execution {request_id} not found")
            return None
        else:
            print(f"Error: Status query failed with status {response.status_code}")
            return None

    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to broker")
        return None
    except Exception as e:
        print(f"Error querying status: {e}")
        return None


def drain_recorded_request_ids() -> list[str]:
    """Return and clear recorded request IDs from recent show_ext calls."""
    global _RECORDED_REQUEST_IDS
    ids = _RECORDED_REQUEST_IDS[:]
    _RECORDED_REQUEST_IDS = []
    return ids


def wait_for_feedback(
    request_id: str,
    timeout: float = 30.0,
    interval: float = 0.5,
    broker_url: str = None
) -> Optional[Dict]:
    """
    Poll broker for feedback until build completes or timeout.
    
    Args:
        request_id: The request ID to poll for
        timeout: Maximum time to wait (seconds)
        interval: Polling interval (seconds)
        broker_url: Optional broker base URL (default: derived from BROKER_URL)
    
    Returns:
        Status dictionary or None if timeout/error
    """
    deadline = time.time() + timeout
    last_status: Optional[Dict] = None

    while time.time() < deadline:
        status = get_build_status(request_id, broker_url)
        if status:
            last_status = status
            if status.get("status") not in {"pending", "building"}:
                return status
        time.sleep(interval)

    return last_status


def collect_and_display_feedback(
    timeout: float = 30.0,
    interval: float = 0.5,
    broker_url: str = None,
    verbose: bool = True
) -> list[Dict]:
    """
    Collect and display feedback for all builds executed since last call.
    Similar to what build-with-feedback does after code execution.
    
    Args:
        timeout: Maximum time to wait for each build (seconds)
        interval: Polling interval (seconds)
        broker_url: Optional broker base URL
        verbose: If True, print feedback to stdout
    
    Returns:
        List of feedback dictionaries (one per request ID)
    """
    request_ids = drain_recorded_request_ids()
    feedbacks = []

    if not request_ids:
        if verbose:
            print("(No builds recorded during execution)")
        return feedbacks

    if verbose:
        print("\n=== Build Feedback ===")

    for rid in request_ids:
        if verbose:
            print(f"\nRequest ID: {rid}")
        
        feedback = wait_for_feedback(rid, timeout, interval, broker_url)
        
        if feedback:
            feedbacks.append(feedback)
            if verbose:
                print(json.dumps(feedback, indent=2))
        else:
            if verbose:
                print("No feedback available (timed out).")

    return feedbacks


def get_screenshot(request_id: str, broker_url: str = None) -> Optional[str]:
    """
    Get screenshot data URL from broker for a given request ID.

    Args:
        request_id: The request ID returned by show_ext()
        broker_url: Optional broker base URL (default: derived from BROKER_URL)

    Returns:
        Screenshot data URL or None if not available
    """
    if not is_requests_available:
        print("Error: requests library not available. Install with: pip install requests")
        return None

    try:
        # Derive base URL from BROKER_URL if not provided
        if broker_url is None:
            broker_url = BROKER_URL.replace('/send', '')

        response = requests.get(
            f"{broker_url}/screenshot/{request_id}",
            timeout=2.0
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("data_url")
        elif response.status_code == 404:
            print(f"Error: Screenshot not available for request {request_id}")
            return None
        else:
            print(f"Error: Screenshot query failed with status {response.status_code}")
            return None

    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to broker")
        return None
    except Exception as e:
        print(f"Error querying screenshot: {e}")
        return None
