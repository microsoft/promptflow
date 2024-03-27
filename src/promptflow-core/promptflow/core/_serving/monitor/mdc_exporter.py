# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from typing import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter


class MdcExporter(SpanExporter):
    """An open telemetry span exporter to MDC."""

    def __init__(self, logger):
        self.logger = logger
        self._init_success = self._init_data_collector()
        logger.info(f"Mdc exporter init status: {self._init_success}")

    def _init_data_collector(self) -> bool:
        """init data collector for tracing spans."""
        self.logger.info("Init mdc for app_traces...")
        try:
            from azureml.ai.monitoring import Collector

            self.span_collector = Collector(name="app_traces")
            return True
        except ImportError as e:
            self.logger.warning(f"Load mdc related module failed: {e}")
            return False
        except Exception as e:
            self.logger.warning(f"Init mdc for app_traces failed: {e}")
            return False

    def export(self, spans: Sequence[ReadableSpan]):
        """export open telemetry spans to MDC."""
        if not self._init_success:
            return
        try:
            import pandas as pd

            for span in spans:
                span_dict: dict = json.loads(span.to_json())
                coll_span = {k: [v] for k, v in span_dict.items()}
                span_df = pd.DataFrame(coll_span)
                self.span_collector.collect(span_df)

        except ImportError as e:
            self.logger.warning(f"Load mdc related module failed: {e}")
        except Exception as e:
            self.logger.warning(f"Collect tracing spans failed: {e}")
