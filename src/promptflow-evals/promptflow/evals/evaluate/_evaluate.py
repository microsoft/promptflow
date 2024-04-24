# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import re
from typing import Callable, Dict, Optional

import pandas as pd

from promptflow.client import PFClient


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


def _validation(target, data, evaluators, output_path, tracking_uri, evaluation_name, evaluator_config):
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
        # Apply column mapping
        mapping_config = evaluator_config.get(evaluator_name, evaluator_config.get("default", None))
        new_data_df = _apply_column_mapping(data_df, mapping_config)

        # Validate input data for evaluator
        _validate_input_data_for_evaluator(evaluator, evaluator_name, new_data_df)


def _apply_column_mapping(source_df: pd.DataFrame, mapping_config: dict, inplace: bool = False):
    """
    Apply column mapping to source_df based on mapping_config.
    This function is used for pre-validation of input data for evaluators
    """
    result_df = source_df

    if mapping_config:
        column_mapping = {}
        pattern_prefix = "data."

        for map_to_key, map_value in mapping_config.items():
            match = re.search(r"^\${([^{}]+)}$", map_value)
            if match is not None:
                pattern = match.group(1)
                if pattern.startswith(pattern_prefix):
                    map_from_key = pattern.split(pattern_prefix)[1]
                    column_mapping[map_from_key] = map_to_key

        result_df = source_df.rename(columns=column_mapping, inplace=inplace)

    return result_df


def _process_evaluator_config(evaluator_config: Dict[str, Dict[str, str]]):
    """Process evaluator_config to replace ${target.} with ${data.}"""

    processed_config = {}

    if evaluator_config is None:
        return processed_config

    unexpected_references = re.compile(r"\${(?!target\.|data\.).+?}")

    for evaluator, mapping_config in evaluator_config.items():
        if isinstance(mapping_config, dict):
            processed_config[evaluator] = {}

            for map_to_key, map_value in mapping_config.items():

                # Check if there's any unexpected reference other than ${target.} or ${data.}
                if unexpected_references.search(map_value):
                    raise ValueError(
                        "Unexpected references detected in 'evaluator_config'. "
                        "Ensure only ${target.} and ${data.} are used."
                    )

                # Replace ${target.} with ${data.}
                processed_config[evaluator][map_to_key] = map_value.replace("${target.", "${data.")

    return processed_config


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

    evaluator_config = _process_evaluator_config(evaluator_config)

    _validation(target, data, evaluators, output_path, tracking_uri, evaluation_name, evaluator_config)

    pf_client = PFClient()

    evaluator_info = {}

    for evaluator_name, evaluator in evaluators.items():
        evaluator_info[evaluator_name] = {}
        evaluator_info[evaluator_name]["run"] = pf_client.run(
            flow=evaluator,
            column_mapping=evaluator_config.get(evaluator_name, evaluator_config.get("default", None)),
            data=data,
            stream=True,
        )

    evaluators_result_df = None
    for evaluator_name, evaluator_info in evaluator_info.items():
        evaluator_result_df = pf_client.get_details(evaluator_info["run"], all_results=True)

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
