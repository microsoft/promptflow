# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import abc
import logging
from os import PathLike
from pathlib import Path
from typing import Union

from promptflow._sdk._constants import LOGGER_NAME
from promptflow.exceptions import ErrorTarget, UserErrorException

from .._constants import DAG_FILE_NAME
from .._errors import ConnectionNotFoundError

logger = logging.getLogger(LOGGER_NAME)


class FlowBase(abc.ABC):
    @classmethod
    # pylint: disable=unused-argument
    def _resolve_cls_and_type(cls, data, params_override):
        """Resolve the class to use for deserializing the data. Return current class if no override is provided.
        :param data: Data to deserialize.
        :type data: dict
        :param params_override: Parameters to override, defaults to None
        :type params_override: typing.Optional[list]
        :return: Class to use for deserializing the data & its "type". Type will be None if no override is provided.
        :rtype: tuple[class, typing.Optional[str]]
        """
        return cls, "flow"


class Flow(FlowBase):
    def __init__(
        self,
        code: str,
        **kwargs,
    ):
        self._code = Path(code)
        path = kwargs.pop("path", None)
        self._path = Path(path) if path else None
        super().__init__(**kwargs)

    @property
    def code(self) -> Path:
        return self._code

    @code.setter
    def code(self, value: Union[str, PathLike, Path]):
        self._code = value

    @property
    def path(self) -> Path:
        flow_file = self._path or self.code / DAG_FILE_NAME
        if not flow_file.is_file():
            raise UserErrorException(
                "The directory does not contain a valid flow.",
                target=ErrorTarget.CONTROL_PLANE_SDK,
            )
        return flow_file

    @classmethod
    def load(
        cls,
        source: Union[str, PathLike],
        **kwargs,
    ):
        source_path = Path(source)
        if not source_path.exists():
            raise Exception(f"Source {source_path.absolute().as_posix()} does not exist")
        if source_path.is_dir() and (source_path / DAG_FILE_NAME).is_file():
            return cls(code=source_path.absolute().as_posix(), **kwargs)
        elif source_path.is_file() and source_path.name == DAG_FILE_NAME:
            # TODO: for file, we should read the yaml to get code and set path to source_path
            return cls(code=source_path.absolute().parent.as_posix(), **kwargs)

        raise Exception("source must be a directory or a flow.dag.yaml file")

    def _init_executable(self, tuning_node=None, variant=None):
        from promptflow._sdk.operations._run_submitter import variant_overwrite_context

        # TODO: check if there is potential bug here
        # this is a little wired:
        # 1. the executable is created from a temp folder when there is additional includes
        # 2. after the executable is returned, the temp folder is deleted
        with variant_overwrite_context(self.code, tuning_node, variant) as flow:
            from promptflow.contracts.flow import Flow as ExecutableFlow

            return ExecutableFlow.from_yaml(flow_file=flow.path, working_dir=flow.code)

    @classmethod
    def _get_local_connections(cls, executable):
        from promptflow._sdk._pf_client import PFClient

        connection_names = executable.get_connection_names()
        local_client = PFClient()
        result = {}
        for n in connection_names:
            try:
                conn = local_client.connections.get(name=n, with_secrets=True)
                result[n] = conn._to_execution_connection_dict()
            except ConnectionNotFoundError:
                # ignore when connection not found since it can be configured with env var.
                raise Exception(f"Connection {n!r} required for flow {executable.name!r} is not found.")
        return result
