"""CADbuildr Foundation - Core types for parametric CAD (auto-generated from GraphQL schema)."""

# Re-export all generated types dynamically
from .gen.models import *
from .gen.runtime import *

# Import compute functions to register them
from . import compute_functions  # noqa: F401

# Import shape transformation methods to register them
from . import shape_methods  # noqa: F401

# Import helpers to add monkey-patched methods
from . import helpers  # noqa: F401

# Export PlaneFactory for backward compatibility
from .helpers import PlaneFactory, TFHelper

# Export pattern classes
from .pattern import CircularPattern, RectangularPattern

# DAG and WebRTC utilities
from .dag_utils import show
from .coms.utils_webrtc import (
    set_port,
    set_broker_url,
    get_build_status,
    get_screenshot,
    wait_for_feedback,
    collect_and_display_feedback,
)
from .coms.kernel_api import KernelApiClient, KernelApiError
