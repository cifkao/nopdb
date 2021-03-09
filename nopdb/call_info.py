import collections
import inspect
import traceback
from types import FrameType
from typing import Any, Optional, Dict


class CallInfo:

    def __init__(self):
        self.name: Optional[str] = None
        self.file: Optional[str] = None
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


class CallCapture:

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
            result.file = frame.f_code.co_filename
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
