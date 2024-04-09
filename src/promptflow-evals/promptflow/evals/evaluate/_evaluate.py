# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
from types import FunctionType
from typing import Callable, Dict, Optional

import pandas as pd

from promptflow.client import PFClient

from ._code_client import CodeClient


def _calculate_mean(df) -> Dict[str, float]:
    df.rename(columns={col: col.replace("outputs.", "") for col in df.columns}, inplace=True)
    mean_value = df.mean(numeric_only=True)
    return mean_value.to_dict()


def _validate_input_data_for_evaluator(evaluator, evaluator_name, data_df):
    required_inputs = [
        param.name
        for param in inspect.signature(evaluator).parameters.values()
        if param.default == inspect.Parameter.empty and param.name not in ["kwargs", "args", "self"]
    ]

    missing_inputs = [col for col in required_inputs if col not in data_df.columns]
    if missing_inputs:
        raise ValueError(f"Missing required inputs for evaluator {evaluator_name} : {missing_inputs}.")


def _validation(target, data, evaluators, output_path, tracking_uri, evaluation_name):
    if data is None:
        raise ValueError("data must be provided for evaluation.")

    if target is not None:
        if not callable(target):
            raise ValueError("target must be a callable function.")

    if data is not None:
        if not isinstance(data, str):
            raise ValueError("data must be a string.")

    if evaluators is not None:
        if not isinstance(evaluators, dict):
            raise ValueError("evaluators must be a dictionary.")

    if output_path is not None:
        if not isinstance(output_path, str):
            raise ValueError("output_path must be a string.")

    if tracking_uri is not None:
        if not isinstance(tracking_uri, str):
            raise ValueError("tracking_uri must be a string.")

    if evaluation_name is not None:
        if not isinstance(evaluation_name, str):
            raise ValueError("evaluation_name must be a string.")

    try:
        data_df = pd.read_json(data, lines=True)
    except Exception as e:
        raise ValueError(f"Failed to load data from {data}. Please validate it is a valid jsonl data. Error: {str(e)}.")

    for evaluator_name, evaluator in evaluators.items():
        _validate_input_data_for_evaluator(evaluator, evaluator_name, data_df)


def evaluate(
    *,
    evaluation_name: Optional[str] = None,
    target: Optional[Callable] = None,
    data: Optional[str] = None,
    evaluators: Optional[Dict[str, Callable]] = None,
    evaluator_config: Optional[Dict[str, Dict[str, str]]] = {},
    tracking_uri: Optional[str] = None,
    output_path: Optional[str] = None,
    **kwargs,
):
    """Evaluates target or data with built-in evaluation metrics

    :keyword evaluation_name: Display name of the evaluation.
    :paramtype evaluation_name: Optional[str]
    :keyword target: Target to be evaluated. `target` and `data` both cannot be None
    :paramtype target: Optional[Callable]
    :keyword data: Path to the data to be evaluated or passed to target if target is set.
        Only .jsonl format files are supported.  `target` and `data` both cannot be None
    :paramtype data: Optional[str]
    :keyword evaluator_config: Configuration for evaluators.
    :paramtype evaluator_config: Optional[Dict[str, Dict[str, str]]
    :keyword output_path: The local folder path to save evaluation artifacts to if set
    :paramtype output_path: Optional[str]
    :keyword tracking_uri: Tracking uri to log evaluation results to AI Studio
    :paramtype tracking_uri: Optional[str]
    :return: A EvaluationResult object.
    :rtype: ~azure.ai.generative.evaluate.EvaluationResult
    """

    _validation(target, data, evaluators, output_path, tracking_uri, evaluation_name)

    pf_client = PFClient()
    code_client = CodeClient()

    evaluator_info = {}

    for evaluator_name, evaluator in evaluators.items():
        if isinstance(evaluator, FunctionType):
            evaluator_info.update({evaluator_name: {"client": pf_client, "evaluator": evaluator}})
        else:
            evaluator_info.update({evaluator_name: {"client": code_client, "evaluator": evaluator}})

        evaluator_info[evaluator_name]["run"] = evaluator_info[evaluator_name]["client"].run(
            flow=evaluator,
            column_mapping=evaluator_config.get(evaluator_name, evaluator_config.get("default", None)),
            data=data,
            stream=True,
        )

    evaluators_result_df = None
    for evaluator_name, evaluator_info in evaluator_info.items():
        evaluator_result_df = evaluator_info["client"].get_details(evaluator_info["run"], all_results=True)

        # drop input columns
        evaluator_result_df = evaluator_result_df.drop(
            columns=[col for col in evaluator_result_df.columns if col.startswith("inputs.")]
        )

        # rename output columns
        # Assuming after removing inputs columns, all columns are output columns
        evaluator_result_df.rename(
            columns={
                col: f"outputs.{evaluator_name}.{col.replace('outputs.', '')}" for col in evaluator_result_df.columns
            },
            inplace=True,
        )

        evaluators_result_df = (
            pd.concat([evaluators_result_df, evaluator_result_df], axis=1, verify_integrity=True)
            if evaluators_result_df is not None
            else evaluator_result_df
        )

    input_data_df = pd.read_json(data, lines=True)
    input_data_df = input_data_df.rename(columns={col: f"inputs.{col}" for col in input_data_df.columns})

    result_df = pd.concat([input_data_df, evaluators_result_df], axis=1, verify_integrity=True)

    return {"rows": result_df.to_dict("records"), "metrics": _calculate_mean(evaluators_result_df), "traces": {}}
