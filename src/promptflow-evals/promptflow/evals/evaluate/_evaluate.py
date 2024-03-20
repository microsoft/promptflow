# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from json import JSONDecodeError
from pathlib import Path
from typing import Optional, Dict, Union, Callable

import numpy as np
import pandas as pd

from ._utils import load_jsonl
from ._flow_run_wrapper import FlowRunWrapper
from promptflow import PFClient


def _calculate_mean(df) -> Dict[str, float]:
    mean_value = df.mean(numeric_only=True)
    return mean_value.to_dict()


def _validation(target, data, evaluators, output_path, tracking_uri, evaluation_name):
    if target is None and data is None:
        raise ValueError("Either target or data must be provided for evaluation.")

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

    evaluator_run_list = []
    pf_client = PFClient()

    for evaluator_name, evaluator in evaluators.items():
        evaluator_run_list.append(FlowRunWrapper(pf_client.run(
            flow=evaluator,
            column_mapping=evaluator_config.get(evaluator_name, evaluator_config.get("default", None)),
            data=data,
            stream=True
        ),
            prefix=evaluator_name
        ))

    result_df = None
    for eval_run in evaluator_run_list:
        if result_df is None:
            result_df = eval_run.get_result_df(all_results=True, exclude_inputs=True)
        else:
            result_df = pd.concat(
                [eval_run.get_result_df(all_results=True, exclude_inputs=True), result_df],
                axis=1,
                verify_integrity=True
            )

    input_data_df = pd.read_json(data, lines=True)
    input_data_df = input_data_df.rename(columns={col: f"inputs.{col}" for col in input_data_df.columns})

    row_results = pd.concat([input_data_df, result_df], axis=1, verify_integrity=True)

    return {
        "rows": row_results.to_dict("records"),
        "metrics": _calculate_mean(result_df),
        "traces": {}
    }
