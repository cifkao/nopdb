import abc
import collections
import inspect
import traceback
from types import FrameType
from typing import Any, List, Optional, Dict

from .common import FriendlyContextManager


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
        return "{}(name={!r}, args={}({}), return_value={!r})".format(
            type(self).__name__,
            self.name,
            type(self.args).__name__,
            ", ".join("{}={!r}".format(k, v) for k, v in (self.args or {}).items()),
            self.return_value,
        )

    def print_stack(self, file=None) -> None:
        if self.stack is not None:
            for line in self.stack.format():
                print(line, end="", file=file)


class BaseCallCapture:
    def __init__(self):
        self._result_by_frame: Dict[FrameType, CallInfo] = {}

    def _callback(self, frame: FrameType, event: str, arg: Any):
        if frame not in self._result_by_frame:
            self._result_by_frame[frame] = CallInfo()
        result = self._result_by_frame[frame]

        if event == "call":
            result.name = frame.f_code.co_name
            result.file = frame.f_code.co_filename
            result.stack = traceback.extract_stack(frame)
            result.return_value = None

            # Extract argument values
            arg_info = inspect.getargvalues(frame)
            result.args = collections.OrderedDict(
                [
                    (name, arg_info.locals[name])
                    for name in arg_info.args
                    if name in arg_info.locals
                ]
            )
        elif event == "return":
            result.locals = frame.f_locals
            result.globals = frame.f_globals
            result.return_value = arg

            # This frame is done, save the result
            del self._result_by_frame[frame]
            self._update_result(result)

    @abc.abstractmethod
    def _update_result(self, result: CallInfo) -> None:
        pass


class CallCapture(BaseCallCapture, FriendlyContextManager, CallInfo):
    def __init__(self):
        BaseCallCapture.__init__(self)
        FriendlyContextManager.__init__(self)
        CallInfo.__init__(self)

    def _update_result(self, result: CallInfo) -> None:
        self.__dict__.update(result.__dict__)


class CallListCapture(BaseCallCapture, FriendlyContextManager, List[CallInfo]):
    def __init__(self):
        BaseCallCapture.__init__(self)
        FriendlyContextManager.__init__(self)
        List.__init__(self)

    def _update_result(self, result: CallInfo) -> None:
        self.append(result)
