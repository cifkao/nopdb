import bdb
import ctypes
import functools
import pdb
import sys
from types import CodeType, FrameType
from typing import Any, Callable, List, Optional, Dict, Type, Union

from .common import FriendlyContextManager
from .nice_debugger import get_nice_debugger
from .scope import Scope


class Breakpoint(FriendlyContextManager):
    def __init__(
        self,
        scope: Scope,
        line: Optional[int] = None,
        cond: Optional[Union[str, CodeType]] = None,
    ):
        FriendlyContextManager.__init__(self)
        if line is None and scope.function is None:
            raise RuntimeError("line number must be given if no function is specified")

        self.scope = scope
        self.line = line
        self.cond = cond
        self._todo_list: List[Callable[[FrameType, str, Any], None]] = []

    def eval(self, expression: str, variables: Optional[Dict[str, Any]] = None) -> list:
        results: list = []
        self._todo_list.append(
            functools.partial(
                self._do_eval,
                expression=expression,
                variables=variables,
                results=results,
            )
        )
        return results

    def exec(
        self, code: Union[str, CodeType], variables: Optional[Dict[str, Any]] = None
    ) -> None:
        self._todo_list.append(
            functools.partial(self._do_exec, code=code, variables=variables)
        )

    def debug(self, debugger_cls: Type[bdb.Bdb] = pdb.Pdb, **kwargs):
        self._todo_list.append(
            functools.partial(self._do_debug, debugger_cls=debugger_cls, kwargs=kwargs)
        )

    @staticmethod
    def _do_eval(
        frame: FrameType,
        event: str,
        arg: Any,
        expression: str,
        results: list,
        variables: Optional[Dict[str, Any]],
    ) -> Any:
        f_locals = {**frame.f_locals, **(variables or {})}
        result = eval(expression, dict(frame.f_globals), f_locals)
        results.append(result)

    @staticmethod
    def _do_exec(
        frame: FrameType,
        event: str,
        arg: Any,
        code: Union[str, CodeType],
        variables: Optional[Dict[str, Any]],
    ) -> None:
        if variables is None:
            variables = {}
        conflict_vars = frame.f_locals.keys() & variables.keys()
        if conflict_vars:
            raise RuntimeError(
                "The following external variables conflict with local ones: {}".format(
                    repr(conflict_vars).lstrip("{").rstrip("}")
                )
            )

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

    @staticmethod
    def _do_debug(
        frame: FrameType,
        event: str,
        arg: Any,
        debugger_cls: Type[bdb.Bdb],
        kwargs: dict,
    ):
        debugger = get_nice_debugger(frame, debugger_cls, kwargs)
        sys.settrace(None)
        debugger.set_trace(frame=frame)
        debugger.trace_dispatch(frame, event, arg)

    def _callback(self, frame: FrameType, event: str, arg: Any):
        # If line is None, we break at the first line...
        if self.line is None and frame.f_lineno != frame.f_code.co_firstlineno:
            return
        # ...otherwise we break at the given line
        if self.line is not None and frame.f_lineno != self.line:
            return
        # Evaluate condition if given
        if self.cond is not None and not eval(
            self.cond, frame.f_globals, frame.f_locals
        ):
            return

        for action in self._todo_list:
            action(frame, event, arg)


def _update_locals(frame: FrameType):
    ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(1))
