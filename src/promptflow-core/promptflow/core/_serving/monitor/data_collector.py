# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class FlowDataCollector:
    """FlowDataCollector is used to collect flow data via MDC for monitoring."""

    def __init__(self, logger):
        self.logger = logger
        self._init_success = self._init_data_collector()
        logger.info(f"Mdc init status: {self._init_success}")

    def _init_data_collector(self) -> bool:
        """init data collector."""
        self.logger.info("Init mdc...")
        try:
            from azureml.ai.monitoring import Collector

            self.inputs_collector = Collector(name="model_inputs")
            self.outputs_collector = Collector(name="model_outputs")
            return True
        except ImportError as e:
            self.logger.warning(f"Load mdc related module failed: {e}")
            return False
        except Exception as e:
            self.logger.warning(f"Init mdc failed: {e}")
            return False

    def collect_flow_data(self, input: dict, output: dict, req_id: str = None, client_req_id: str = None):
        """collect flow data via MDC for monitoring."""
        if not self._init_success:
            return
        try:
            import pandas as pd
            from azureml.ai.monitoring.context import BasicCorrelationContext

            # build context
            ctx = BasicCorrelationContext(id=req_id)
            # collect inputs
            coll_input = {k: [v] for k, v in input.items()}
            input_df = pd.DataFrame(coll_input)
            self.inputs_collector.collect(input_df, ctx)
            # collect outputs
            coll_output = {k: [v] for k, v in output.items()}
            output_df = pd.DataFrame(coll_output)
            # collect outputs data, pass in correlation_context so inputs and outputs data can be correlated later
            self.outputs_collector.collect(output_df, ctx)
        except ImportError as e:
            self.logger.warning(f"Load mdc related module failed: {e}")
        except Exception as e:
            self.logger.warning(f"Collect flow data failed: {e}")
