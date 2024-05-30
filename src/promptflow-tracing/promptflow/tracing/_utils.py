import os
import re
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Dict

from .contracts.iterator_proxy import AsyncIteratorProxy, IteratorProxy


def is_tracing_disabled():
    return os.environ.get("PF_DISABLE_TRACING", "false").lower() == "true"


def serialize(value: object, remove_null: bool = False, serialization_funcs: Dict[type, Callable] = None) -> dict:
    if serialization_funcs:
        for cls, f in serialization_funcs.items():
            if isinstance(value, cls):
                return f(value)
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [serialize(v, remove_null, serialization_funcs) for v in value]
    if isinstance(value, (IteratorProxy, AsyncIteratorProxy)):
        # TODO: The current implementation of the serialize function is not self-explanatory, as value.items is mutable
        # whereas the serialize function should deal with a fixed object. We should rename the function to
        # to_serializable to better reflect its purpose.
        return value.items
    try:
        from promptflow.contracts.tool import ConnectionType

        #  Note that custom connection check should before dict check
        if ConnectionType.is_connection_value(value):
            return ConnectionType.serialize_conn(value)
    except ImportError:
        pass
    if isinstance(value, dict):
        return {k: serialize(v, remove_null, serialization_funcs) for k, v in value.items()}
    if is_dataclass(value):
        if hasattr(value, "serialize"):
            result = value.serialize()
        else:
            result = {
                f.name: serialize(getattr(value, f.name), remove_null, serialization_funcs) for f in fields(value)
            }
        if not remove_null:
            return result
        null_keys = [k for k, v in result.items() if v is None]
        for k in null_keys:
            result.pop(k)
        return result
    try:
        from pydantic import BaseModel

        if isinstance(value, BaseModel):  # Handle pydantic model, which is used in langchain
            return value.dict()
    except ImportError:
        # Ignore ImportError if pydantic is not installed
        pass
    return value


def get_input_names_for_prompt_template(template_str):
    try:
        # We need to parse jinja template only when the promptflow is installed and run flow with PromptTemplate
        # type input, so using try-catch to avoid the dependency of jinja2 when it's not needed.
        from jinja2 import Environment, meta
    except ImportError:
        return []

    input_names = []
    env = Environment()
    template = env.parse(template_str)
    input_names.extend(sorted(meta.find_undeclared_variables(template), key=lambda x: template_str.find(x)))

    # currently we only support image type
    pattern = r"\!\[(\s*image\s*)\]\(\{\{\s*([^{}]+)\s*\}\}\)"
    matches = re.finditer(pattern, template_str)
    for match in matches:
        input_names.append(match.group(2).strip())

    return input_names


def get_prompt_param_name_from_func(f):
    """Get the param name of prompt template on provider."""

    try:
        from promptflow.contracts.types import PromptTemplate

        return next(
            (k for k, annotation in getattr(f, "__annotations__", {}).items() if annotation == PromptTemplate), None
        )
    except ImportError:
        return None
