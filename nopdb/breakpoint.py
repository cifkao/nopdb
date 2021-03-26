import bdb
import functools
import linecache
import pdb
import sys
from types import CodeType, FrameType
from typing import Any, Callable, List, Optional, Dict, Type, Union, TYPE_CHECKING
import warnings

from .common import NoPdbContextManager
from .nice_debugger import get_nice_debugger
from .scope import Scope

if TYPE_CHECKING:
    from .nopdb import NoPdb


class Breakpoint(NoPdbContextManager):
    """A breakpoint that executes scheduled actions when hit.

    Breakpoints are typically created with :func:`nopdb.breakpoint`. The breakpoint
    object works as a context manager that removes the breakpoint on exit.
    """

    def __init__(
        self,
        nopdb: "NoPdb",
        scope: Scope,
        line: Optional[Union[int, str]] = None,
        cond: Optional[Union[str, bytes, CodeType]] = None,
    ):
        NoPdbContextManager.__init__(
            self, nopdb=nopdb, scope=scope, events=["call", "line"]
        )
        if line is None and scope.function is None:
            raise TypeError("A line must be given if no function is specified")
        if all(x is None for x in [scope.module, scope.file, scope.function]):
            raise TypeError("A module, file or function must be specified")

        self.scope = scope
        self.line = line
        self.cond = cond
        self._todo_list: List[Callable[[FrameType, str, Any], None]] = []

    def eval(
        self,
        expression: Union[str, bytes, CodeType],
        variables: Optional[Dict[str, Any]] = None,
    ) -> list:
        """Schedule an expression to be evaluated at the breakpoint.

        Args:
            expression (str, bytes or ~types.CodeType): A Python expression to be
                evaluated in the breakpoint's scope.
            variables (~typing.Dict[str, ~typing.Any], optional): External variables
                for the expression.

        Returns:
            list:
                An empty list that will later be filled with values of the expression.
        """
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
        self,
        code: Union[str, bytes, CodeType],
        variables: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Schedule some code to be executed at the breakpoint.

        The code will be executed in the breakpoint's scope. Any changes to local
        variables (including newly defined variables) will be preserved in the local
        scope; note that this feature is somewhat experimental and may not work with
        Python implementations other than CPython and PyPy.

        Args:
            code (str, bytes or ~types.CodeType): Python source code to be executed in
                the breakpoint's scope.
            variables (~typing.Dict[str, ~typing.Any], optional): External variables
                for the code. These may not conflict with local variables and will
                *not* be preserved in the local scope.
        """
        self._todo_list.append(
            functools.partial(self._do_exec, code=code, variables=variables)
        )

    def debug(self, debugger_cls: Type[bdb.Bdb] = pdb.Pdb, **kwargs) -> None:
        """Schedule an interactive debugger to be entered at the breakpoint.

        Args:
            debugger_cls (~typing.Type[bdb.Bdb], optional): The debuger class. Defaults
                to :class:`pdb.Pdb`.
            **kwargs: Keyword arguments to pass to the debugger.
        """
        self._todo_list.append(
            functools.partial(self._do_debug, debugger_cls=debugger_cls, kwargs=kwargs)
        )

    @staticmethod
    def _do_eval(
        frame: FrameType,
        event: Union[str, bytes, CodeType],
        arg: Any,
        expression: str,
        results: list,
        variables: Optional[Dict[str, Any]],
    ) -> None:
        f_locals = {**frame.f_locals, **(variables or {})}
        result = eval(expression, dict(frame.f_globals), f_locals)
        results.append(result)

    @staticmethod
    def _do_exec(
        frame: FrameType,
        event: str,
        arg: Any,
        code: Union[str, bytes, CodeType],
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
        update_locals(frame)

    @staticmethod
    def _do_debug(
        frame: FrameType,
        event: str,
        arg: Any,
        debugger_cls: Type[bdb.Bdb],
        kwargs: dict,
    ) -> None:
        debugger = get_nice_debugger(frame, debugger_cls, kwargs)
        sys.settrace(None)
        debugger.set_trace(frame=frame)
        debugger.trace_dispatch(frame, event, arg)

    def _callback(self, frame: FrameType, event: str, arg: Any) -> None:
        # If line is None, break when the function is called
        if self.line is None and event == "call":
            return
        # If line is an int, check the line number
        if isinstance(self.line, int) and frame.f_lineno != self.line:
            return
        # If line is a string, match the line text
        if isinstance(self.line, str):
            line_text = linecache.getline(
                frame.f_code.co_filename, frame.f_lineno, frame.f_globals
            )
            if self.line.strip() != line_text.strip():
                return
        # Evaluate condition if given
        if self.cond is not None and not eval(
            self.cond, frame.f_globals, frame.f_locals
        ):
            return

        for action in self._todo_list:
            action(frame, event, arg)


def get_update_locals():
    # fmt: off
    try:
        import ctypes
        locals_to_fast = ctypes.pythonapi.PyFrame_LocalsToFast

        def update_locals(frame: FrameType):
            locals_to_fast(ctypes.py_object(frame), ctypes.c_int(1))

        return update_locals
    except (ImportError, AttributeError):
        pass

    try:
        import __pypy__  # type: ignore
        return __pypy__.locals_to_fast
    except (ImportError, AttributeError):
        pass
    # fmt: on

    warnings.warn(
        "Unknown Python implementation (not CPython or PyPy). Local variable "
        "assignment probably will not work",
        RuntimeWarning,
    )

    def update_locals(frame: FrameType):
        pass

    return update_locals


update_locals = get_update_locals()
