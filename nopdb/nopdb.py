import collections
import contextlib
import ctypes
import functools
import inspect
import sys
import threading
import traceback
from types import CodeType, FrameType, ModuleType
from typing import Any, Callable, ContextManager, Iterable, Iterator, List, Optional, Dict, Set, Tuple, Union, cast
import warnings


__all__ = [
    'Breakpoint',
    'CallInfo',
    'Handle',
    'Nopdb',
    'Scope',
    'TraceFunc',
    'breakpoint',
    'capture_call',
    'capture_calls',
    'get_nopdb'
]


TraceFunc = Callable[[FrameType, str, Any], Any]


class Handle:
    pass


class CallInfo:

    def __init__(self):
        self.name: Optional[str] = None
        self.filename: Optional[str] = None
        self.stack: Optional[traceback.StackSummary] = None
        self.args: Optional[dict] = None
        self.locals: Optional[dict] = None
        self.globals: Optional[dict] = None
        self.return_value: Optional[Any] = None

    def __repr__(self) -> str:
        return '{}(name={!r}, args={}({}), return_value={!r})'.format(
            type(self).__name__, self.name,
            type(self.args).__name__,
            ', '.join('{}={!r}'.format(k, v) for k, v in self.args.items()),
            self.return_value,
        )

    def print_stack(self, file = None) -> None:
        for line in self.stack.format():
            print(line, end='', file=file)


class Scope:

    def __init__(self,
                 function: Optional[Union[Callable, str]] = None,
                 module: Optional[ModuleType] = None,
                 filename: Optional[str] = None,
                 obj: Optional[Any] = None,
                 parent_scopes: 'Optional[List[Scope]]' = None):
        self.function = function
        self.module = module
        self.filename = filename
        self.obj = obj
        self.parent_scopes = list(parent_scopes) if parent_scopes else []

        self._fn_name, self._fn_code, self._fn_self = None, None, None
        if isinstance(function, str):
            self._fn_name = function
        elif function is not None:
            self._fn_code, self._fn_self = _get_code_and_self(function)

        if obj is not None:
            self._fn_self = obj

    def match_frame(self, frame: FrameType) -> bool:
        if self._fn_code is not None:
            if frame.f_code is not self._fn_code:
                return False
            if self._fn_self is not None:
                # The function is a method; check if `self` is the correct object
                arg_info = inspect.getargvalues(frame)
                if len(arg_info.args) == 0:  # Just in case this somehow happens
                    return False
                if arg_info.locals[arg_info.args[0]] is not self._fn_self:
                    return False

        if self._fn_name is not None:
            if frame.f_code.co_name != self._fn_name:
                return False

        if self.module is not None:
            if frame.f_code.co_filename != self.module.__file__:
                return False

        if self.filename is not None:
            # TODO: Support relative paths
            if frame.f_code.co_filename != self.filename:
                return False

        for scope in self.parent_scopes:
            raise NotImplementedError()

        return True


class Breakpoint:

    def __init__(self,
                 scope: Scope,
                 line: Optional[int] = None,
                 cond: Optional[Union[str, CodeType]] = None):
        self.scope = scope
        self.line = line
        self.cond = cond
        self._todo_list: List[Callable[[FrameType], None]] = []

    def eval(self, expression: str, variables: Optional[Dict[str, Any]] = None) -> list:
        results = []
        self._todo_list.append(functools.partial(
            self._do_eval, expression=expression, variables=variables, results=results))
        return results

    def exec(self, code: Union[str, CodeType], variables: Optional[Dict[str, Any]] = None) -> None:
        self._todo_list.append(functools.partial(
            self._do_exec, code=code, variables=variables))

    @staticmethod
    def _do_eval(frame: FrameType, expression: str, results: list,
                 variables: Optional[Dict[str, Any]]) -> Any:
        f_locals = {**frame.f_locals, **(variables or {})}
        result = eval(expression, dict(frame.f_globals), f_locals)
        results.append(result)

    @staticmethod
    def _do_exec(frame: FrameType, code: Union[str, CodeType],
                 variables: Optional[Dict[str, Any]]) -> None:
        if variables is None:
            variables = {}
        conflict_vars = frame.f_locals.keys() & variables.keys()
        if conflict_vars:
            raise RuntimeError("The following external variables conflict with local ones: {}"
                               .format(repr(conflict_vars).lstrip('{').rstrip('}')))

        # Run the code with the external variables added, then remove them again
        f_locals = {**frame.f_locals, **variables}
        exec(code, frame.f_globals, f_locals)
        for name in list(f_locals.keys() & variables.keys()):
            del f_locals[name]

        # Update the frame
        for name in list(frame.f_locals.keys() - f_locals.keys()):
            del frame.f_locals[name]
        frame.f_locals.update(f_locals)
        _update_locals(frame)

    def _callback(self, frame: FrameType, event: str, arg: Any):
        # If line is None, we break at the call...
        if self.line is None and event != 'call':
            return
        # ...otherwise we break at the given line
        if self.line is not None and (event != 'line' or frame.f_lineno != self.line):
            return
        # Evaluate condition if given
        if self.cond is not None and not eval(self.cond, frame.f_globals, frame.f_locals):
            return

        for action in self._todo_list:
            action(frame)


