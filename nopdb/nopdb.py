import collections
import contextlib
import functools
from os import PathLike
import sys
import threading
from types import CodeType, FrameType, ModuleType
from typing import Any, Callable, ContextManager, Iterable, List, Optional, Dict, Set, Tuple, Union, cast
import warnings

from .call_info import CallCapture, CallInfo
from .common import TraceFunc
from .scope import Scope
from .breakpoint import Breakpoint


__all__ = [
    'Handle',
    'Nopdb',
    'breakpoint',
    'capture_call',
    'capture_calls',
    'get_nopdb'
]


class Handle:
    pass


class Nopdb:

    def __init__(self):
        self._started = False
        self._orig_trace_func: Optional[TraceFunc] = None
        self._callbacks: Dict[Handle, Tuple[Scope, Set[str], TraceFunc]] \
            = collections.OrderedDict()

        def trace_func(frame: FrameType, event: str, arg: Any) -> Optional[TraceFunc]:
            # Do not do anything if this instance is not currently tracing
            if sys.gettrace() is not trace_func:
                return None

            trace_locally = False

            # Check which callbacks we need to call
            for scope, events, callback in self._callbacks.values():
                if scope.match_frame(frame):
                    # If an event other than 'call' is requested, we will need to return a local
                    # trace function.
                    if event == 'call' and not all(e == 'call' for e in events):
                        trace_locally = True

                    if event in events:
                        callback(frame, event, arg)

            if trace_locally:
                return trace_func

        self._trace_func = trace_func

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        if self._started:
            raise RuntimeError('nopdb has already been started')
        self._orig_trace_func = sys.gettrace()
        sys.settrace(self._trace_func)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            raise RuntimeError('nopdb has not been started')
        if sys.gettrace() is self._trace_func:
            sys.settrace(self._orig_trace_func)
        else:
            warnings.warn(
                'Another trace function has been set since nopdb was started. '
                'Will not restore the original trace function.',
                RuntimeWarning)
        self._started = False

    @contextlib.contextmanager
    def _as_started(self):
        started = self._started
        if started and sys.gettrace() is not self._trace_func:
            raise RuntimeError('nopdb has been started, but a different trace function was '
                               'set in the meantime')
        if not started:
            self.start()
        try:
            yield
        finally:
            if not started:
                self.stop()

    def __enter__(self) -> 'Nopdb':
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()

    def add_callback(self, scope: Scope, callback: TraceFunc,
                     events: Iterable[str] = None) -> Handle:
        handle = Handle()
        self._callbacks[handle] = (scope, set(events or []), callback)
        return handle

    def remove_callback(self, handle: Handle):
        del self._callbacks[handle]

    def capture_call(self,
                     function: Optional[Union[Callable, str]] = None, *,
                     module: Optional[ModuleType] = None,
                     file: Optional[Union[str, PathLike]] = None,
                     obj: Optional[Any] = None) -> ContextManager[CallInfo]:
        return cast(ContextManager[CallInfo],
                    self._capture_calls(scope=Scope(function, module, file, obj),
                                        capture_all=False))

    def capture_calls(self,
                      function: Optional[Union[Callable, str]] = None, *,
                      module: Optional[ModuleType] = None,
                      file: Optional[Union[str, PathLike]] = None,
                      obj: Optional[Any] = None) -> ContextManager[List[CallInfo]]:
        return cast(ContextManager[List[CallInfo]],
                    self._capture_calls(scope=Scope(function, module, file, obj),
                                        capture_all=True))

    @contextlib.contextmanager
    def _capture_calls(self, *, scope: Scope, capture_all: bool):
        with self._as_started():
            capture = CallCapture(capture_all=capture_all)
            handle = self.add_callback(scope, capture, ['call', 'return'])
            try:
                if capture_all:
                    yield capture.result_list
                else:
                    yield capture.result
            finally:
                self.remove_callback(handle)

    @contextlib.contextmanager  # type: ignore
    def breakpoint(self, *,
                   function: Optional[Union[Callable, str]] = None,
                   module: Optional[ModuleType] = None,
                   file: Optional[Union[str, PathLike]] = None,
                   line: Optional[int] = None,
                   cond: Optional[Union[str, CodeType]] = None) -> ContextManager[Breakpoint]:
        with self._as_started():
            scope = Scope(function, module, file)
            bp = Breakpoint(scope=scope, line=line, cond=cond)
            handle = self.add_callback(scope, bp._callback, ['call', 'line'])
            try:
                yield bp
            finally:
                self.remove_callback(handle)


_THREAD_LOCAL = threading.local()


def get_nopdb() -> Nopdb:
    if not hasattr(_THREAD_LOCAL, 'default_nopdb'):
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
