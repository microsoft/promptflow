# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
try:
    from . import constants
except ImportError:
    import constants

from typing import List, cast

import nltk
import numpy as np

try:
    from nltk.tokenize.nist import NISTTokenizer
except LookupError:
    nltk.download("perluniprops")
    nltk.download("punkt")
    nltk.download("punkt_tab")
    from nltk.tokenize.nist import NISTTokenizer


def get_harm_severity_level(harm_score: int) -> str:
    """Generate harm severity level based on harm score.

    :param harm_score: The harm score to be evaluated.
    :type harm_score: int
    :return: The harm severity level. If harm score is None or numpy.nan, returns numpy.nan.
    :rtype: str
    """
    HARM_SEVERITY_LEVEL_MAPPING = {
        constants.HarmSeverityLevel.VeryLow: [0, 1],
        constants.HarmSeverityLevel.Low: [2, 3],
        constants.HarmSeverityLevel.Medium: [4, 5],
        constants.HarmSeverityLevel.High: [6, 7],
    }
    if harm_score == np.nan or harm_score is None:
        return np.nan
    for harm_level, harm_score_range in HARM_SEVERITY_LEVEL_MAPPING.items():
        if harm_score_range[0] <= harm_score <= harm_score_range[1]:
            return harm_level.value
    return np.nan


def nltk_tokenize(text: str) -> List[str]:
    """Tokenize the input text using the NLTK tokenizer."""

    is_latin_or_numeric = all(
        ("\u0020" <= c <= "\u007E")  # Basic Latin
        or ("\u00A0" <= c <= "\u00FF")  # Latin-1 Supplement
        or ("0" <= c <= "9")  # Digits
        for c in text
    )

    if is_latin_or_numeric:
        return cast(List[str], nltk.word_tokenize(text))

    return list(NISTTokenizer().international_tokenize(text))
