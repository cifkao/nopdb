import collections
import contextlib
import functools
from os import PathLike
import pathlib
import sys
from types import CodeType, FrameType, ModuleType
from typing import (
    Any,
    Callable,
    Iterable,
    Optional,
    Dict,
    Set,
    Tuple,
    Union,
)
import warnings

from .call_capture import CallCapture, CallListCapture
from .common import TraceFunc, THREAD_LOCAL, suspend, resume, is_suspended
from .scope import Scope
from .breakpoint import Breakpoint


__all__ = [
    "Handle",
    "NoPdb",
    "breakpoint",
    "capture_call",
    "capture_calls",
    "get_nopdb",
]


class Handle:
    pass


class NoPdb:
    """The main NoPdb class.

    Multiple instances can be created, but only one can be active in a given thread at
    a given time. It can be used as a context manager.
    """

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
        """Start this instance.

        Called automatically when the object is used as a context manager.
        """
        if self._started:
            raise RuntimeError("nopdb has already been started")
        self._orig_trace_func = sys.gettrace()
        sys.settrace(self._trace_func)
        self._started = True

    def stop(self) -> None:
        """Stop this instance.

        Called automatically when the object is used as a context manager.
        """
        if not self._started:
            raise RuntimeError("nopdb has not been started")
        if getattr(sys.gettrace(), "__self__", None) is self:
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
        if started and getattr(sys.gettrace(), "__self__", None) is not self:
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

    def __enter__(self) -> "NoPdb":
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
        if is_suspended():
            return None

        # Avoid tracing our own code
        try:
            # Replacement for PurePath.is_relative_to() for Python < 3.9
            pathlib.PurePath(frame.f_code.co_filename).relative_to(_NOPDB_ROOT)
            return None
        except ValueError:
            pass

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
        self, scope: Scope, callback: TraceFunc, events: Iterable[str]
    ) -> Handle:
        """Register a low-level callback for the given type(s) of events.

        Args:
            scope (Scope): The scope in which the callback should be active.
            callback (TraceFunc): The callback function. It should have the same
                signature as the function passed to :func:`sys.settrace`, but its
                return value will be ignored.
            events (~typing.Iterable[str]): A list of event names (:code:`'call'`,
                :code:`'line'`, :code:`'return'` or :code:`'exception'`); see
                :func:`sys.settrace`.

        Returns:
            Handle:
                A handle that can be passed to :meth:`remove_callback`.
        """
        handle = Handle()
        self._callbacks[handle] = (scope, set(events), callback)
        return handle

    def remove_callback(self, handle: Handle) -> None:
        """Remove a callback added using :meth:`add_callback`.

        Args:
            handle (Handle): A handle returned by :meth:`add_callback`.
        """
        del self._callbacks[handle]

    def capture_call(
        self,
        function: Optional[Union[Callable, str]] = None,
        *,
        module: Optional[ModuleType] = None,
        file: Optional[Union[str, PathLike]] = None
    ) -> CallCapture:
        """Capture a function call.

        The returned object can be used as a context manager, which will cause the
        capturing to stop at the end of the block.

        If multiple calls occur, the returned object will be updated as each call
        returns. At the end, the returned object will contain information about the
        call that was the last to return.

        Args:
            function (~typing.Callable or str, optional): A Python callable or the name
                of a Python function. If an instance method is passed, only calls
                invoked on that particular instance will be captured.
            module (~types.ModuleType, optional): A Python module. If given, only calls
                to functions defined in this module will be captured.
            file (str or ~os.PathLike, optional): A path to a Python source file. If
                given, only calls to functions defined in this file will be captured.
                If a string is passed, it will be used as a glob-style pattern for
                :meth:`pathlib.PurePath.match`. If a path-like object is passed, it
                will be resolved to a canonical path and checked for an exact match.

        Returns:
            CallCapture:
                An instance of :class:`CallInfo` which also works as a context
                manager.
        """
        suspend()
        try:
            capture = CallCapture()
            capture._exit_stack.enter_context(self._as_started())
            handle = self.add_callback(
                Scope(function, module, file),
                capture._callback,
                ["call", "return"],
            )
            capture._exit_stack.callback(
                functools.partial(self.remove_callback, handle=handle)
            )
            return capture
        finally:
            resume()

    def capture_calls(
        self,
        function: Optional[Union[Callable, str]] = None,
        *,
        module: Optional[ModuleType] = None,
        file: Optional[Union[str, PathLike]] = None
    ) -> CallListCapture:
        """Capture function calls.

        The return value is an initially empty list, which is updated with a new item
        as each call returns. At the end, the list will contain a :class:`CallInfo`
        object for each call, following the order in which the calls returned.

        The return value can also be used as a context manager, which will cause the
        capturing to stop at the end of the block.

        Args:
            function (~typing.Callable or str, optional): A Python callable or the name
                of a Python function. If an instance method is passed, only calls
                invoked on that particular instance will be captured.
            module (~types.ModuleType, optional): A Python module. If given, only calls
                to functions defined in this module will be captured.
            file (str or ~os.PathLike, optional): A path to a Python source file. If
                given, only calls to functions defined in this file will be captured.
                If a string is passed, it will be used as a glob-style pattern for
                :meth:`pathlib.PurePath.match`. If a path-like object is passed, it
                will be resolved to a canonical path and checked for an exact match.

        Returns:
            CallListCapture:
                A list of :class:`CallInfo` objects which also works as a
                context manager.
        """
        suspend()
        try:
            capture = CallListCapture()
            capture._exit_stack.enter_context(self._as_started())
            handle = self.add_callback(
                Scope(function, module, file),
                capture._callback,
                ["call", "return"],
            )
            capture._exit_stack.callback(
                functools.partial(self.remove_callback, handle=handle)
            )
            return capture
        finally:
            resume()

    def breakpoint(
        self,
        *,
        function: Optional[Union[Callable, str]] = None,
        module: Optional[ModuleType] = None,
        file: Optional[Union[str, PathLike]] = None,
        line: Optional[int] = None,
        cond: Optional[Union[str, bytes, CodeType]] = None
    ) -> Breakpoint:
        """Set a breakpoint.

        The returned :class:`Breakpoint` object works as a context manager that removes
        the breakpoint at the end of the block.

        The breakpoint itself does not stop execution when hit, but can trigger
        user-defined actions; see :meth:`Breakpoint.eval`, :meth:`Breakpoint.exec`,
        :meth:`Breakpoint.debug`.

        At least a function, a module or a file must be specified. If no function is
        given, a line number is also required.

        Example::

           # Stop at line 3 of the file or notebook cell where f is defined
           with nopdb.breakpoint(function=f, line=3) as bp:
               x = bp.eval("x")             # Schedule an expression
               type_y = bp.eval("type(y)")  # Another one
               # Run some code that calls f...

           print(x, type_y)  # Retrieve the values

        Args:
            function (~typing.Callable or str, optional): A Python callable or the name
                of a Python function. If an instance method is passed, only calls
                invoked on that particular instance will trigger the breakpoint.
            module (~types.ModuleType, optional): A Python module.
            file (str or ~os.PathLike, optional): A path to a Python source file.
                If a string is passed, it will be used as a glob-style pattern for
                :meth:`pathlib.PurePath.match`. If a path-like object is passed, it
                will be resolved to a canonical path and checked for an exact match.
            line (int, optional): The line number at which to break, counted from the
                beginning of the file. If `None` and a `function` is passed, the
                breakpoint will be triggered as soon as the function is called. If no
                `function` is passed, `line` is required. Note that unlike in `pdb`,
                the breakpoint will only get triggered by this exact line number.
            cond (str, bytes or ~types.CodeType, optional): A condition to evaluate. If
                given, the breakpoint will only be triggered when the condition
                evaluates to true.

        Returns:
            Breakpoint:
                The breakpoint object, which also works as a context manager.
        """
        suspend()
        try:
            scope = Scope(function, module, file)
            bp = Breakpoint(scope=scope, line=line, cond=cond)
            bp._exit_stack.enter_context(self._as_started())
            handle = self.add_callback(scope, bp._callback, ["call", "line"])
            bp._exit_stack.callback(
                functools.partial(self.remove_callback, handle=handle)
            )
            return bp
        finally:
            resume()


def get_nopdb() -> NoPdb:
    """Return an instance of :class:`NoPdb`.

    If a :class:`NoPdb` instance is currently active in the current thread, that
    instance is returned. Otherwise, the default instance for the current thread is
    returned.
    """
    # If a NoPdb instance is currently tracing, return it
    trace_obj = getattr(sys.gettrace(), "__self__", None)
    if isinstance(trace_obj, NoPdb):
        return trace_obj

    # Otherwise return the default instance for this thread
    if not hasattr(THREAD_LOCAL, "default_nopdb"):
        THREAD_LOCAL.default_nopdb = NoPdb()
    return THREAD_LOCAL.default_nopdb


@functools.wraps(get_nopdb().capture_call)
def capture_call(*args, **kwargs):
    return get_nopdb().capture_call(*args, **kwargs)


@functools.wraps(get_nopdb().capture_calls)
def capture_calls(*args, **kwargs):
    return get_nopdb().capture_calls(*args, **kwargs)


@functools.wraps(get_nopdb().breakpoint)
def breakpoint(*args, **kwargs):
    return get_nopdb().breakpoint(*args, **kwargs)


_NOPDB_ROOT = pathlib.PurePath(__file__).parent
