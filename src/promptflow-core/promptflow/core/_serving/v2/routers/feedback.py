# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json

from fastapi import APIRouter, Request
from opentelemetry import baggage, context, trace

from promptflow.core._serving.constants import FEEDBACK_TRACE_FIELD_NAME, FEEDBACK_TRACE_SPAN_NAME
from promptflow.core._serving.utils import serialize_attribute_value, try_extract_trace_context


def get_feedback_router(logger):
    router = APIRouter()

    @router.post("/feedback")
    async def feedback(request: Request):
        ctx = try_extract_trace_context(logger, request.headers)
        open_telemetry_tracer = trace.get_tracer_provider().get_tracer("promptflow")
        token = context.attach(ctx) if ctx else None
        try:
            with open_telemetry_tracer.start_as_current_span(FEEDBACK_TRACE_SPAN_NAME) as span:
                data = await request.body()
                if data:
                    data = data.decode(errors="replace")
                should_flatten = request.query_params.get("flatten", "false").lower() == "true"
                if should_flatten:
                    try:
                        # try flatten the data to avoid data too big issue (especially for app insights scenario)
                        data = json.loads(data)
                        for k in data:
                            span.set_attribute(k, serialize_attribute_value(data[k]))
                    except Exception as e:
                        logger.warning(f"Failed to flatten the feedback, fall back to non-flattern mode. Error: {e}.")
                        span.set_attribute(FEEDBACK_TRACE_FIELD_NAME, data)
                else:
                    span.set_attribute(FEEDBACK_TRACE_FIELD_NAME, data)
                # add baggage data if exist
                data = baggage.get_all()
                if data:
                    for k, v in data.items():
                        span.set_attribute(k, v)
        finally:
            if token:
                context.detach(token)
        return {"status": "Feedback received."}

    return router
