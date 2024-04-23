# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import os
import shutil
import uuid

from types import FunctionType
from typing import Any, Callable, Dict, Optional, List

import pandas as pd

from promptflow.client import PFClient

from ._code_client import CodeClient
from ._utils import save_function_as_flow

from promptflow._sdk._constants import LINE_NUMBER


def _calculate_mean(df) -> Dict[str, float]:
    df.rename(columns={col: col.replace("outputs.", "") for col in df.columns}, inplace=True)
    mean_value = df.mean(numeric_only=True)
    return mean_value.to_dict()


def _get_missing_inputs(evaluator, columns):
    required_inputs = [
        param.name
        for param in inspect.signature(evaluator).parameters.values()
        if param.default == inspect.Parameter.empty and param.name not in ["kwargs", "args", "self"]
    ]

    return [col for col in required_inputs if col not in columns]


def _validate_data(data):
    if data is None:
        raise ValueError("data must be provided for evaluation.")

    if data is not None:
        if not isinstance(data, str):
            raise ValueError("data must be a string.")


def _validate_input_data_for_evaluator(evaluator, evaluator_name, columns, is_target_fn=False):
    missing_inputs = _get_missing_inputs(evaluator, columns)
    if missing_inputs:
        if not is_target_fn:
            raise ValueError(f"Missing required inputs for evaluator {evaluator_name} : {missing_inputs}.")
        else:
            raise ValueError(f"Missing required inputs for target : {missing_inputs}.")


def _validation(target, columns, evaluators, output_path, tracking_uri, evaluation_name):

    if target is not None:
        if not callable(target):
            raise ValueError("target must be a callable function.")

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

    _validate_columns(columns, evaluators, target)


def _get_data_columns(data: str) -> List[str]:
    """
    Read the data and return the list of columns, if data is None, return empty list.

    :keyword data: The path to jsonl file.
    :paramtype data: str
    :return: The list of columns or empty list.
    :rtype: List[str]
    :raises: ValueError
    """
    try:
        data_df = pd.read_json(data, lines=True)
    except Exception as e:
        raise ValueError(
            f"Failed to load data from {data}. Please validate it is a valid jsonl data. Error: {str(e)}.")
    return list(data_df.columns)


def _validate_columns(columns: List[str], evaluators: Dict[str, Any], target: Optional[Callable]) -> None:
    """
    Check that all columns needed by evaluator or target function are present.

    :keyword columns: The list of column in the data frame.
    :paramtype columns: List[str]
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
        _validate_input_data_for_evaluator(target, None, columns, is_target_fn=True)
    else:
        for evaluator_name, evaluator in evaluators.items():
            _validate_input_data_for_evaluator(evaluator, evaluator_name, columns)


def _apply_target_to_data(target: Callable, data: str, pf_client: PFClient) -> str:
    """
    Apply the target function to the data set and save the data to temporary file.

    :keyword target: The function to be applied to data.
    :paramtype target: Callable
    :keyword data: The path to input jsonl file.
    :paramtype data: str
    :keyword pf_client: The promptflow client to be used.
    :paramtype pf_client: PFClient
    :return: The path to data file with answers from target function.
    :rtype: str
    """
    # We are manually creating the temporary directory for the flow
    # because the way tempdir remove temporary directories will
    # hang the debugger, because promptflow will keep flow directory.
    saved_flow = f'flow_{uuid.uuid1()}'
    os.makedirs(saved_flow)
    save_function_as_flow(fun=target, target_dir=saved_flow, pf=pf_client)
    run = pf_client.run(
        flow=saved_flow,
        data=data,
        name=f'preprocess_{uuid.uuid1()}'
    )
    run = pf_client.stream(run)
    # Delete temporary directory if we can.
    try:
        shutil.rmtree(saved_flow)
    except BaseException:
        # Exception means, we are running in debugger. In this case we can keep the
        # directory.
        pass
    function_output = pd.read_json(pf_client.runs._get_outputs_path(run),
                                   orient='records', lines=True)
    function_output.set_index(LINE_NUMBER, inplace=True)
    function_output.sort_index(inplace=True)
    data_input = pd.read_json(data, orient='records', lines=True)
    data_input = pd.concat([data_input, function_output], axis=1, verify_integrity=True)
    del function_output
    new_data_name = f'{uuid.uuid1()}.jsonl'
    data_input.to_json(new_data_name, orient='records', lines=True)
    return new_data_name


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

    _validate_data(data)
    initial_columns = _get_data_columns(data)
    _validation(target, initial_columns, evaluators, output_path, tracking_uri, evaluation_name)

    pf_client = PFClient()
    code_client = CodeClient()

    tempfile_created = False
    if data is not None and target is not None:
        data = _apply_target_to_data(target, data, pf_client)
        # After we have generated all columns we can check if we have
        # everything we need for evaluators.
        new_columns = _get_data_columns(data)
        _validate_columns(new_columns, evaluators, None)
        tempfile_created = True

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
    if tempfile_created:
        # During the run we have created the temporary file. We will delete it here.
        os.unlink(data)

    # Rename columns, generated by template function to outputs instead of inputs.
    template_generated_columns = set(input_data_df) - set(initial_columns)
    input_data_df.rename(columns={
        col: f"{'outputs' if col in template_generated_columns else 'inputs'}.{col}" for col in input_data_df.columns},
        inplace=True)

    result_df = pd.concat([input_data_df, evaluators_result_df], axis=1, verify_integrity=True)

    return {"rows": result_df.to_dict("records"), "metrics": _calculate_mean(evaluators_result_df), "traces": {}}
