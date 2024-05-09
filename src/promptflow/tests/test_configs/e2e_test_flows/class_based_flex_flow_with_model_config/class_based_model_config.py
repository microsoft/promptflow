# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import TypedDict

from promptflow.tracing import trace
from promptflow.core import AzureOpenAIModelConfiguration


class Result(TypedDict):
    correct: bool
    original_answer: str


class EvalFlow:
    def __init__(self, model_config: AzureOpenAIModelConfiguration):
        self.model_config = model_config

    @trace
    def __call__(
        self, answer: str = "ChatGPT is a language model", expected_word: str = "ChatGPT"
    ) -> Result:
        """Flow entry function."""

        return Result(
            correct=expected_word in answer,
            original_answer=answer,
        )

    def __aggregate__(self, line_results: list) -> dict:
        """Aggregate the results."""
        total = len(line_results)
        total_correct = len([r for r in line_results if bool(r["correct"])])
        return {
            "total_correct": total_correct,
            "total": total,
        }
