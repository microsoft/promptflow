# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from functools import wraps
from typing import Any, Callable, Optional, ParamSpec, TypeVar, Union, overload

from promptflow._sdk.entities._experiment import Experiment, NodeBase

from ._func_utils import get_outputs_and_locals

T = TypeVar("T")
P = ParamSpec("P")


@overload
def experiment(
    func: None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    **kwargs: Any,
) -> Callable[[Callable[P, T]], Callable[P, Experiment]]:
    ...


@overload
def experiment(
    func: Callable[P, T],
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    **kwargs: Any,
) -> Callable[P, Experiment]:
    ...


def experiment(
    func: Optional[Callable[P, T]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    **kwargs: Any,
) -> Union[Callable[[Callable[P, T]], Callable[P, Experiment]], Callable[P, Experiment]]:
    """Build an experiment with nodes defined in this function.

    :param func: The user pipeline function to be decorated.
    :type func: types.FunctionType
    :keyword name: The name of experiment, defaults to function name.
    :paramtype name: str
    :keyword description: The description of the experiment.
    :paramtype description: str
    :return: Either
      * A decorator, if `func` is None
      * The decorated `func`
    :rtype: Union[
        Callable[[Callable], Callable[..., ~promptflow._sdk.entities._experiment.Experiment]],
        Callable[P, ~promptflow._sdk.entities._experiment.Experiment]
      ]
    """

    def decorator(func: Callable[P, T]) -> Callable:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Experiment:
            outputs, _locals = get_outputs_and_locals(func, kwargs)
            nodes = _resolve_nodes(_locals)
            data, inputs = _resolve_parameter_from_func(func, args, kwargs)
            return Experiment(
                name=name or func.__name__,
                description=description,
                nodes=nodes,
                data=data,
                input=inputs,
                **kwargs,
            )

        return wrapper

    # enable use decorator without "()" if all arguments are default values
    if func is not None:
        return decorator(func)
    return decorator


def _resolve_nodes(_locals: dict) -> list:
    """Resolve experiment nodes from locals."""
    nodes = []
    for name, value in _locals.items():
        if isinstance(value, NodeBase):
            value.name = name if value.name is None else value.name
            nodes.append(value)
    return nodes


def _resolve_parameter_from_func(func: Callable[P, T], args: P.args, kwargs: P.kwargs) -> tuple:
    """Resolve experiment data and inputs from function arguments."""
    data = {}
    inputs = {}
    for arg_name, arg_value in kwargs.items():
        if arg_name in func.__annotations__:
            if arg_name in func.__code__.co_varnames:
                inputs[arg_name] = arg_value
            else:
                data[arg_name] = arg_value
