# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import IO, AnyStr, Optional, Union

from dotenv import dotenv_values

from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.yaml_utils import load_yaml
from promptflow.exceptions import UserErrorException

from ._errors import MultipleExperimentTemplateError, NoExperimentTemplateError
from .entities import Run
from .entities._connection import CustomConnection, _Connection
from .entities._experiment import Experiment, ExperimentTemplate
from .entities._flows import Flow

logger = get_cli_sdk_logger()


def load_common(
    cls,
    source: Union[str, PathLike, IO[AnyStr]],
    relative_origin: str = None,
    params_override: Optional[list] = None,
    **kwargs,
):
    """Private function to load a yaml file to an entity object.

    :param cls: The entity class type.
    :type cls: type[Resource]
    :param source: A source of yaml.
    :type source: Union[str, PathLike, IO[AnyStr]]
    :param relative_origin: The origin of to be used when deducing
        the relative locations of files referenced in the parsed yaml.
        Must be provided, and is assumed to be assigned by other internal
        functions that call this.
    :type relative_origin: str
    :param params_override: _description_, defaults to None
    :type params_override: list, optional
    """
    if relative_origin is None:
        if isinstance(source, (str, PathLike)):
            relative_origin = source
        else:
            try:
                relative_origin = source.name
            except AttributeError:  # input is a stream or something
                relative_origin = "./"

    params_override = params_override or []
    yaml_dict = load_yaml(source)

    logger.debug(f"Resolve cls and type with {yaml_dict}, params_override {params_override}.")
    # pylint: disable=protected-access
    cls, type_str = cls._resolve_cls_and_type(data=yaml_dict, params_override=params_override)

    try:
        return cls._load(
            data=yaml_dict,
            yaml_path=relative_origin,
            params_override=params_override,
            **kwargs,
        )
    except Exception as e:
        raise UserErrorException(f"Load entity error: {e}", privacy_info=[str(e)]) from e


def load_flow(
    source: Union[str, PathLike, IO[AnyStr]],
    **kwargs,
) -> Flow:
    """Load flow from YAML file.

    :param source: The local yaml source of a flow. Must be a path to a local file.
        If the source is a path, it will be open and read.
        An exception is raised if the file does not exist.
    :type source: Union[PathLike, str]
    :return: A Flow object
    :rtype: ~promptflow._sdk.entities._flows.Flow
    """
    return Flow.load(source, **kwargs)


def load_run(
    source: Union[str, PathLike, IO[AnyStr]],
    params_override: Optional[list] = None,
    **kwargs,
) -> Run:
    """Load run from YAML file.

    :param source: The local yaml source of a run. Must be a path to a local file.
        If the source is a path, it will be open and read.
        An exception is raised if the file does not exist.
    :type source: Union[PathLike, str]
    :param params_override: Fields to overwrite on top of the yaml file.
        Format is [{"field1": "value1"}, {"field2": "value2"}]
    :type params_override: List[Dict]
    :return: A Run object
    :rtype: Run
    """
    data = load_yaml(source=source)
    return Run._load(data=data, yaml_path=source, params_override=params_override, **kwargs)


def load_connection(
    source: Union[str, PathLike, IO[AnyStr]],
    **kwargs,
):
    """Load connection from YAML file or .env file.

    :param source: The local yaml source of a connection or .env file. Must be a path to a local file.
        If the source is a path, it will be open and read.
        An exception is raised if the file does not exist.
    :type source: Union[PathLike, str]
    :return: A Connection object
    :rtype: Connection
    """
    if Path(source).name.endswith(".env"):
        return _load_env_to_connection(source, **kwargs)
    return load_common(_Connection, source, **kwargs)


def _load_env_to_connection(
    source,
    params_override: Optional[list] = None,
    **kwargs,
):
    source = Path(source)
    name = next((_dct["name"] for _dct in params_override if "name" in _dct), None)
    if not name:
        raise UserErrorException(message_format="Please specify --name when creating connection from .env.")
    if not source.exists():
        e = FileNotFoundError(f"File {source.absolute().as_posix()!r} not found.")
        raise UserErrorException(str(e), privacy_info=[source.absolute().as_posix()]) from e
    try:
        data = dict(dotenv_values(source))
        if not data:
            # Handle some special case dotenv returns empty with no exception raised.
            e = ValueError(
                f"Load nothing from dotenv file {source.absolute().as_posix()!r}, "
                "please make sure the file is not empty and readable."
            )
            raise UserErrorException(str(e), privacy_info=[source.absolute().as_posix()]) from e
        return CustomConnection(name=name, secrets=data)
    except Exception as e:
        raise UserErrorException(f"Load entity error: {e}", privacy_info=[str(e)]) from e


def _load_experiment_template(
    source: Union[str, PathLike, IO[AnyStr]],
    **kwargs,
):
    """Load experiment template from YAML file.

    :param source: The local yaml source of an experiment template. Must be a path to a local file.
        If the source is a path, it will be open and read.
        An exception is raised if the file does not exist.
    :type source: Union[PathLike, str]
    :return: An ExperimentTemplate object
    :rtype: ExperimentTemplate
    """
    source_path = Path(source)
    if source_path.is_dir():
        target_yaml_list = []
        for item in list(source_path.iterdir()):
            if item.name.endswith(".exp.yaml"):
                target_yaml_list.append(item)
        if len(target_yaml_list) > 1:
            raise MultipleExperimentTemplateError(
                f"Multiple experiment template files found in {source_path.resolve().absolute().as_posix()}, "
                f"please specify one."
            )
        if not target_yaml_list:
            raise NoExperimentTemplateError(
                f"Experiment template file not found in {source_path.resolve().absolute().as_posix()}."
            )
        source_path = target_yaml_list[0]
    if not source_path.exists():
        raise NoExperimentTemplateError(
            f"Experiment template file {source_path.resolve().absolute().as_posix()} not found."
        )
    return load_common(ExperimentTemplate, source=source_path)


def _load_experiment(
    source: Union[str, PathLike, IO[AnyStr]],
    **kwargs,
):
    """
    Load experiment from YAML file.

    :param source: The local yaml source of an experiment. Must be a path to a local file.
        If the source is a path, it will be open and read.
        An exception is raised if the file does not exist.
    :type source: Union[PathLike, str]
    :return: An Experiment object
    :rtype: Experiment
    """
    source = Path(source)
    absolute_path = source.resolve().absolute().as_posix()
    if not source.exists():
        raise NoExperimentTemplateError(f"Experiment file {absolute_path} not found.")
    experiment = load_common(Experiment, source, **kwargs)
    return experiment
