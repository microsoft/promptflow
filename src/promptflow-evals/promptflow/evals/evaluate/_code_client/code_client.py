# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import json
import logging

import pandas as pd

from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow.evals.evaluate._utils import _apply_column_mapping, load_jsonl
from promptflow.tracing import ThreadPoolExecutorWithContext as ThreadPoolExecutor
from promptflow.tracing._integrations._openai_injector import inject_openai_api, recover_openai_api

from ..._user_agent import USER_AGENT

LOGGER = logging.getLogger(__name__)


class BatchRunContext:
    def __init__(self, client):
        self.client = client

    def __enter__(self):
        if isinstance(self.client, CodeClient):
            ClientUserAgentUtil.append_user_agent(USER_AGENT)
            inject_openai_api()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(self.client, CodeClient):
            recover_openai_api()


class CodeRun:
    def __init__(self, run, input_data, evaluator_name=None, **kwargs):
        self.run = run
        self.evaluator_name = evaluator_name if evaluator_name is not None else ""
        self.input_data = input_data

    def get_result_df(self, exclude_inputs=False):
        result_df = self.run.result(timeout=60 * 60)
        if exclude_inputs:
            result_df = result_df.drop(columns=[col for col in result_df.columns if col.startswith("inputs.")])
        return result_df


class CodeClient:
    def __init__(self):
        self._thread_pool = ThreadPoolExecutor(thread_name_prefix="evaluators_thread")

    def _calculate_metric(self, evaluator, input_df, column_mapping, evaluator_name):
        row_metric_futures = []
        row_metric_results = []
        input_df = _apply_column_mapping(input_df, column_mapping)
        # Ignoring args and kwargs from the signature since they are usually catching extra arguments
        parameters = {param.name for param in inspect.signature(evaluator).parameters.values()
                      if param.name not in ['args', 'kwargs']}
        for value in input_df.to_dict("records"):
            # Filter out only the parameters that are present in the input data
            # if no parameters then pass data as is
            filtered_values = {k: v for k, v in value.items() if k in parameters} if len(parameters) > 0 else value
            row_metric_futures.append(self._thread_pool.submit(evaluator, **filtered_values))

        for row_number, row_metric_future in enumerate(row_metric_futures):
            try:
                result = row_metric_future.result()
                if not isinstance(result, dict):
                    result = {'output': result}
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

    def run(self, flow, data, evaluator_name=None, column_mapping=None, **kwargs):
        input_df = data
        if not isinstance(input_df, pd.DataFrame):
            try:
                json_data = load_jsonl(data)
            except json.JSONDecodeError:
                raise ValueError(f"Failed to parse data as JSON: {data}. Please provide a valid json lines data.")

            input_df = pd.DataFrame(json_data)
        eval_future = self._thread_pool.submit(self._calculate_metric, flow, input_df, column_mapping, evaluator_name)
        return CodeRun(run=eval_future, input_data=data, evaluator_name=evaluator_name)

    def get_details(self, run, all_results=False):
        result_df = run.run.result(timeout=60 * 60)
        return result_df
