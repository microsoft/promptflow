from abc import ABC, abstractproperty
from dataclasses import dataclass

import nltk.translate.bleu_score

from ._utils import nltk_tokenize


@dataclass
class EvaluatorConfigBase:
    aggregation_type: str = "mean"


class EvaluatorBase(ABC):
    def __init__(self, config: EvaluatorConfigBase):
        self.config = config

    @abstractproperty
    def metric_name(self):
        pass

    def __aggregate__(self, line_results) -> dict:
        scores = [line_result[self.metric_name] for line_result in line_results]
        if self.config.aggregation_type == "mean":
            return {f"{self.metric_name}_mean": sum(scores) / len(scores)}
        elif self.config.aggregation_type == "sum":
            return {f"{self.metric_name}_sum": sum(scores)}


# --- Bleu ---
@dataclass
class BleuScoreEvaluatorConfig(EvaluatorConfigBase):
    pass


class BleuScoreEvaluator(EvaluatorBase):
    def __init__(self, config=BleuScoreEvaluatorConfig()):
        super().__init__(config)

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
@dataclass
class StringCountEvaluatorConfig(EvaluatorConfigBase):
    case_sensitive: bool = False


class StringCountEvaluator(EvaluatorBase):
    def __init__(self, config=StringCountEvaluatorConfig()):
        super().__init__(config)
        self.case_sensitive = config.case_sensitive

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
@dataclass
class SetMembershipEvaluatorConfig(EvaluatorConfigBase):
    present_grade: float = 1.0
    absent_grade: float = 0.0
    case_sensitive: bool = False


class SetMembershipEvaluator(EvaluatorBase):
    def __init__(self, config=SetMembershipEvaluatorConfig()):
        super().__init__(config)
        self.present_grade = config.present_grade
        self.absent_grade = config.absent_grade
        self.case_sensitive = config.case_sensitive

    @property
    def metric_name(self):
        return "set_membership"

    def __call__(self, *, element: str, set: list, **kwargs):
        if not self.case_sensitive:
            element = element.lower()
            set = [x.lower() for x in set]

        return {self.metric_name: self.present_grade if element in set else self.absent_grade}
