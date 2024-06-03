# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple

from promptflow._constants import DEFAULT_ENCODING
from promptflow._utils.yaml_utils import load_yaml
from promptflow.contracts.flow import Flow
from promptflow.core._serving.extension.extension_type import ExtensionType
from promptflow.core._serving.extension.otel_exporter_provider_factory import OTelExporterProviderFactory
from promptflow.core._serving.monitor.context_data_provider import ContextDataProvider
from promptflow.core._serving.monitor.flow_monitor import FlowMonitor
from promptflow.core._serving.v1.blueprint.monitor_blueprint import construct_monitor_blueprint
from promptflow.core._serving.v1.blueprint.static_web_blueprint import construct_staticweb_blueprint
from promptflow.core._version import __version__

USER_AGENT = f"promptflow-local-serving/{__version__}"
DEFAULT_STATIC_PATH = Path(__file__).parent.parent / "static"


class AppExtension(ABC):
    def __init__(self, logger, extension_type: ExtensionType, collector=None, **kwargs):
        self.logger = logger
        self.extension_type = extension_type
        self.data_collector = collector
        self.flow_monitor = None

    @abstractmethod
    def get_flow_project_path(self) -> str:
        """Get flow project path."""
        pass

    @abstractmethod
    def get_flow_name(self) -> str:
        """Get flow name."""
        pass

    @abstractmethod
    def get_connection_provider(self) -> str:
        """Get connection provider."""
        pass

    @abstractmethod
    def get_blueprints(self, flow_monitor: FlowMonitor):
        """Get blueprints for current extension."""
        pass

    def get_override_connections(self, flow: Flow) -> Tuple[dict, dict]:
        """
        Get override connections for current extension.

        :param flow: The flow to execute.
        :type flow: ~promptflow.contracts.flow.Flow
        :return: The override connections, first dict is for connection data override, second dict is for connection name override.  # noqa: E501
        :rtype: (dict, dict)
        """
        return {}, {}

    def raise_ex_on_invoker_initialization_failure(self, ex: Exception):
        """
        whether to raise exception when initializing flow invoker failed.

        :param ex: The exception when initializing flow invoker.
        :type ex: Exception
        :return: Whether to raise exception when initializing flow invoker failed.
        """
        return True

    def get_user_agent(self) -> str:
        """Get user agent used for current extension."""
        return USER_AGENT

    def get_credential(self):
        """Get credential for current extension."""
        return None

    def get_metrics_common_dimensions(self):
        """Get common dimensions for metrics if exist."""
        return self._get_common_dimensions_from_env()

    def get_flow_monitor(self, ctx_data_provider: ContextDataProvider) -> FlowMonitor:
        """Get flow monitor for current extension."""
        if self.flow_monitor:
            return self.flow_monitor
        custom_dimensions = self.get_metrics_common_dimensions()
        metric_exporters = OTelExporterProviderFactory.get_metrics_exporters(self.logger, self.extension_type)
        trace_exporters = OTelExporterProviderFactory.get_trace_exporters(self.logger, self.extension_type)
        log_exporters = OTelExporterProviderFactory.get_log_exporters(self.logger, self.extension_type)
        self.flow_monitor = FlowMonitor(
            self.logger,
            self.get_flow_name(),
            self.data_collector,
            ctx_data_provider,
            custom_dimensions,
            metric_exporters,
            trace_exporters,
            log_exporters,
        )  # noqa: E501
        return self.flow_monitor

    def _get_mlflow_project_path(self, project_path: str):
        # check whether it's mlflow model
        mlflow_metadata_file = os.path.join(project_path, "MLmodel")
        if os.path.exists(mlflow_metadata_file):
            with open(mlflow_metadata_file, "r", encoding=DEFAULT_ENCODING) as fin:
                mlflow_metadata = load_yaml(fin)
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
                self.logger.warning(f"Failed to parse common dimensions with value={common_dimensions_str}: {ex}")
        return {}

    def _get_default_blueprints(self, flow_monitor, static_folder=None):
        static_web_blueprint = construct_staticweb_blueprint(static_folder)
        monitor_print = construct_monitor_blueprint(flow_monitor)
        return [static_web_blueprint, monitor_print]


class DefaultAppExtension(AppExtension):
    """default app extension for local serve."""

    def __init__(self, logger, **kwargs):
        super().__init__(logger=logger, extension_type=ExtensionType.DEFAULT, **kwargs)
        static_folder = kwargs.get("static_folder", None)
        self.static_folder = static_folder if static_folder else DEFAULT_STATIC_PATH
        logger.info(f"Static_folder: {self.static_folder}")
        self.connection_provider = kwargs.get("connection_provider", None) or None

    def get_flow_project_path(self) -> str:
        return os.getenv("PROMPTFLOW_PROJECT_PATH", ".")

    def get_flow_name(self) -> str:
        project_path = self.get_flow_project_path()
        return Path(project_path).resolve().absolute().stem

    def get_connection_provider(self) -> str:
        return self.connection_provider

    def get_blueprints(self, flow_monitor: FlowMonitor):
        return self._get_default_blueprints(flow_monitor, self.static_folder)
