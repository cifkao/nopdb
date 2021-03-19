import abc
import collections
import inspect
import traceback
from types import FrameType
from typing import Any, List, Optional, Dict, TYPE_CHECKING

from .common import NoPdbContextManager

if TYPE_CHECKING:
    from .nopdb import NoPdb
    from .scope import Scope


class CallInfo:
    """Information about a function call.

    Attributes:
        name (str): The name of the function's code object.
        file (str): The path to the file where the function was defined.
        stack (traceback.StackSummary): The call stack.
        args (dict): The function's arguments.
        locals (dict): Local variables on return.
        globals (dict): Global variables on return.
        return_value: The return value.
    """

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
        """Print the call stack."""
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


class CallCapture(BaseCallCapture, NoPdbContextManager, CallInfo):
    def __init__(self, nopdb: "NoPdb", scope: "Scope"):
        BaseCallCapture.__init__(self)
        NoPdbContextManager.__init__(
            self, nopdb=nopdb, scope=scope, events=["call", "return"]
        )
        CallInfo.__init__(self)

    def _update_result(self, result: CallInfo) -> None:
        self.__dict__.update(result.__dict__)


class CallListCapture(BaseCallCapture, NoPdbContextManager, List[CallInfo]):
    def __init__(self, nopdb: "NoPdb", scope: "Scope"):
        BaseCallCapture.__init__(self)
        NoPdbContextManager.__init__(
            self, nopdb=nopdb, scope=scope, events=["call", "return"]
        )
        list.__init__(self)

    def _update_result(self, result: CallInfo) -> None:
        self.append(result)
