# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
from abc import abstractmethod
from enum import Enum

from opentelemetry.sdk.environment_variables import (
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_EXPORTER_OTLP_LOGS_ENDPOINT,
    OTEL_EXPORTER_OTLP_METRICS_ENDPOINT,
    OTEL_EXPORTER_OTLP_PROTOCOL,
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
)

from promptflow.core._serving.extension.extension_type import ExtensionType
from promptflow.core._serving.monitor.mdc_exporter import MdcExporter


class ExporterType(Enum):
    METRIC = "metric"
    TRACE = "trace"
    LOG = "log"


class OTelExporterProvider:
    def __init__(self, logger, exporter_type: ExporterType) -> None:
        self.logger = logger
        self._exporter_type = exporter_type

    @abstractmethod
    def is_enabled(self, extension: ExtensionType):
        """check whether the exporter is enabled for given extension."""
        pass

    @abstractmethod
    def get_exporter(self, **kwargs):
        """get exporter instance."""
        pass

    @property
    def exporter_type(self) -> ExporterType:
        return self._exporter_type


class AppInsightExporterProvider(OTelExporterProvider):
    def __init__(self, logger, exporter_type: ExporterType) -> None:
        super().__init__(logger, exporter_type)
        self.app_insight_connection_string = try_get_app_insight_connection_string()
        if not self.app_insight_connection_string:
            self.logger.info(f"No connection string detected, app insight {exporter_type.value} exporter is disabled.")

    def is_enabled(self, extension: ExtensionType):
        return self.app_insight_connection_string is not None


class AppInsightTraceExporterProvider(AppInsightExporterProvider):
    def __init__(self, logger) -> None:
        super().__init__(logger, ExporterType.TRACE)

    def get_exporter(self, **kwargs):
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

            return AzureMonitorTraceExporter.from_connection_string(self.app_insight_connection_string)
        except ImportError:
            self.logger.warning(
                "azure-monitor-opentelemetry-exporter is not installed, \
                                 AzureMonitorTraceExporter will not be enabled!"
            )
            return None


class MdcTraceExporterProvider(OTelExporterProvider):
    def __init__(self, logger) -> None:
        super().__init__(logger, ExporterType.TRACE)

    def is_enabled(self, extension: ExtensionType):
        return extension == ExtensionType.AZUREML

    def get_exporter(self, **kwargs):
        return MdcExporter(self.logger)


class AppInsightMetricsExporterProvider(AppInsightExporterProvider):
    def __init__(self, logger) -> None:
        super().__init__(logger, ExporterType.METRIC)

    def get_exporter(self, **kwargs):
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter

            return AzureMonitorMetricExporter.from_connection_string(self.app_insight_connection_string)
        except ImportError:
            self.logger.warning(
                "azure-monitor-opentelemetry-exporter is not installed, \
                                 AzureMonitorMetricExporter will not be enabled!"
            )
            return None


class AppInsightLogExporterProvider(AppInsightExporterProvider):
    def __init__(self, logger) -> None:
        super().__init__(logger, ExporterType.LOG)

    def get_exporter(self, **kwargs):
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter

            return AzureMonitorLogExporter.from_connection_string(self.app_insight_connection_string)
        except ImportError:
            self.logger.warning(
                "azure-monitor-opentelemetry-exporter is not installed, \
                                 AzureMonitorLogExporter will not be enabled!"
            )
            return None


OTEL_EXPORTER_OTLP_AAD_AUTH_ENABLE = "OTEL_EXPORTER_OTLP_AAD_AUTH_ENABLE"
OTEL_EXPORTER_OTLP_AAD_AUTH_SCOPE = "OTEL_EXPORTER_OTLP_AAD_AUTH_SCOPE"


