import collections
import contextlib
import functools
from os import PathLike
import sys
import threading
from types import CodeType, FrameType, ModuleType
from typing import (
    Any,
    Callable,
    ContextManager,
    Iterable,
    List,
    Optional,
    Dict,
    Set,
    Tuple,
    Union,
    cast,
)
import warnings

from .call_info import CallCapture, CallInfo
from .common import TraceFunc
from .scope import Scope
from .breakpoint import Breakpoint


__all__ = [
    "Handle",
    "Nopdb",
    "breakpoint",
    "capture_call",
    "capture_calls",
    "get_nopdb",
]


class Handle:
    pass


class Nopdb:
    def __init__(self):
        self._started = False
        self._orig_trace_func: Optional[TraceFunc] = None
        self._callbacks: Dict[
            Handle, Tuple[Scope, Set[str], TraceFunc]
        ] = collections.OrderedDict()

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        if self._started:
            raise RuntimeError("nopdb has already been started")
        self._orig_trace_func = sys.gettrace()
        sys.settrace(self._trace_func)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            raise RuntimeError("nopdb has not been started")
        if getattr(sys.gettrace(), "__self__") is self:
            sys.settrace(self._orig_trace_func)
        else:
            warnings.warn(
                "Another trace function has been set since nopdb was started. "
                "Will not restore the original trace function.",
                RuntimeWarning,
            )
        self._started = False

    @contextlib.contextmanager
    def _as_started(self):
        started = self._started
        if started and getattr(sys.gettrace(), "__self__") is not self:
            raise RuntimeError(
                "nopdb has been started, but a different trace function was "
                "set in the meantime"
            )
        if not started:
            self.start()
        try:
            yield
        finally:
            if not started:
                self.stop()

    def __enter__(self) -> "Nopdb":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()

    def _trace_func(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        # Do not do anything if this instance is not currently tracing
        if getattr(sys.gettrace(), "__self__", None) is not self:
            return None

        trace_locally = False

        # Check which callbacks we need to call
        for scope, events, callback in self._callbacks.values():
            if scope.match_frame(frame):
                # If an event other than 'call' is requested, we will need to
                # return a local trace function.
                if event == "call" and not all(e == "call" for e in events):
                    trace_locally = True

                if event in events:
                    callback(frame, event, arg)

        if trace_locally:
            return self._trace_func

        return None

    def add_callback(
        self, scope: Scope, callback: TraceFunc, events: Iterable[str] = None
    ) -> Handle:
        handle = Handle()
        self._callbacks[handle] = (scope, set(events or []), callback)
        return handle

    def remove_callback(self, handle: Handle):
        del self._callbacks[handle]

    def capture_call(
        self,
        function: Optional[Union[Callable, str]] = None,
        *,
        module: Optional[ModuleType] = None,
        file: Optional[Union[str, PathLike]] = None,
        obj: Optional[Any] = None
    ) -> ContextManager[CallInfo]:
        """Capture a function call.

        If a function is called multiple times, only the last call will be captured.

        Args:
            function (Union[Callable, str], optional): A Python callable or the name of
                a Python function. If an instance method is passed, only calls invoked
                on that particular instance will be captured. Defaults to None.
            module (ModuleType, optional): A Python module. If given, only calls to
                functions defined in this module will be captured. Defaults to None.
            file (Union[str, PathLike], optional): A path to a Python source file. If
                given, only calls to functions defined in this file will be captured.
                If a string is passed, it will be used as a glob-style pattern for
                :meth:`pathlib.PurePath.match`. If a path-like object is passed, it
                will be resolved to a canonical path and checked for an exact match.
                Defaults to None.
            obj (Any, optional): A Python object. If given, only calls to this object's
                methods will be captured. Defaults to None.

        Returns:
            ContextManager[CallInfo]: A context manager returning a :class:`CallInfo`
            object.
        """
        return cast(
            ContextManager[CallInfo],
            self._capture_calls(
                scope=Scope(function, module, file, obj), capture_all=False
            ),
        )

    def capture_calls(
        self,
        function: Optional[Union[Callable, str]] = None,
        *,
        module: Optional[ModuleType] = None,
        file: Optional[Union[str, PathLike]] = None,
        obj: Optional[Any] = None
    ) -> ContextManager[List[CallInfo]]:
        """Capture function calls.

        Args:
            function (Union[Callable, str], optional): A Python callable or the name of
                a Python function. If an instance method is passed, only calls invoked
                on that particular instance will be captured. Defaults to None.
            module (ModuleType, optional): A Python module. If given, only calls to
                functions defined in this module will be captured. Defaults to None.
            file (Union[str, PathLike], optional): A path to a Python source file. If
                given, only calls to functions defined in this file will be captured.
                If a string is passed, it will be used as a glob-style pattern for
                :meth:`pathlib.PurePath.match`. If a path-like object is passed, it
                will be resolved to a canonical path and checked for an exact match.
                Defaults to None.
            obj (Any, optional): A Python object. If given, only calls to this object's
                methods will be captured. Defaults to None.

        Returns:
            ContextManager[List[CallInfo]]: A context manager returning a list of
            :class:`CallInfo` objects.
        """
        return cast(
            ContextManager[List[CallInfo]],
            self._capture_calls(
                scope=Scope(function, module, file, obj), capture_all=True
            ),
        )

    @contextlib.contextmanager
    def _capture_calls(self, *, scope: Scope, capture_all: bool):
        with self._as_started():
            capture = CallCapture(capture_all=capture_all)
            handle = self.add_callback(scope, capture, ["call", "return"])
            try:
                if capture_all:
                    yield capture.result_list
                else:
                    yield capture.result
            finally:
                self.remove_callback(handle)

    @contextlib.contextmanager  # type: ignore
    def breakpoint(
        self,
        *,
        function: Optional[Union[Callable, str]] = None,
        module: Optional[ModuleType] = None,
        file: Optional[Union[str, PathLike]] = None,
        line: Optional[int] = None,
        cond: Optional[Union[str, CodeType]] = None
    ) -> ContextManager[Breakpoint]:
        """Set a breakpoint.

        Args:
            function (Union[Callable, str], optional): A Python callable or the name of
                a Python function. If an instance method is passed, only calls invoked
                on that particular instance will be captured. Defaults to None.
            module (ModuleType, optional): A Python module. If given, only calls to
                functions defined in this module will be captured. Defaults to None.
            file (Union[str, PathLike], optional): A path to a Python source file. If
                given, only calls to functions defined in this file will be captured.
                If a string is passed, it will be used as a glob-style pattern for
                :meth:`pathlib.PurePath.match`. If a path-like object is passed, it
                will be resolved to a canonical path and checked for an exact match.
                Defaults to None.
            line (int, optional): The line number at which to break. Defaults to None.
            cond (Union[str, CodeType], optional): A condition to evaluate. If given,
                the breakpoint will only be triggered when the condition evaluates
                to true. Defaults to None.

        Returns:
            ContextManager[Breakpoint]: A context manager returning the breakpoint.
        """
        with self._as_started():
            scope = Scope(function, module, file)
            bp = Breakpoint(scope=scope, line=line, cond=cond)
            handle = self.add_callback(scope, bp._callback, ["call", "line"])
            try:
                yield bp  # type: ignore
            finally:
                self.remove_callback(handle)


_THREAD_LOCAL = threading.local()


def get_nopdb() -> Nopdb:
    """Return an instance of :class:`Nopdb`.

    If a :class:`Nopdb` instance is currently active, that instance is returned.
    Otherwise, the default instance for the current thread is returned.
    """
    # If a Nopdb instance is currently tracing, return it
    trace_fn = sys.gettrace()
    if hasattr(trace_fn, "__self__"):
        return getattr(trace_fn, "__self__")

    # Otherwise return the default instance for this thread
    if not hasattr(_THREAD_LOCAL, "default_nopdb"):
        _THREAD_LOCAL.default_nopdb = Nopdb()
    return _THREAD_LOCAL.default_nopdb


@functools.wraps(get_nopdb().capture_call)
def capture_call(*args, **kwargs):
    return get_nopdb().capture_call(*args, **kwargs)


@functools.wraps(get_nopdb().capture_calls)
def capture_calls(*args, **kwargs):
    return get_nopdb().capture_calls(*args, **kwargs)


@functools.wraps(get_nopdb().breakpoint)
def breakpoint(*args, **kwargs):
    return get_nopdb().breakpoint(*args, **kwargs)
