# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import abc
import logging
import sys
from contextlib import contextmanager
from types import CodeType, FrameType, FunctionType, MethodType
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

from bytecode import Bytecode, Instr, Label

logger = logging.getLogger(__name__)


class PersistentLocalsFunctionBuilder(abc.ABC):
    errors = {
        "not_callable": "func must be a function or a callable object",
        "conflict_argument": "Injected param name __self conflicts with function args {args}",
        "not_all_template_separators_used": "Not all template separators are used, "
        "please switch to a compatible version of Python.",
        "invalid_template": "Provided template functions are invalid in current environment, "
        "please switch to a compatible version (3.9 e.g.) of Python "
        "and/or check template functions.",
    }
    injected_param = "__self"

    @classmethod
    def make_error(cls, error_name: str, **kwargs) -> str:
        """Make error message with error_name and kwargs.

        :param error_name: A key from :attr:`~PersistentLocalsFunctionBuilder.errors`
        :type error_name: str
        :return: Formatted error message
        :rtype: str
        """
        return cls.errors[error_name].format(**kwargs)

    @abc.abstractmethod
    def _call(self, func, _all_kwargs) -> Tuple[Any, dict]:
        raise NotImplementedError()

    def call(self, func, _all_kwargs) -> Tuple[Any, dict]:
        """Get outputs and locals in calling func with _all_kwargs. Locals will be used to update node variable names.

        :param func: The function to execute.
        :type func: Union[FunctionType, MethodType]
        :param _all_kwargs: All kwargs to call self.func.
        :type _all_kwargs: typing.Dict[str, typing.Any]
        :return: A tuple of outputs and locals.
        :rtype: typing.Tuple[typing.Any, typing.Dict]
        """
        if isinstance(func, (FunctionType, MethodType)):
            pass
        elif hasattr(func, "__call__"):
            func = func.__call__
        else:
            raise TypeError(self.make_error("not_callable"))

        if self.injected_param in func.__code__.co_varnames:
            raise ValueError(self.make_error("conflict_argument", args=list(func.__code__.co_varnames)))

        return self._call(func, _all_kwargs)


class PersistentLocalsFunctionProfilerBuilder(PersistentLocalsFunctionBuilder):
    @staticmethod
    @contextmanager
    # pylint: disable-next=docstring-missing-return,docstring-missing-rtype
    def _replace_sys_profiler(profiler: Callable[[FrameType, str, Any], None]) -> Iterable[None]:
        """A context manager which replaces sys profiler to given profiler.

        :param profiler: The profile function.
            See https://docs.python.org/3/library/sys.html#sys.setprofile for more information
        :type profiler: Callable[[FrameType, str, Any], None]
        """
        original_profiler = sys.getprofile()
        sys.setprofile(profiler)
        try:
            yield
        finally:
            sys.setprofile(original_profiler)

    @staticmethod
    def _get_func_variable_tracer(
        _locals_data: Dict[str, Any], func_code: CodeType
    ) -> Callable[[FrameType, str, Any], None]:
        """Get a tracer to trace variable names in function.

        :param _locals_data: A dict to save locals data.
        :type _locals_data: dict
        :param func_code: An code object to compare if current frame is inside user function.
        :type func_code: CodeType
        :return: A tracing function
        :rtype: Callable[[FrameType, str, Any], None]
        """

        def tracer(frame: FrameType, event: str, arg: Any) -> None:  # pylint: disable=unused-argument
            if frame.f_code == func_code and event == "return":
                # Copy the locals of user's dsl function when it returns.
                _locals_data.update(frame.f_locals.copy())

        return tracer

    def _call(self, func, _all_kwargs):
        _locals = {}
        func_variable_profiler = self._get_func_variable_tracer(_locals, func.__code__)
        with self._replace_sys_profiler(func_variable_profiler):
            outputs = func(**_all_kwargs)
        return outputs, _locals


class PersistentLocalsFunction(object):
    def __init__(
        self,
        _func,
        *,
        _self: Optional[Any] = None,
        skip_locals: Optional[List[str]] = None,
    ):
        """
        :param _func: The function to be wrapped.
        :param _self: If original func is a method, _self should be provided, which is the instance of the method.
        :param skip_locals: A list of local variables to skip when saving the locals.
        """
        self._locals = {}
        self._self = _self
        # make function an instance method
        self._func = MethodType(_func, self)
        self._skip_locals = skip_locals

    def __call__(__self, *args, **kwargs):  # pylint: disable=no-self-argument
        # Use __self in case self is also passed as a named argument in kwargs
        __self._locals.clear()
        try:
            if __self._self:
                return __self._func(__self._self, *args, **kwargs)  # pylint: disable=not-callable
            return __self._func(*args, **kwargs)  # pylint: disable=not-callable
        finally:
            # always pop skip locals even if exception is raised in user code
            if __self._skip_locals is not None:
                for skip_local in __self._skip_locals:
                    __self._locals.pop(skip_local, None)

    @property
    def locals(self):
        return self._locals


