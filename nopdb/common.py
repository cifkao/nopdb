import contextlib
from types import FrameType
from typing import Any, Callable, TypeVar


TraceFunc = Callable[[FrameType, str, Any], Any]

TFriendlyContextManager = TypeVar(
    "TFriendlyContextManager", bound="FriendlyContextManager"
)


class FriendlyContextManager:
    def __init__(self):
        self._exit_stack = contextlib.ExitStack()

    def __enter__(self: TFriendlyContextManager) -> TFriendlyContextManager:
        self._exit_stack.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return self._exit_stack.__exit__(exc_type, exc_value, traceback)
