import contextlib
import threading
from types import FrameType
from typing import Any, Callable, TypeVar


TraceFunc = Callable[[FrameType, str, Any], Any]


TFriendlyContextManager = TypeVar(
    "TFriendlyContextManager", bound="FriendlyContextManager"
)


THREAD_LOCAL = threading.local()


# Some functions for suspending and resuming tracing internally. We cannot have
# a @contextlib.contextmanager for this, because the __enter__ would end up being
# traced. So we just define two functions and use them with try-finally.
# Note that this is only necessary in code that uses other libraries.


def suspend():
    THREAD_LOCAL.suspended = getattr(THREAD_LOCAL, "suspended", 0) + 1


def resume():
    THREAD_LOCAL.suspended -= 1


def is_suspended():
    return getattr(THREAD_LOCAL, "suspended", 0) > 0


class FriendlyContextManager:
    def __init__(self):
        suspend()
        try:
            self._exit_stack = contextlib.ExitStack()
            self._exit_stack.__enter__()
        finally:
            resume()

    def __enter__(self: TFriendlyContextManager) -> TFriendlyContextManager:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        suspend()
        try:
            return self._exit_stack.__exit__(exc_type, exc_value, traceback)
        finally:
            resume()