def _source_template_func(mock_arg):
    return mock_arg


def _target_template_func(__self, mock_arg):
    try:
        return mock_arg
    finally:
        __self._locals = locals().copy()  # pylint: disable=protected-access


class PersistentLocalsFunctionBytecodeBuilder(PersistentLocalsFunctionBuilder):
    _template_separators = []
    _template_separators_before_body = []
    _template_separators_after_body = []
    _template_body = []
    _template_tail = None
    __initialized = False

    @classmethod
    def _split(cls, instructions, separator, n=-1):
        cur_start, index, result = 0, 0, []
        while index < len(instructions) - len(separator) + 1:
            if cls.is_instr_equal(instructions[index], separator[0]):
                for i, template_body_instruction in enumerate(separator):
                    if not cls.is_instr_equal(instructions[index + i], template_body_instruction):
                        break
                else:
                    result.append(instructions[cur_start:index])
                    cur_start = index + len(separator)
                    index += len(separator)
                    if len(result) == n:
                        break
                    continue
            index += 1
        result.append(instructions[cur_start:])
        if n != -1 and len(result) != n:
            msg = "can't split instructions into {} pieces with provided separators".format(n)
            raise ValueError(msg)
        return result

    @classmethod
    def _class_init_impl(cls):  # pylint: disable=unused-argument
        """Override this method to implement different template matching algorithm."""
        cls._template_separators_before_body, cls._template_separators_after_body = cls._split(
            cls.get_instructions(_source_template_func),
            separator=cls._get_mock_body_instructions(),
            n=2,
        )
        # use None to indicate the body
        cls._template_separators = cls._template_separators_before_body + [None] + cls._template_separators_after_body

        cls._template_body = cls._split_instructions_based_on_template(
            cls.get_instructions(_target_template_func),
            remove_mock_body=True,
        )
        cls._template_tail = cls._template_body.pop()
        if len(cls._template_body) != len(cls._template_body):
            raise ValueError(cls.make_error("invalid_template"))

    @classmethod
    def __class_init(cls):
        if cls.__initialized:
            return

        cls._class_init_impl()

        cls.__initialized = True

    def __init__(self):
        self.__class_init()

    # region methods depending on package bytecode
    @classmethod
    def get_instructions(cls, func):
        return list(Bytecode.from_code(func.__code__))

    @classmethod
    def is_instr_equal(cls, instr1: Instr, instr2: Instr) -> bool:
        if instr1 is None and instr2 is None:
            return True
        if instr1 is None or instr2 is None:
            return False
        if instr1.__class__ != instr2.__class__:
            return False
        if isinstance(instr1, Instr):
            if isinstance(instr1.arg, Label) and isinstance(instr2.arg, Label):
                return True
            return instr1.opcode == instr2.opcode and instr1.arg == instr2.arg
        # objects like Label and TryBegin
        return True

    @classmethod
    def is_instructions_equal(cls, instructions1: List[Instr], instructions2: List[Instr]) -> bool:
        if len(instructions1) != len(instructions2):
            return False
        for instr1, instr2 in zip(instructions1, instructions2):
            if not cls.is_instr_equal(instr1, instr2):
                return False
        return True

    def _create_code(self, instructions: List[Instr], base_func: Union[FunctionType, MethodType]) -> CodeType:
        """Create the base bytecode for the function to be generated.

        Will keep information of the function, such as name, globals, etc., but skip all instructions.

        :param instructions: The list of instructions. Used to replace the instructions in base_func
        :type instructions: List[Instr]
        :param base_func: A function that provides base metadata (name, globals, etc...). Instructions will not
            be kept
        :type base_func: Union[FunctionType, MethodType]
        :return: Generated code
        :rtype: CodeType
        """
        fn_code = Bytecode.from_code(base_func.__code__)
        fn_code.clear()
        fn_code.extend(instructions)
        fn_code.argcount += 1
        fn_code.argnames.insert(0, self.injected_param)
        return fn_code.to_code()

    @classmethod
    def _get_mock_body_instructions(cls):
        return [Instr("LOAD_FAST", "mock_arg")]

    # endregion

    @classmethod
    def _get_pieces(cls, instructions: List[Instr], separators: List[Instr]) -> List[List[Instr]]:
        """Split the instructions into pieces by the separators.
        Note that separators is a list of instructions. For example,
        instructions: [I3, I1, I2, I3, I1, I3, I1, I2, I3]
        separators: [I1, I2]
        result: [[I3], [I3, I1, I3], [I3]]

        :param instructions: The list of instructions to split
        :type instructions: List[instr]
        :param separators: The sequence of Instr to use as a delimiter
        :type separators: List[Instr]
        :return: A sublists of instructions that were delimited by separators
        :rtype: List[List[Instr]]
        """
        separator_iter = iter(separators)

        def get_next_separator():
            try:
                while True:
                    separator = next(separator_iter)
                    if separator is not None:
                        return separator
            except StopIteration:
                return None

        pieces = []
        last_piece = []
        cur_separator = get_next_separator()
        for instr in instructions:
            if cls.is_instr_equal(instr, cur_separator):
                # skip the separator
                pieces.append(last_piece)
                cur_separator = get_next_separator()
                last_piece = []
            else:
                last_piece.append(instr)
        pieces.append(last_piece)

        if cur_separator is not None:
            raise ValueError(cls.make_error("not_all_template_separators_used"))

        return pieces

    @classmethod
    def _split_instructions_based_on_template(
        cls,
        instructions: List[Instr],
        *,
        remove_mock_body: bool = False,
    ) -> List[List[Instr]]:
        """Split instructions into several pieces by separators.
        For example, in Python 3.11, the template source instructions will be:

        .. code-block:: python

            [
                Instr('RESUME', 0),  # initial instruction shared by all functions
                Instr('LOAD_FAST', 'mock_arg'),  # the body execution instruction
                Instr('RETURN_VALUE'),  # the return instruction shared by all functions
            ]

        Then the separators before body will be:

        .. code-block:: python

            [
                Instr('RESUME', 0),
            ]

        And the separators after body will be:

        .. code-block:: python

            [
                Instr('RETURN_VALUE'),
            ]

        For passed in instructions, we will split them with separators from beginning (the first RESUME) and
        with reversed_separators from end (the last RETURN_VALUE).

        :param instructions: The instructions to split
        :type instructions: List[instr]
        :keyword remove_mock_body: Whether to remove the mock body. Defaults to False
        :paramtype remove_mock_body: bool
        :return: The split instructions
        :rtype: List[List[Instr]]
        """
        if remove_mock_body:
            # this parameter should be set as True only when processing the template target function,
            # when we should ignore the mock body
            pieces = cls._get_pieces(
                instructions, cls._template_separators_before_body + cls._get_mock_body_instructions()
            )
        else:
            pieces = cls._get_pieces(instructions, cls._template_separators_before_body)

        reversed_pieces = cls._get_pieces(reversed(pieces.pop()), reversed(cls._template_separators_after_body))

        while reversed_pieces:
            pieces.append(list(reversed(reversed_pieces.pop())))

        return pieces

    def _build_instructions(self, func: Union[FunctionType, MethodType]) -> List[Instr]:
        generated_instructions = []

        for template_piece, input_piece, separator in zip(
            self._template_body,
            self._split_instructions_based_on_template(self.get_instructions(func)),
            self._template_separators,
        ):
            generated_instructions.extend(template_piece)
            generated_instructions.extend(input_piece)
            if separator is not None:
                generated_instructions.append(separator)
        generated_instructions.extend(self._template_tail)
        return generated_instructions

    def _build_func(self, func: Union[FunctionType, MethodType]) -> PersistentLocalsFunction:
        """Build a persistent locals function from the given function. Use bytecode injection to add try...finally
        statement around code to persistent the locals in the function.

        It will change the func bytecode in this way:

        .. code-block:: python

            def func(__self, *func_args):
                try:
                   the func code...
                finally:
                   __self.locals = locals().copy()

        You can get the locals in func by this code:

        .. code-block:: python

            builder = PersistentLocalsFunctionBuilder()
            persistent_locals_func = builder.build(your_func)
            # Execute your func
            result = persistent_locals_func(*args)
            # Get the locals in the func.
            func_locals = persistent_locals_func.locals

        :param func: The function to modify
        :type func: Union[FunctionType, MethodType]
        :return: The built persistent locals function
        :rtype: PersistentLocalsFunction
        """
        generated_func = FunctionType(
            self._create_code(self._build_instructions(func), func),
            func.__globals__,
            func.__name__,
            func.__defaults__,
            func.__closure__,
        )
        return PersistentLocalsFunction(
            generated_func,
            _self=func.__self__ if isinstance(func, MethodType) else None,
            skip_locals=[self.injected_param],
        )

    def _call(self, func, _all_kwargs) -> Tuple[Any, dict]:
        persistent_func = self._build_func(func)
        outputs = persistent_func(**_all_kwargs)
        return outputs, persistent_func.locals


def get_outputs_and_locals(func: Callable, _all_kwargs):
    """Get outputs and locals from func. Locals will be used to update node variable names.

    :param func: The function to execute.
    :type func: Union[FunctionType, MethodType]
    :param _all_kwargs: All kwargs to call self.func.
    :type _all_kwargs: typing.Dict[str, typing.Any]
    :return: A tuple of outputs and locals.
    :rtype: typing.Tuple[typing.Dict, typing.Dict]
    """
    return PersistentLocalsFunctionBytecodeBuilder().call(func, _all_kwargs)
