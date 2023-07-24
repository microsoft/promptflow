# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
from os import PathLike
from pathlib import Path
from typing import IO, AnyStr, Optional, Union, Dict, Any

from ._configuration import _get_flow_operations
from ._ml import load_common, Component
from ._utils import is_arm_id


def load_flow(
    source: Union[str, PathLike, IO[AnyStr]],
    *,
    relative_origin: Optional[str] = None,
    **kwargs,
):
    """Construct a flow object from a yaml file.

    :param source: The local yaml source of a compute. Must be either a
        path to a local file, or an already-open file.
        If the source is a path, it will be open and read.
        An exception is raised if the file does not exist.
        If the source is an open file, the file will be read directly,
        and an exception is raised if the file is not readable.
    :type source: Union[PathLike, str, io.TextIOWrapper]
    :param relative_origin: The origin to be used when deducing
        the relative locations of files referenced in the parsed yaml.
        Defaults to the inputted source's directory if it is a file or file path input.
        Defaults to "./" if the source is a stream input with no name value.
    :type relative_origin: str
    :param params_override: Fields to overwrite on top of the yaml file.
        Format is [{"field1": "value1"}, {"field2": "value2"}]
    :type params_override: List[Dict]
    :return: Loaded flow object.
    :rtype: promptflow.azure.Flow
    """
    from promptflow.azure.entities._flow import Flow

    if is_arm_id(source):
        return source
    return Flow(path=Path(source))


def load_as_component(
    source: Union[str, PathLike, IO[AnyStr]],
    *,
    component_type: str,
    columns_mapping: Dict[str, Union[str, float, int, bool]] = None,
    variant: str = None,
    environment_variables: Dict[str, Any] = None,
    is_deterministic: bool = True,
    **kwargs,
) -> Component:
    """
    Load a flow as a component.
    :param source: Source of the flow. Should be a path to a flow dag yaml file or a flow directory.
    :type source: Union[str, PathLike, IO[AnyStr]]
    :param component_type: Type of the loaded component, support parallel only for now.
    :type component_type: str
    :param variant: Node variant used for the flow.
    :type variant: str
    :param environment_variables: Environment variables to set for the flow.
    :type environment_variables: dict
    :param columns_mapping: Inputs mapping for the flow.
    :type columns_mapping: dict
    :param is_deterministic: Whether the loaded component is deterministic.
    :type is_deterministic: bool
    """
    name = kwargs.pop("name", None)
    version = kwargs.pop("version", None)
    description = kwargs.pop("description", None)
    display_name = kwargs.pop("display_name", None)
    tags = kwargs.pop("tags", None)

    flow = load_flow(
        source=source,
        relative_origin=kwargs.pop("relative_origin", None),
        **kwargs,
    )

    if component_type != "parallel":
        raise NotImplementedError(
            f"Component type {component_type} is not supported yet."
        )

    # TODO: confirm if we should keep flow operations
    flow_operations = _get_flow_operations()
    component = flow_operations.load_as_component(
        flow=flow,
        columns_mapping=columns_mapping,
        variant=variant,
        environment_variables=environment_variables,
        name=name,
        version=version,
        description=description,
        is_deterministic=is_deterministic,
        display_name=display_name,
        tags=tags,
    )
    return component