class OTLPExporterProvider(OTelExporterProvider):
    def __init__(self, logger, exporter_type: ExporterType) -> None:
        super().__init__(logger, exporter_type)
        self.otel_exporter_endpoint = os.environ.get(OTEL_EXPORTER_OTLP_ENDPOINT, None)
        extra_env: str = None
        if not self.otel_exporter_endpoint:
            if exporter_type == ExporterType.TRACE:
                extra_env = OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
                self.otel_exporter_endpoint = os.environ.get(OTEL_EXPORTER_OTLP_TRACES_ENDPOINT, None)
            elif exporter_type == ExporterType.METRIC:
                extra_env = OTEL_EXPORTER_OTLP_METRICS_ENDPOINT
                self.otel_exporter_endpoint = os.environ.get(OTEL_EXPORTER_OTLP_METRICS_ENDPOINT, None)
            elif exporter_type == ExporterType.LOG:
                extra_env = OTEL_EXPORTER_OTLP_LOGS_ENDPOINT
                self.otel_exporter_endpoint = os.environ.get(OTEL_EXPORTER_OTLP_LOGS_ENDPOINT, None)

        if not self.otel_exporter_endpoint:
            self.logger.info(
                f"No OTEL_EXPORTER_OTLP_ENDPOINT or {extra_env} detected, OTLP {exporter_type.value} exporter is disabled."  # noqa
            )
        # https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/#otel_exporter_otlp_protocol
        self.otel_exporter_protocol = os.environ.get(OTEL_EXPORTER_OTLP_PROTOCOL, "http/protobuf")

    def is_enabled(self, extension: ExtensionType):
        return self.otel_exporter_endpoint is not None


class OTLPTraceExporterProvider(OTLPExporterProvider):
    def __init__(self, logger) -> None:
        super().__init__(logger, ExporterType.TRACE)

    def get_exporter(self, **kwargs):
        logger = self.logger
        try:
            if self.otel_exporter_protocol == "http/protobuf":
                dependency_lib = "opentelemetry-exporter-otlp-proto-http"
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                class AADAuthOTLPSpanExporter(OTLPSpanExporter):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        self.aad_auth, self.aad_auth_scope, self.credential = try_parse_otlp_aad_auth_info(
                            logger, "OTLPSpanExporter"
                        )

                    def _export(self, serialized_data: str):
                        if self.aad_auth and self.credential:
                            token = self.credential.get_token(self.aad_auth_scope).token
                            auth_header = {"Authorization": f"Bearer {token}"}
                            self._session.headers.update(auth_header)
                        return super()._export(serialized_data)

                return AADAuthOTLPSpanExporter(endpoint=self.otel_exporter_endpoint)
            else:
                # TODO: add aad support if needed.
                dependency_lib = "opentelemetry-exporter-otlp-proto-grpc"
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

                return OTLPSpanExporter(endpoint=self.otel_exporter_endpoint)
        except ImportError:
            self.logger.warning(
                f"{dependency_lib} is not installed, \
                                 OTLPSpanExporter will not be enabled!"
            )
            return None


class OTLPMetricsExporterProvider(OTLPExporterProvider):
    def __init__(self, logger) -> None:
        super().__init__(logger, ExporterType.METRIC)

    def get_exporter(self, **kwargs):
        logger = self.logger
        try:
            if self.otel_exporter_protocol == "http/protobuf":
                dependency_lib = "opentelemetry-exporter-otlp-proto-http"
                from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

                class AADAuthOTLPMetricExporter(OTLPMetricExporter):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        self.aad_auth, self.aad_auth_scope, self.credential = try_parse_otlp_aad_auth_info(
                            logger, "OTLPMetricExporter"
                        )

                    def _export(self, serialized_data: str):
                        if self.aad_auth and self.credential:
                            token = self.credential.get_token(self.aad_auth_scope).token
                            auth_header = {"Authorization": f"Bearer {token}"}
                            self._session.headers.update(auth_header)
                        return super()._export(serialized_data)

                return AADAuthOTLPMetricExporter(endpoint=self.otel_exporter_endpoint)
            else:
                # TODO: add aad support if needed.
                dependency_lib = "opentelemetry-exporter-otlp-proto-grpc"
                from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

                return OTLPMetricExporter(endpoint=self.otel_exporter_endpoint, insecure=True)
        except ImportError:
            self.logger.warning(
                f"{dependency_lib} is not installed, \
                                 OTLPMetricExporter will not be enabled!"
            )
            return None


