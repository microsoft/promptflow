# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import os
import re
import shutil
import uuid

from types import FunctionType
from typing import Any, Callable, Dict, Optional, List, Tuple

import pandas as pd

from promptflow.client import PFClient

from ._code_client import CodeClient
from ._utils import save_function_as_flow

from promptflow._sdk._constants import LINE_NUMBER


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
        raise ValueError(
            f"Failed to load data from {data}. Please validate it is a valid jsonl data. Error: {str(e)}.")

    _validate_columns(initial_data_df, evaluators, target)
    return initial_data_df


def _validate_columns(df: pd.DataFrame, evaluators: Dict[str, Any], target: Optional[Callable]) -> None:
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
            _validate_input_data_for_evaluator(evaluator, evaluator_name, df)


def _apply_target_to_data(
        target: Callable,
        data: str,
        pf_client: PFClient,
        initial_data: pd.DataFrame) -> Tuple[str, pd.DataFrame, List[str]]:
    """
    Apply the target function to the data set and save the data to temporary file.

    :keyword target: The function to be applied to data.
    :paramtype target: Callable
    :keyword data: The path to input jsonl file.
    :paramtype data: str
    :keyword pf_client: The promptflow client to be used.
    :paramtype pf_client: PFClient
    :keyword initial_data: The data frame with the loaded data.
    :paramtype initial_data: pd.DataFrame
    :return: The tuple, containing path, data frame and the list of added columns.
    :rtype: Tuple[str, pd.DataFrame, List[str]]
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
    function_output = pf_client.runs.get_details(run, all_results=True)
    # Remove input and output prefix
    re_prefix = re.compile('(outputs[.])|(inputs[.])')
    added_columns = {
        re_prefix.sub('', col) for col in filter(
            lambda x: x.startswith('outputs.'), function_output.columns)}

    rename_dict = {col: re_prefix.sub('', col) for col in function_output.columns}
    function_output.rename(columns=rename_dict, inplace=True)
    drop_columns = set(function_output.columns) - added_columns
    function_output.set_index(LINE_NUMBER, inplace=True)
    function_output.sort_index(inplace=True)
    function_output.reset_index(inplace=True, drop=False)
    # function_output contains only input columns, taken by function,
    # so we need to concatenate it to the input data frame.
    function_output.drop(drop_columns, inplace=True, axis=1)
    function_output = pd.concat([function_output, initial_data], axis=1)
    new_data_name = f'{uuid.uuid1()}.jsonl'
    function_output.to_json(new_data_name, orient='records', lines=True)
    return new_data_name, function_output, added_columns


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

    input_data_df = _validate_and_load_data(
        target, data, evaluators, output_path, tracking_uri, evaluation_name)

    pf_client = PFClient()
    code_client = CodeClient()

    tempfile_created = False
    target_generated_columns = set()
    if data is not None and target is not None:
        data, input_data_df, target_generated_columns = _apply_target_to_data(
            target, data, pf_client, input_data_df)
        # After we have generated all columns we can check if we have
        # everything we need for evaluators.
        _validate_columns(input_data_df, evaluators, None)
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

    if tempfile_created and os.path.isfile(data):
        # During the run we have created the temporary file. We will delete it here.
        os.unlink(data)

    # Rename columns, generated by template function to outputs instead of inputs.
    input_data_df.rename(columns={
        col: f"{'outputs' if col in target_generated_columns else 'inputs'}.{col}" for col in input_data_df.columns},
        inplace=True)

    result_df = pd.concat([input_data_df, evaluators_result_df], axis=1, verify_integrity=True)

    return {"rows": result_df.to_dict("records"), "metrics": _calculate_mean(evaluators_result_df), "traces": {}}
