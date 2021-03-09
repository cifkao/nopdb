import bdb
import sys
from types import FrameType
from typing import Any, Callable, Dict, Optional, Tuple, Type

from .common import TraceFunc


def get_nice_debugger(frame: FrameType, cls: Type[bdb.Bdb], kwargs: dict):
    class NiceDebugger(cls):  # type: ignore
        def __init__(self, frame: FrameType, kwargs: dict):
            self._orig_trace_func = sys.gettrace()
            self._orig_local_trace_funcs = _get_local_trace_funcs(frame)
            super().__init__(**kwargs)

        def set_continue(self) -> None:
            super().set_continue()
            if sys.gettrace() is None:
                self._restore_trace_funcs()

        def trace_dispatch(
            self, frame: FrameType, event: str, arg: Any
        ) -> Optional[Callable[[FrameType, str, Any], Any]]:
            if id(frame) not in self._orig_local_trace_funcs:
                self._orig_local_trace_funcs[id(frame)] = (frame, frame.f_trace)

            try:
                return super().trace_dispatch(frame, event, arg)
            except bdb.BdbQuit:
                self._restore_trace_funcs()
                return None

        def _restore_trace_funcs(self) -> None:
            _restore_local_trace_funcs(self._orig_local_trace_funcs)
            sys.settrace(self._orig_trace_func)

    return NiceDebugger(frame, kwargs)


def _get_local_trace_funcs(
    frame: FrameType,
) -> Dict[int, Tuple[FrameType, Optional[TraceFunc]]]:
    trace_funcs = {}
    while True:
        # Store a reference to the frame to prevent its ID from being reused by another
        # frame
        trace_funcs[id(frame)] = (frame, frame.f_trace)
        if not frame.f_back:
            break
        frame = frame.f_back
    return trace_funcs


def _restore_local_trace_funcs(
    local_trace_funcs: Dict[int, Tuple[FrameType, Optional[TraceFunc]]]
) -> None:
    for frame, trace_func in local_trace_funcs.values():
        if trace_func is None:
            del frame.f_trace
        else:
            frame.f_trace = trace_func
