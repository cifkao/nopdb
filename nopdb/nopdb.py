import collections
import contextlib
import inspect
import sys
import traceback
from types import CodeType, FrameType, ModuleType
from typing import Any, Callable, ContextManager, Iterator, List, Optional, Dict, Tuple, Union
import warnings


__all__ = [
    'CallInfo',
    'Handle',
    'Nopdb',
    'Scope',
    'TraceFunc',
    'capture_call',
    'capture_calls',
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
                 parent_scopes: 'Optional[List[Scope]]' = None):
        self.function = function
        self.module = module
        self.filename = filename
        self.parent_scopes = list(parent_scopes) if parent_scopes else []

        self._fn_name, self._fn_code, self._fn_self = None, None, None
        if isinstance(function, str):
            self._fn_name = function
        elif function is not None:
            self._fn_code, self._fn_self = _get_code_and_self(function)

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


class Nopdb:

    def __init__(self):
        self._started = False
        self._orig_trace_func: Optional[TraceFunc] = None
        self._callbacks: Dict[Handle, Tuple[Scope, List[str], Callable]] \
            = collections.OrderedDict()

        def trace_func(frame: FrameType, event: str, arg: Any) -> Optional[TraceFunc]:
            match = False
            for scope, events, callback in self._callbacks.values():
                if scope.match_frame(frame):
                    match = True
                    if event in events:
                        callback(frame, event, arg)

            if match:
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
    def _as_started(self) -> None:
        started = self._started
        if started and sys.gettrace() is not self._trace_func:
            raise RuntimeError('nopdb has been started, but a different trace function was '
                               'set in the meantime')
        if not started:
            self.start()
        yield
        if not started:
            self.stop()

    def __enter__(self) -> 'Nopdb':
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()

    def add_callback(self, scope: 'Scope', callback, events=None) -> Handle:
        handle = Handle()
        self._callbacks[handle] = (scope, set(events or []), callback)
        return handle

    def remove_callback(self, handle: Handle):
        del self._callbacks[handle]

    @contextlib.contextmanager
    def capture_call(self,
                     function: Optional[Union[Callable, str]] = None,
                     module: Optional[ModuleType] = None,
                     filename: Optional[str] = None) -> Iterator[CallInfo]:
        with self._as_started():
            scope = Scope(function, module, filename)
            capture = _CallCapture()
            handle = self.add_callback(scope, capture, ['call', 'return'])
            yield capture.result
            self.remove_callback(handle)

    @contextlib.contextmanager
    def capture_calls(self,
                      function: Optional[Union[Callable, str]] = None,
                      module: Optional[ModuleType] = None,
                      filename: Optional[str] = None) -> Iterator[List[CallInfo]]:
        with self._as_started():
            scope = Scope(function, module, filename)
            capture = _CallCapture(capture_all=True)
            handle = self.add_callback(scope, capture, ['call', 'return'])
            yield capture.result_list
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

            # Extract argument values and locals
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


_DEFAULT_NOPDB = Nopdb()


def capture_call(function: Optional[Union[Callable, str]] = None,
                 module: Optional[ModuleType] = None,
                 filename: Optional[str] = None) -> ContextManager[CallInfo]:
    return _DEFAULT_NOPDB.capture_call(function=function, module=module, filename=filename)


def capture_calls(function: Optional[Union[Callable, str]] = None,
                  module: Optional[ModuleType] = None,
                  filename: Optional[str] = None) -> ContextManager[List[CallInfo]]:
    return _DEFAULT_NOPDB.capture_calls(function=function, module=module, filename=filename)


def _get_code_and_self(fn: Callable) -> CodeType:
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