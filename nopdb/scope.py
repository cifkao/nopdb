import inspect
from os import PathLike
import pathlib
from types import CodeType, FrameType, ModuleType, MethodType
from typing import Any, Callable, Optional, Tuple, Union


class Scope:
    def __init__(
        self,
        function: Optional[Union[Callable, str]] = None,
        module: Optional[ModuleType] = None,
        file: Optional[Union[str, PathLike]] = None,
        unwrap: bool = True,
    ):
        self.function = function
        self.module = module

        self._fn_name, self._fn_code, self._fn_self = None, None, None
        if isinstance(function, str):
            self._fn_name = function
        elif function is not None:
            self._fn_code, self._fn_self = _get_code_and_self(function, unwrap=unwrap)

        self.file: Optional[Union[str, pathlib.Path]] = None
        if isinstance(file, PathLike):
            self.file = pathlib.Path(file).resolve()
        else:
            self.file = file

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

        if self.file is not None:
            file = frame.f_code.co_filename
            if file.endswith(">"):
                # Special filename: exact match
                if file != self.file:
                    return False
            elif isinstance(self.file, pathlib.Path):
                if pathlib.Path(file).resolve() != self.file:
                    return False
            elif not pathlib.Path(file).resolve().match(self.file):
                return False

        return True


def _get_code_and_self(fn: Callable, unwrap: bool) -> Tuple[CodeType, Any]:
    # First find the actual Python function that implements the callable, if possible.
    # Then if unwrap is True, try to follow the wrapper chain, assuming that the
    # wrappers are well-behaved (as opposed to, say, a Python function wrapping a
    # built-in). If not, we raise an error.

    def _unwrap(f):
        if unwrap:
            f = inspect.unwrap(f)
        return f

    exc: Optional[Exception] = None
    try:
        # Bound method
        if inspect.ismethod(fn):
            assert isinstance(fn, MethodType)
            return _unwrap(fn.__func__).__code__, fn.__self__
        # Regular function
        if inspect.isfunction(fn):
            return _unwrap(fn).__code__, None
        # Instance of a class that defines a __call__ method
        if hasattr(fn, "__class__") and hasattr(fn.__class__, "__call__"):
            return _unwrap(fn.__class__.__call__).__code__, fn
    except AttributeError as _exc:
        exc = _exc

    raise TypeError(
        "Could not find the code for {!r}. "
        "Please provide a pure Python callable".format(fn)
    ) from exc
