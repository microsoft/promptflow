# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import abc
import base64
import hashlib
import logging
import shutil
from os import PathLike
from pathlib import Path
from typing import Union

import yaml

from promptflow._sdk._constants import LOGGER_NAME
from promptflow.exceptions import ErrorTarget, UserErrorException

from .._constants import DAG_FILE_NAME, LOCAL_MGMT_DB_PATH
from .._utils import PromptflowIgnoreFile, render_jinja_template
from .._vendor import get_upload_files_from_folder
from ..exceptions import ConnectionNotFoundError

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
                result[n] = conn.to_execution_connection_dict()
            except ConnectionNotFoundError:
                # ignore when connection not found since it can be configured with env var.
                raise Exception(f"Connection {n!r} required for flow {executable.name!r} is not found.")
        return result


class FlowProtected(Flow):
    """
    Not sure if we need this class.
    We need to hide many "protected" methods in Flow, which will be frequently referenced in other classes.
    So one way is to maintain another protected class, which can be referenced in SDK but won't be
    exposed to users.
    """

    def _build_environment_config(self):
        flow_info = yaml.safe_load(self.path.read_text())
        # standard env object:
        # environment:
        #   image: xxx
        #   conda_file: xxx
        #   python_requirements_txt: xxx
        #   setup_sh: xxx
        # TODO: deserialize dag with structured class here to avoid using so many magic strings
        env_obj = flow_info.get("environment", {})
        from promptflow import __version__

        # version 0.0.1 is the dev version of promptflow
        env_obj["sdk_version"] = __version__ if __version__ != "0.0.1" else None

        if not env_obj.get("python_requirements_txt", None) and (Path(self.code) / "requirements.txt").is_file():
            env_obj["python_requirements_txt"] = "requirements.txt"

        env_obj["conda_env_name"] = "promptflow-serve"
        if "conda_file" in env_obj:
            conda_file = Path(self.code) / env_obj["conda_file"]
            if conda_file.is_file():
                conda_obj = yaml.safe_load(conda_file.read_text())
                if "name" in conda_obj:
                    env_obj["conda_env_name"] = conda_obj["name"]

        return env_obj

    @classmethod
    def _copy_tree(cls, source: Path, target: Path, render_context: dict = None):
        def is_template(path: str):
            return path.endswith(".jinja2")

        for source_path, target_path in get_upload_files_from_folder(
            path=source,
            ignore_file=PromptflowIgnoreFile(prompt_flow_path=source),
        ):
            (target / target_path).parent.mkdir(parents=True, exist_ok=True)
            if render_context is None or not is_template(source_path):
                shutil.copy(source_path, target / target_path)
            else:
                (target / target_path[: -len(".jinja2")]).write_text(
                    render_jinja_template(source_path, **render_context)
                )

    def _migrate_connections(self, output_dir: Path, encryption_key: str):
        executable = self._init_executable()
        connections = self._get_local_connections(executable)
        for connection_name in executable.get_connection_names():
            if connection_name not in connections:
                logger.info(
                    f"Connection {connection_name} is not found in local, skip migration. "
                    f"Service call will fail before it has been manually created inside docker "
                    f"container via `pf connection create`."
                )

        # TODO: refactor this
        # Important: this operation is very dangerous and won't support multiprocess,
        # we should only enable this on cli for now
        from promptflow._sdk._orm.session import mgmt_db_rebase
        from promptflow._sdk._pf_client import PFClient
        from promptflow._sdk.entities._connection import _Connection

        with mgmt_db_rebase((output_dir / "connections.sqlite").resolve(), customized_encryption_key=encryption_key):
            local_client = PFClient()
            for connection_name, connection_execution_dict in connections.items():
                local_client.connections.create_or_update(
                    _Connection.from_execution_connection_dict(name=connection_name, data=connection_execution_dict),
                    encryption_key=encryption_key,
                )

    def _export_to_docker(self, output_dir: Path, migration_secret: str):
        environment_config = self._build_environment_config()

        # TODO: make below strings constants
        self._copy_tree(
            source=Path(__file__).parent.parent / "data" / "docker",
            target=output_dir,
            render_context={
                "env": environment_config,
                "local_db_rel_path": LOCAL_MGMT_DB_PATH.relative_to(Path.home()).as_posix(),
            },
        )

        flow_copy_target = output_dir / "flow"
        flow_copy_target.mkdir(parents=True, exist_ok=True)
        self._copy_tree(self.code, flow_copy_target)
        self._migrate_connections(
            output_dir,
            encryption_key=base64.urlsafe_b64encode(hashlib.sha256(migration_secret.encode("utf-8")).digest()).decode(
                "utf-8"
            ),
        )

    def export(self, output: Union[str, PathLike], migration_secret: str, format="docker"):
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        if format == "docker":
            self._export_to_docker(output, migration_secret)
        else:
            raise ValueError(f"Unsupported export format: {format}")