class Nopdb:

    def __init__(self):
        self._started = False
        self._orig_trace_func: Optional[TraceFunc] = None
        self._callbacks: Dict[Handle, Tuple[Scope, Set[str], TraceFunc]] \
            = collections.OrderedDict()

        def trace_func(frame: FrameType, event: str, arg: Any) -> Optional[TraceFunc]:
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
                     filename: Optional[str] = None,
                     obj: Optional[Any] = None) -> ContextManager[CallInfo]:
        return cast(ContextManager[CallInfo],
                    self._capture_calls(scope=Scope(function, module, filename, obj),
                                        capture_all=False))

    def capture_calls(self,
                      function: Optional[Union[Callable, str]] = None, *,
                      module: Optional[ModuleType] = None,
                      filename: Optional[str] = None,
                      obj: Optional[Any] = None) -> ContextManager[List[CallInfo]]:
        return cast(ContextManager[List[CallInfo]],
                    self._capture_calls(scope=Scope(function, module, filename, obj),
                                        capture_all=True))

    @contextlib.contextmanager
    def _capture_calls(self, *, scope: Scope, capture_all: bool):
        with self._as_started():
            capture = _CallCapture(capture_all=capture_all)
            handle = self.add_callback(scope, capture, ['call', 'return'])
            try:
                if capture_all:
                    yield capture.result_list
                else:
                    yield capture.result
            finally:
                self.remove_callback(handle)

    @contextlib.contextmanager
    def breakpoint(self, *,
                   function: Optional[Union[Callable, str]] = None,
                   module: Optional[ModuleType] = None,
                   filename: Optional[str] = None,
                   line: int,
                   cond: Optional[Union[str, CodeType]] = None) -> Iterator[Breakpoint]:
        with self._as_started():
            scope = Scope(function, module, filename)
            bp = Breakpoint(scope=scope, line=line, cond=cond)
            handle = self.add_callback(scope, bp._callback, ['call', 'line'])
            try:
                yield bp
            finally:
                self.remove_callback(handle)


class _CallCapture:

    def __init__(self, capture_all=False):
        self.capture_all = capture_all
        if capture_all:
            self.result_list = []
        else:
            self.result = CallInfo()
        self._result_by_frame: Dict[FrameType, CallInfo] = {}

    def __call__(self, frame: FrameType, event: str, arg: Any):
        if frame not in self._result_by_frame:
            self._result_by_frame[frame] = CallInfo()
        result = self._result_by_frame[frame]

        if event == 'call':
            result.name = frame.f_code.co_name
            result.filename = frame.f_code.co_filename
            result.stack = traceback.extract_stack(frame)
            result.return_value = None

            # Extract argument values
            arg_info = inspect.getargvalues(frame)
            result.args = collections.OrderedDict(
                [(name, arg_info.locals[name])
                for name in arg_info.args
                if name in arg_info.locals])
        elif event == 'return':
            result.locals = frame.f_locals
            result.globals = frame.f_globals
            result.return_value = arg

            # This frame is done, save the result
            del self._result_by_frame[frame]
            if self.capture_all:
                self.result_list.append(result)
            else:
                self.result.__dict__.update(result.__dict__)


_THREAD_LOCAL = threading.local()
_THREAD_LOCAL.default_nopdb = Nopdb()


def get_nopdb() -> Nopdb:
    return _THREAD_LOCAL.default_nopdb


def capture_call(function: Optional[Union[Callable, str]] = None, *,
                 module: Optional[ModuleType] = None,
                 filename: Optional[str] = None,
                 obj: Optional[Any] = None) -> ContextManager[CallInfo]:
    return get_nopdb().capture_call(function=function, module=module, filename=filename, obj=obj)


def capture_calls(function: Optional[Union[Callable, str]] = None, *,
                  module: Optional[ModuleType] = None,
                  filename: Optional[str] = None,
                  obj: Optional[Any] = None) -> ContextManager[List[CallInfo]]:
    return get_nopdb().capture_calls(function=function, module=module, filename=filename, obj=obj)


def breakpoint(function: Optional[Union[Callable, str]] = None, *,
               module: Optional[ModuleType] = None,
               filename: Optional[str] = None,
               line: Optional[int] = None,
               cond: Optional[Union[str, CodeType]] = None) -> ContextManager[Breakpoint]:
    return get_nopdb().breakpoint(
        function=function, module=module, filename=filename, line=line, cond=cond)


def _get_code_and_self(fn: Callable) -> Tuple[CodeType, Any]:
    # Bound method
    if inspect.ismethod(fn):
        return fn.__code__, fn.__self__
    # Regular function
    if inspect.isfunction(fn):
        return fn.__code__, None
    # Instance of a class that defines a __call__ method
    if (hasattr(fn, '__class__')
            and hasattr(fn.__class__, '__call__')
            and inspect.isfunction(fn.__class__.__call__)):
        return fn.__class__.__call__.__code__, fn
    raise TypeError('Could not find the code for {!r}. '
                    'Please provide a pure Python callable'.format(fn))


def _update_locals(frame: FrameType):
    ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(1))
