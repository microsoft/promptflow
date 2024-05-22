# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import mimetypes
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict

from promptflow._utils.flow_utils import resolve_flow_path
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.user_agent_utils import setup_user_agent_to_operation_context
from promptflow.core import Flow
from promptflow.core._serving._errors import InvalidFlowInitConfig
from promptflow.core._serving.extension.extension_factory import ExtensionFactory
from promptflow.core._serving.flow_invoker import AsyncFlowInvoker
from promptflow.core._serving.utils import get_output_fields_to_remove, get_sample_json, load_feedback_swagger
from promptflow.core._utils import init_executable
from promptflow.exceptions import ErrorTarget
from promptflow.storage._run_storage import DummyRunStorage

from ..._constants import PF_FLOW_INIT_CONFIG
from .swagger import generate_swagger


class PromptflowServingAppBasic(ABC):
    def init_app(self, **kwargs):
        logger = kwargs.pop("logger", None)
        if logger is None:
            logger = LoggerFactory.get_logger("pfserving-app", target_stdout=True)
        self.logger = logger
        # default to local, can be override when creating the app
        self.extension = ExtensionFactory.create_extension(logger, **kwargs)
        # make sure pfserving exporters initiated before any customer code loading
        self.flow_monitor = self.extension.get_flow_monitor(self.get_context_data_provider())
        self.flow_invoker: AsyncFlowInvoker = None

        # parse promptflow project path
        self.project_path = self.extension.get_flow_project_path()
        logger.info(f"Project path: {self.project_path}")

        flow_file_path = kwargs.get("flow_file_path", None)
        if flow_file_path:
            self.flow_file_path = Path(flow_file_path)
        else:
            flow_dir, flow_file_name = resolve_flow_path(self.project_path, allow_prompty_dir=True)
            # project path is also the current working directory
            self.flow_file_path = flow_dir / flow_file_name

        self.flow = init_executable(flow_path=self.flow_file_path, working_dir=Path(self.project_path))

        # enable environment_variables
        environment_variables = kwargs.get("environment_variables", {})
        logger.debug(f"Environment variables: {environment_variables}")
        os.environ.update(environment_variables)
        default_environment_variables = self.flow.get_environment_variables_with_overrides()
        self.set_default_environment_variables(default_environment_variables)

        self.flow_name = self.extension.get_flow_name()
        self.flow.name = self.flow_name
        conn_data_override, conn_name_override = self.extension.get_override_connections(self.flow)
        self.connections_override = conn_data_override
        self.connections_name_override = conn_name_override

        self.connection_provider = self.extension.get_connection_provider()
        self.credential = self.extension.get_credential()
        self.sample = get_sample_json(self.project_path, logger)

        self.init = kwargs.get("init", {})
        if not self.init:
            init_params = os.environ.get(PF_FLOW_INIT_CONFIG, None)
            if init_params:
                try:
                    self.init = json.loads(init_params)
                except Exception as e:
                    self.logger.error(f"PF_FLOW_INIT_CONFIG can't be deserialized to json: {e}")
                    raise InvalidFlowInitConfig(
                        "PF_FLOW_INIT_CONFIG can't be deserialized to json",
                        target=ErrorTarget.SERVING_APP,
                    )

        logger.debug("Init params: " + str(self.init))

        self.init_swagger()
        # try to initialize the flow invoker
        try:
            self.init_invoker_if_not_exist()
        except Exception as e:
            if self.extension.raise_ex_on_invoker_initialization_failure(e):
                raise e
        # ensure response has the correct content type
        mimetypes.add_type("application/javascript", ".js")
        mimetypes.add_type("text/css", ".css")
        setup_user_agent_to_operation_context(self.extension.get_user_agent())

    @abstractmethod
    def get_context_data_provider(self):
        pass

    @abstractmethod
    def streaming_response_required(self):
        pass

    def init_invoker_if_not_exist(self):
        if self.flow_invoker:
            return
        self.logger.info("Promptflow executor starts initializing...")
        self.flow_invoker = AsyncFlowInvoker(
            flow=Flow.load(source=self.flow_file_path),
            connection_provider=self.connection_provider,
            streaming=self.streaming_response_required,
            raise_ex=False,
            connections=self.connections_override,
            connections_name_overrides=self.connections_name_override,
            # for serving, we don't need to persist intermediate result, this is to avoid memory leak.
            storage=DummyRunStorage(),
            credential=self.credential,
            init_kwargs=self.init,
            logger=self.logger,
        )
        # why we need to update bonded executable flow?
        self.flow = self.flow_invoker.flow
        # Set the flow name as folder name
        self.flow.name = self.flow_name
        self.response_fields_to_remove = get_output_fields_to_remove(self.flow, self.logger)
        self.logger.info("Promptflow executor initializing succeed!")

    def init_swagger(self):
        self.response_fields_to_remove = get_output_fields_to_remove(self.flow, self.logger)
        self.swagger = generate_swagger(self.flow, self.sample, self.response_fields_to_remove)
        data = load_feedback_swagger()
        self.swagger["paths"]["/feedback"] = data

    def set_default_environment_variables(self, default_environment_variables: Dict[str, str] = None):
        if default_environment_variables is None:
            return
        for key, value in default_environment_variables.items():
            if key not in os.environ:
                os.environ[key] = value
