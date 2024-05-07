# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import os
import re
import tempfile
from typing import Any, Callable, Dict, Optional, Set, Tuple

import pandas as pd

from promptflow._sdk._constants import LINE_NUMBER
from promptflow.client import PFClient
from ._utils import _log_metrics_and_instance_results
from .._user_agent import USER_AGENT


def _calculate_mean(df) -> Dict[str, float]:
    df.rename(columns={col: col.replace("outputs.", "") for col in df.columns}, inplace=True)
    mean_value = df.mean(numeric_only=True)
    return mean_value.to_dict()


def _validate_input_data_for_evaluator(evaluator, evaluator_name, df_data, is_target_fn=False):
    required_inputs = [
        param.name
        for param in inspect.signature(evaluator).parameters.values()
        if param.default == inspect.Parameter.empty and param.name not in ["kwargs", "args", "self"]
    ]

    missing_inputs = [col for col in required_inputs if col not in df_data.columns]
    if missing_inputs:
        if not is_target_fn:
            raise ValueError(f"Missing required inputs for evaluator {evaluator_name} : {missing_inputs}.")
        else:
            raise ValueError(f"Missing required inputs for target : {missing_inputs}.")


def _validate_and_load_data(target, data, evaluators, output_path, tracking_uri, evaluation_name):
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
        initial_data_df = pd.read_json(data, lines=True)
    except Exception as e:
        raise ValueError(f"Failed to load data from {data}. Please validate it is a valid jsonl data. Error: {str(e)}.")

    return initial_data_df


def _validate_columns(
    df: pd.DataFrame,
    evaluators: Dict[str, Any],
    target: Optional[Callable],
    evaluator_config: Dict[str, Dict[str, str]],
) -> None:
    """
    Check that all columns needed by evaluator or target function are present.

    :keyword df: The data frame to be validated.
    :paramtype df: pd.DataFrame
    :keyword evaluators: The dictionary of evaluators.
    :paramtype evaluators: Dict[str, Any]
    :keyword target: The callable to be applied to data set.
    :paramtype target: Optional[Callable]
    """
    if target:
        # If the target function is given, it may return
        # several columns and hence we cannot check the availability of columns
        # without knowing target function semantics.
        # Instead, here we will validate the columns, taken by target.
        _validate_input_data_for_evaluator(target, None, df, is_target_fn=True)
    else:
        for evaluator_name, evaluator in evaluators.items():
            # Apply column mapping
            mapping_config = evaluator_config.get(evaluator_name, evaluator_config.get("default", None))
            new_df = _apply_column_mapping(df, mapping_config)

            # Validate input data for evaluator
            _validate_input_data_for_evaluator(evaluator, evaluator_name, new_df)


def _apply_target_to_data(
    target: Callable, data: str, pf_client: PFClient, initial_data: pd.DataFrame,
    evaluation_name: Optional[str] = None
) -> Tuple[pd.DataFrame, Set[str]]:
    """
    Apply the target function to the data set and return updated data and generated columns.

    :keyword target: The function to be applied to data.
    :paramtype target: Callable
    :keyword data: The path to input jsonl file.
    :paramtype data: str
    :keyword pf_client: The promptflow client to be used.
    :paramtype pf_client: PFClient
    :keyword initial_data: The data frame with the loaded data.
    :paramtype initial_data: pd.DataFrame
    :return: The tuple, containing data frame and the list of added columns.
    :rtype: Tuple[pd.DataFrame, List[str]]
    """
    # We are manually creating the temporary directory for the flow
    # because the way tempdir remove temporary directories will
    # hang the debugger, because promptflow will keep flow directory.
    run = pf_client.run(
        flow=target,
        display_name=evaluation_name,
        data=data,
        properties={"runType": "eval_run"},
        stream=True
    )
    target_output = pf_client.runs.get_details(run, all_results=True)
    # Remove input and output prefix
    prefix = "outputs."
    rename_dict = {col: col[len(prefix):] for col in target_output.columns if col.startswith(prefix)}
    # Sort output by line numbers
    target_output.set_index(f"inputs.{LINE_NUMBER}", inplace=True)
    target_output.sort_index(inplace=True)
    target_output.reset_index(inplace=True, drop=False)
    # target_output contains only input columns, taken by function,
    # so we need to concatenate it to the input data frame.
    drop_columns = set(target_output.columns) - set(rename_dict.keys())
    target_output.drop(drop_columns, inplace=True, axis=1)
    # Remove outputs. prefix
    target_output.rename(columns=rename_dict, inplace=True)
    # Concatenate output to input
    target_output = pd.concat([target_output, initial_data], axis=1)
    return target_output, set(rename_dict.values()), run


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

    unexpected_references = re.compile(r"\${(?!target\.|data\.).+?}")

    if evaluator_config:
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

    input_data_df = _validate_and_load_data(target, data, evaluators, output_path, tracking_uri, evaluation_name)

    # Process evaluator config to replace ${target.} with ${data.}
    evaluator_config = _process_evaluator_config(evaluator_config)
    _validate_columns(input_data_df, evaluators, target, evaluator_config)

    pf_client = PFClient(
        config={
            "trace.destination": tracking_uri
        } if tracking_uri else None,
        user_agent=USER_AGENT,

    )
    target_run = None

    target_generated_columns = set()
    if data is not None and target is not None:
        input_data_df, target_generated_columns, target_run = _apply_target_to_data(target, data, pf_client,
                                                                                    input_data_df, evaluation_name)
        # After we have generated all columns we can check if we have
        # everything we need for evaluators.
        _validate_columns(input_data_df, evaluators, target=None, evaluator_config=evaluator_config)

    evaluator_info = {}

    with tempfile.TemporaryDirectory() as d:
        data_file = data
        if target_generated_columns:
            data_file = os.path.join(d, "input.jsonl")
            input_data_df.to_json(data_file, orient="records", lines=True)

        for evaluator_name, evaluator in evaluators.items():
            evaluator_info[evaluator_name] = {}
            evaluator_info[evaluator_name]["run"] = pf_client.run(
                flow=evaluator,
                run=target_run,
                column_mapping=evaluator_config.get(evaluator_name, evaluator_config.get("default", None)),
                data=data_file,
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
                    col: "outputs." f"{evaluator_name}.{col.replace('outputs.', '')}"
                    for col in evaluator_result_df.columns
                },
                inplace=True,
            )

            evaluators_result_df = (
                pd.concat([evaluators_result_df, evaluator_result_df], axis=1, verify_integrity=True)
                if evaluators_result_df is not None
                else evaluator_result_df
            )

    # Rename columns, generated by template function to outputs instead of inputs.
    input_data_df.rename(
        columns={
            col: f"{'outputs' if col in target_generated_columns else 'inputs'}.{col}" for col in input_data_df.columns
        },
        inplace=True,
    )

    result_df = pd.concat([input_data_df, evaluators_result_df], axis=1, verify_integrity=True)
    metrics = _calculate_mean(evaluators_result_df)

    studio_url = _log_metrics_and_instance_results(
        metrics, result_df, tracking_uri, target_run, pf_client, data, evaluation_name)

    return {"rows": result_df.to_dict("records"), "metrics": metrics, "studio_url": studio_url}
