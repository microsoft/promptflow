import os
import string
from abc import ABC

import nltk.translate.bleu_score

from promptflow.core import Prompty

from ._utils import nltk_tokenize


class EvaluatorBase(ABC):
    def __init__(self, aggregation_type: str = "mean"):
        self.aggregation_type = aggregation_type

    def metric_name(self):
        pass

    def __aggregate__(self, line_results) -> dict:
        scores = [line_result[self.metric_name] for line_result in line_results]
        if self.aggregation_type == "mean":
            return {f"{self.metric_name}_mean": sum(scores) / len(scores)}
        elif self.aggregation_type == "sum":
            return {f"{self.metric_name}_sum": sum(scores)}


# --- Bleu ---
class BleuScoreEvaluator(EvaluatorBase):
    def __init__(self, aggregation_type: str = "mean"):
        super().__init__(aggregation_type)

    @property
    def metric_name(self):
        return "bleu_score"

    def __call__(self, *, reference: str, hypothesis: str, **kwargs):
        """Evaluate BLEU score."""
        reference_tokens = nltk_tokenize(reference)
        hypothesis_tokens = nltk_tokenize(hypothesis)

        smoothing_function = nltk.translate.bleu_score.SmoothingFunction().method4
        score = nltk.translate.bleu_score.sentence_bleu(
            [reference_tokens], hypothesis_tokens, smoothing_function=smoothing_function
        )
        assert isinstance(score, (float, int))

        return {self.metric_name: score}


# --- String Count ---
class StringCountEvaluator(EvaluatorBase):
    def __init__(self, aggregation_type: str = "mean", case_sensitive: bool = False):
        super().__init__(aggregation_type)
        self.case_sensitive = case_sensitive

    @property
    def metric_name(self):
        return "string_count"

    def __call__(self, *, reference: str, hypothesis: str, **kwargs):
        reference = str(reference)
        hypothesis = str(hypothesis)
        if not self.case_sensitive:
            reference = reference.lower()
            hypothesis = hypothesis.lower()
        count = reference.count(hypothesis)
        return {self.metric_name: count}


# --- Set Membership ---
class SetMembershipEvaluator(EvaluatorBase):
    def __init__(
        self,
        aggregation_type: str = "mean",
        present_grade: float = 1.0,
        absent_grade: float = 0.0,
        case_sensitive: bool = False,
    ):
        super().__init__(aggregation_type)
        self.present_grade = present_grade
        self.absent_grade = absent_grade
        self.case_sensitive = case_sensitive

    @property
    def metric_name(self):
        return "set_membership"

    def __call__(self, *, element: str, set: list, **kwargs):
        if not self.case_sensitive:
            element = element.lower()
            set = [x.lower() for x in set]

        return {self.metric_name: self.present_grade if element in set else self.absent_grade}


# --- Closed QA Model ---
class ClosedQAModelEvaluator(EvaluatorBase):
    def __init__(self, model_config, true_grade: float, false_grade: float, aggregation_type: str = "sum"):
        super().__init__(aggregation_type)

        if model_config.api_version is None:
            model_config.api_version = "2024-02-15-preview"

        self.true_grade = true_grade
        self.false_grade = false_grade

        prompty_model_config = {"configuration": model_config}
        current_dir = os.path.dirname(__file__)
        prompty_path = os.path.join(current_dir, "closed_qa.prompty")

        self._flow = Prompty.load(source=prompty_path, model=prompty_model_config)

    @property
    def metric_name(self):
        return "closed_qa"

    def __call__(self, *, task: str, submission: str, criterion: str, **kwargs):
        llm_output = self._flow(task=task, submission=submission, criterion=criterion, timeout=600)
        grades = {
            "y": self.true_grade,
            "n": self.false_grade,
        }

        lines = llm_output.splitlines()
        lines = [line for line in lines if line]
        cleaned_last_line = "".join(c for c in lines[-1] if c not in string.punctuation).lower().strip()

        return {self.metric_name: grades.get(cleaned_last_line, self.false_grade)}
