# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Grader Utils."""

from functools import lru_cache
from typing import List, Set, cast

import nltk

try:
    from nltk.tokenize.nist import NISTTokenizer
except LookupError:
    nltk.download("perluniprops")
    nltk.download("punkt")
    from nltk.tokenize.nist import NISTTokenizer


@lru_cache(maxsize=1)
def _nist_tokenizer() -> NISTTokenizer:
    # if necessary, lazy import NISTTokenizer because it requires perluniprops.
    return NISTTokenizer()


def is_latin_or_numeric(s: str) -> bool:
    """
    Use character range check to determine how to tokenize a string.

    TODO: Support emojis, right now they are marked as non latin.
    """
    return all(
        ("\u0020" <= c <= "\u007E")  # Basic Latin (includes numbers)
        or ("\u00A0" <= c <= "\u00FF")  # Latin-1 Supplement
        or ("0" <= c <= "9")  # Digits
        for c in s
    )


def nltk_tokenize(s: str) -> List[str]:
    """Tokenizer for bleu grader."""
    if is_latin_or_numeric(s):
        return cast(List[str], nltk.word_tokenize(s))
    return list(_nist_tokenizer().international_tokenize(s))


def split_non_empty(s: str, delimiter: str, *, lower: bool) -> Set[str]:
    """Split Non-Empty string."""
    values = (value.strip() for value in s.split(delimiter))
    if lower:
        values = (value.lower() for value in values)
    return {value for value in values if value}


def div_or_zero(a: float, b: float) -> float:
    """div_or_zero."""
    return a / b if b != 0 else 0
