from types import FrameType
from typing import Any, Callable


TraceFunc = Callable[[FrameType, str, Any], Any]