# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class EvaluationMetrics:
    """Metrics for model evaluation."""

    GPT_GROUNDEDNESS = "gpt_groundedness"
    GPT_RELEVANCE = "gpt_relevance"
    GPT_COHERENCE = "gpt_coherence"
    GPT_FLUENCY = "gpt_fluency"
    GPT_SIMILARITY = "gpt_similarity"
    F1_SCORE = "f1_score"
    GPT_RETRIEVAL_SCORE = "gpt_retrieval_score"
    HATE_FAIRNESS = "hate_fairness"
    HATE_UNFAIRNESS = "hate_unfairness"
    VIOLENCE = "violence"
    SELF_HARM = "self_harm"
    SEXUAL = "sexual"


class Prefixes:
    """Column prefixes for inputs and outputs."""

    INPUTS = "inputs."
    OUTPUTS = "outputs."
    TSG_OUTPUTS = "__outputs."


class SupportedLanguages:
    """Supported languages for evaluation, using ISO standard language codes."""

    Spanish = "es"
    Italian = "it"
    French = "fr"
    German = "de"
    SimplifiedChinese = "zh-cn"
    Portuguese = "pt"
    Japanese = "ja"


DEFAULT_EVALUATION_RESULTS_FILE_NAME = "evaluation_results.json"

CONTENT_SAFETY_DEFECT_RATE_THRESHOLD_DEFAULT = 4

PF_BATCH_TIMEOUT_SEC_DEFAULT = 3600
PF_BATCH_TIMEOUT_SEC = "PF_BATCH_TIMEOUT_SEC"
