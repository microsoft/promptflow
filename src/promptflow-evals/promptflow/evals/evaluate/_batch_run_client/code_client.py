# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import json
import logging

import pandas as pd

from promptflow.contracts.types import AttrDict
from promptflow.evals.evaluate._utils import _apply_column_mapping, _has_aggregator, get_int_env_var, load_jsonl
from promptflow.tracing import ThreadPoolExecutorWithContext as ThreadPoolExecutor

from ..._constants import PF_BATCH_TIMEOUT_SEC, PF_BATCH_TIMEOUT_SEC_DEFAULT

LOGGER = logging.getLogger(__name__)


class CodeRun:
    def __init__(self, run, input_data, evaluator_name=None, aggregated_metrics=None, **kwargs):
        self.run = run
        self.evaluator_name = evaluator_name if evaluator_name is not None else ""
        self.input_data = input_data
        self.aggregated_metrics = aggregated_metrics

    def get_result_df(self, exclude_inputs=False):
        batch_run_timeout = get_int_env_var(PF_BATCH_TIMEOUT_SEC, PF_BATCH_TIMEOUT_SEC_DEFAULT)
        result_df = self.run.result(timeout=batch_run_timeout)
        if exclude_inputs:
            result_df = result_df.drop(columns=[col for col in result_df.columns if col.startswith("inputs.")])
        return result_df

    def get_aggregated_metrics(self):
        try:
            batch_run_timeout = get_int_env_var(PF_BATCH_TIMEOUT_SEC, PF_BATCH_TIMEOUT_SEC_DEFAULT)
            aggregated_metrics = (
                self.aggregated_metrics.result(timeout=batch_run_timeout)
                if self.aggregated_metrics is not None
                else None
            )
        except Exception as ex:  # pylint: disable=broad-exception-caught
            LOGGER.debug(f"Error calculating metrics for evaluator {self.evaluator_name}, failed with error {str(ex)}")
            aggregated_metrics = None

        if not isinstance(aggregated_metrics, dict):
            LOGGER.warning(
                f"Aggregated metrics for evaluator {self.evaluator_name}"
                f" is not a dictionary will not be logged as metrics"
            )

        aggregated_metrics = aggregated_metrics if isinstance(aggregated_metrics, dict) else {}

        return aggregated_metrics


class CodeClient:
    def __init__(self):
        self._thread_pool = ThreadPoolExecutor(thread_name_prefix="evaluators_thread")

    def _calculate_metric(self, evaluator, input_df, column_mapping, evaluator_name):
        row_metric_futures = []
        row_metric_results = []
        input_df = _apply_column_mapping(input_df, column_mapping)
        # Ignoring args and kwargs from the signature since they are usually catching extra arguments
        parameters = {
            param.name
            for param in inspect.signature(evaluator).parameters.values()
            if param.name not in ["args", "kwargs"]
        }
        for value in input_df.to_dict("records"):
            # Filter out only the parameters that are present in the input data
            # if no parameters then pass data as is
            filtered_values = {k: v for k, v in value.items() if k in parameters} if len(parameters) > 0 else value
            row_metric_futures.append(self._thread_pool.submit(evaluator, **filtered_values))

        for row_number, row_metric_future in enumerate(row_metric_futures):
            try:
                result = row_metric_future.result()
                if not isinstance(result, dict):
                    result = {"output": result}
                row_metric_results.append(result)
            except Exception as ex:  # pylint: disable=broad-except
                msg_1 = f"Error calculating value for row {row_number} for metric {evaluator_name}, "
                msg_2 = f"failed with error {str(ex)} : Stack trace : {str(ex.__traceback__)}"
                LOGGER.info(msg_1 + msg_2)
                # If a row fails to calculate, add an empty dict to maintain the row index
                # This is to ensure the output dataframe has the same number of rows as the input dataframe
                # pd concat will fill NaN for missing values
                row_metric_results.append({})

        return pd.concat(
            [input_df.add_prefix("inputs."), pd.DataFrame(row_metric_results)],
            axis=1,
            verify_integrity=True,
        )

    def _calculate_aggregations(self, evaluator, run):
        try:
            if _has_aggregator(evaluator):
                aggregate_input = None
                evaluator_output = run.get_result_df(exclude_inputs=True)
                if len(evaluator_output.columns) == 1 and evaluator_output.columns[0] == "output":
                    aggregate_input = evaluator_output["output"].tolist()
                else:
                    aggregate_input = [AttrDict(item) for item in evaluator_output.to_dict("records")]

                aggr_func = getattr(evaluator, "__aggregate__")
                aggregated_output = aggr_func(aggregate_input)
                return aggregated_output
        except Exception as ex:  # pylint: disable=broad-exception-caught
            LOGGER.warning(
                f"Error calculating aggregations for evaluator {run.evaluator_name}," f" failed with error {str(ex)}"
            )
        return None

    def run(self, flow, data, evaluator_name=None, column_mapping=None, **kwargs):
        input_df = data
        if not isinstance(input_df, pd.DataFrame):
            try:
                json_data = load_jsonl(data)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Failed to parse data as JSON: {data}. Please provide a valid json lines data."
                ) from exc

            input_df = pd.DataFrame(json_data)
        eval_future = self._thread_pool.submit(self._calculate_metric, flow, input_df, column_mapping, evaluator_name)
        run = CodeRun(run=eval_future, input_data=data, evaluator_name=evaluator_name, aggregated_metrics=None)
        aggregation_future = self._thread_pool.submit(self._calculate_aggregations, evaluator=flow, run=run)
        run.aggregated_metrics = aggregation_future
        return run

    def get_details(self, run, all_results=False):
        result_df = run.get_result_df(exclude_inputs=not all_results)
        return result_df

    def get_metrics(self, run):
        try:
            aggregated_metrics = run.get_aggregated_metrics()
            print("Aggregated metrics")
            print(aggregated_metrics)
        except Exception as ex:  # pylint: disable=broad-exception-caught
            LOGGER.debug(f"Error calculating metrics for evaluator {run.evaluator_name}, failed with error {str(ex)}")
            return None
        return aggregated_metrics
