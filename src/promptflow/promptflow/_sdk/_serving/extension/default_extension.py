# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from abc import ABC, abstractmethod
import os
import json
import yaml
from pathlib import Path
from promptflow._sdk._configuration import Configuration
from promptflow._version import VERSION
from promptflow.contracts.flow import Flow
from promptflow._sdk._serving.metrics import MetricsRecorder
from promptflow._sdk._serving.flow_monitor import FlowMonitor
from promptflow._sdk._serving.blueprint.static_web_blueprint import construct_staticweb_blueprint
from promptflow._sdk._serving.blueprint.monitor_blueprint import construct_monitor_blueprint

USER_AGENT = f"promptflow-local-serving/{VERSION}"
DEFAULT_STATIC_PATH = Path(__file__).parent / "static"


class AppExtension(ABC):
    def __init__(self, logger, **kwargs):
        self.logger = logger

    @abstractmethod
    def get_flow_project_path(self) -> str:
        pass

    @abstractmethod
    def get_flow_name(self) -> str:
        pass

    @abstractmethod
    def get_connection_provider(self) -> str:
        pass

    @abstractmethod
    def get_blueprints(self):
        pass

    def get_override_connections(self, flow: Flow) -> (dict, dict):
        return {}, {}

    def raise_ex_on_invoker_initialization_failure(self, ex: Exception):
        return True

    def get_user_agent(self) -> str:
        return USER_AGENT

    def get_extra_metrics_dimensions(self):
        return self._get_common_dimensions_from_env()

    def get_flow_monitor(self) -> FlowMonitor:
        extra_dimensions = self.get_extra_metrics_dimensions()
        metrics_recorder = MetricsRecorder(common_dimensions=extra_dimensions)
        # default no data collector, no app insights metric exporter
        return FlowMonitor(self.logger, self.get_flow_name(), None, metrics_recorder=metrics_recorder)

    def _get_mlflow_project_path(self, project_path: str):
        # check whether it's mlflow model
        mlflow_metadata_file = os.path.join(project_path, "MLmodel")
        if os.path.exists(mlflow_metadata_file):
            with open(mlflow_metadata_file, "r", encoding="UTF-8") as fin:
                mlflow_metadata = yaml.safe_load(fin)
            flow_entry = mlflow_metadata.get("flavors", {}).get("promptflow", {}).get("entry")
            if mlflow_metadata:
                dag_path = os.path.join(project_path, flow_entry)
                return str(Path(dag_path).parent.absolute())
        return project_path

    def _get_common_dimensions_from_env(self):
        common_dimensions_str = os.getenv("PF_SERVING_METRICS_COMMON_DIMENSIONS", None)
        if common_dimensions_str:
            try:
                common_dimensions = json.loads(common_dimensions_str)
                return common_dimensions
            except Exception as ex:
                self.logger.warn(f"Failed to parse common dimensions with value={common_dimensions_str}: {ex}")
        return {}

    def _get_default_blueprints(self, static_folder=None):
        static_web_blueprint = construct_staticweb_blueprint(static_folder)
        monitor_print = construct_monitor_blueprint(self.get_flow_monitor())
        return [static_web_blueprint, monitor_print]


class DefaultAppExtension(AppExtension):
    def __init__(self, logger, **kwargs):
        self.logger = logger
        static_folder = kwargs.get("static_folder", None)
        self.static_folder = static_folder if static_folder else DEFAULT_STATIC_PATH
        logger.info(f"Static_folder: {self.static_folder}")
        app_config = kwargs.get("config", None) or {}
        pf_config = Configuration(overrides=app_config)
        logger.info(f"Promptflow config: {pf_config}")
        self.connection_provider = pf_config.get_connection_provider()

    def get_flow_project_path(self) -> str:
        return os.getenv("PROMPTFLOW_PROJECT_PATH", ".")

    def get_flow_name(self) -> str:
        project_path = self.get_flow_project_path()
        return Path(project_path).stem

    def get_connection_provider(self) -> str:
        return self.connection_provider

    def get_blueprints(self):
        return self._get_default_blueprints(self.static_folder)