class OTLPLogExporterProvider(OTLPExporterProvider):
    def __init__(self, logger) -> None:
        super().__init__(logger, ExporterType.LOG)

    def get_exporter(self, **kwargs):
        logger = self.logger
        try:
            if self.otel_exporter_protocol == "http/protobuf":
                dependency_lib = "opentelemetry-exporter-otlp-proto-http"
                from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

                class AADAuthOTLPLogExporter(OTLPLogExporter):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        self.aad_auth, self.aad_auth_scope, self.credential = try_parse_otlp_aad_auth_info(
                            logger, "OTLPLogExporter"
                        )

                    def _export(self, serialized_data: str):
                        if self.aad_auth and self.credential:
                            token = self.credential.get_token(self.aad_auth_scope).token
                            auth_header = {"Authorization": f"Bearer {token}"}
                            self._session.headers.update(auth_header)
                        return super()._export(serialized_data)

                return AADAuthOTLPLogExporter(endpoint=self.otel_exporter_endpoint)
            else:
                # TODO: add aad support if needed.
                dependency_lib = "opentelemetry-exporter-otlp-proto-grpc"
                from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

                return OTLPLogExporter(endpoint=self.otel_exporter_endpoint)
        except ImportError:
            self.logger.warning(
                f"{dependency_lib} is not installed, \
                                 OTLPSpanExporter will not be enabled!"
            )
            return None


class OTelExporterProviderFactory:
    """Factory to create OTel trace and metric exporters based on extension type."""

    @staticmethod
    def get_trace_exporters(logger, extension: ExtensionType, **kwargs):
        trace_providers = [
            AppInsightTraceExporterProvider(logger),
            MdcTraceExporterProvider(logger),
            OTLPTraceExporterProvider(logger),
        ]
        exporters = []
        for provider in trace_providers:
            if provider.is_enabled(extension):
                exporter = provider.get_exporter(**kwargs)
                if exporter:
                    exporters.append(exporter)
        return exporters

    @staticmethod
    def get_metrics_exporters(logger, extension: ExtensionType, **kwargs):
        metric_providers = [AppInsightMetricsExporterProvider(logger), OTLPMetricsExporterProvider(logger)]
        exporters = []
        for provider in metric_providers:
            if provider.is_enabled(extension):
                exporter = provider.get_exporter(**kwargs)
                if exporter:
                    exporters.append(exporter)
        return exporters

    @staticmethod
    def get_log_exporters(logger, extension: ExtensionType, **kwargs):
        log_providers = [AppInsightLogExporterProvider(logger), OTLPLogExporterProvider(logger)]
        exporters = []
        for provider in log_providers:
            if provider.is_enabled(extension):
                exporter = provider.get_exporter(**kwargs)
                if exporter:
                    exporters.append(exporter)
        return exporters


def try_get_app_insight_connection_string():
    """
    Try to get application insight connection string from environment variable.
    app insight base exporter support these environment variables:
    - "APPINSIGHTS_INSTRUMENTATIONKEY"
    - "APPLICATIONINSIGHTS_CONNECTION_STRING"
    """
    instrumentation_key = os.getenv("AML_APP_INSIGHTS_KEY") or os.getenv("APPINSIGHTS_INSTRUMENTATIONKEY")
    if instrumentation_key:
        return f"InstrumentationKey={instrumentation_key}"
    connection_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    return connection_str


def try_parse_otlp_aad_auth_info(logger, exporter_name):
    aad_auth = os.environ.get(OTEL_EXPORTER_OTLP_AAD_AUTH_ENABLE, "false").lower() == "true"
    aad_auth_scope = os.environ.get(OTEL_EXPORTER_OTLP_AAD_AUTH_SCOPE, "https://management.azure.com/.default")
    credential = None
    if aad_auth:
        try:
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
        except ImportError:
            logger.warning(
                f"azure-identity is not installed, \
                                AAD auth for {exporter_name} will not be enabled!"
            )
    return aad_auth, aad_auth_scope, credential
