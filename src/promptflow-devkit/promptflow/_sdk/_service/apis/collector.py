# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# this file is different from other files in this folder
# functions (APIs) defined in this file follows OTLP 1.1.0
# https://opentelemetry.io/docs/specs/otlp/#otlphttp-request
# to provide OTLP/HTTP endpoint as OTEL collector

import logging
from typing import Callable, Optional

from flask import request
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from promptflow._sdk._errors import MissingAzurePackage
from promptflow._sdk._tracing import _is_azure_ext_installed, process_otlp_trace_request
from promptflow._sdk._utilities.tracing_utils import _telemetry_helper as trace_telemetry_helper
from promptflow._sdk._utilities.tracing_utils import aggregate_trace_count


def trace_collector(
    get_created_by_info_with_cache: Callable,
    logger: logging.Logger,
    cloud_trace_only: bool = False,
    credential: Optional[object] = None,
):
    """Collect traces from OTLP/HTTP endpoint and write to local/remote storage.

    This function is target to be reused in other places, so pass in get_created_by_info_with_cache and logger to avoid
    app related dependencies.

    :param get_created_by_info_with_cache: A function that retrieves information about the creator of the trace.
    :type get_created_by_info_with_cache: Callable
    :param logger: The logger object used for logging.
    :type logger: logging.Logger
    :param cloud_trace_only: If True, only write trace to cosmosdb and skip local trace. Default is False.
    :type cloud_trace_only: bool
    :param credential: The credential object used to authenticate with cosmosdb. Default is None.
    :type credential: Optional[object]
    """
    all_spans = list()
    content_type = request.headers.get("Content-Type")
    # binary protobuf encoding
    if "application/x-protobuf" in content_type:
        trace_request = ExportTraceServiceRequest()
        trace_request.ParseFromString(request.data)
        # this function will be called in some old runtime versions
        # where runtime will pass either credential object, or the function to get credential
        # as we need to be compatible with this, need to handle both cases
        if credential is not None:
            # local prompt flow service will not pass credential, so this is runtime scenario
            get_credential = credential if callable(credential) else lambda: credential  # noqa: F841
            all_spans = process_otlp_trace_request(
                trace_request=trace_request,
                get_created_by_info_with_cache=get_created_by_info_with_cache,
                logger=logger,
                get_credential=get_credential,
                cloud_trace_only=cloud_trace_only,
            )
        else:
            # if `promptflow-azure` is not installed, pass an exception class to the function
            get_credential = MissingAzurePackage
            if _is_azure_ext_installed():
                from azure.identity import AzureCliCredential

                get_credential = AzureCliCredential
            all_spans = process_otlp_trace_request(
                trace_request=trace_request,
                get_created_by_info_with_cache=get_created_by_info_with_cache,
                logger=logger,
                get_credential=get_credential,
                cloud_trace_only=cloud_trace_only,
            )
        # trace telemetry
        if len(all_spans) > 0:
            summary = aggregate_trace_count(all_spans=all_spans)
            trace_telemetry_helper.append(summary=summary)

        return "Traces received", 200

    # JSON protobuf encoding
    elif "application/json" in content_type:
        raise NotImplementedError
