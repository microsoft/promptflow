# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from enum import Enum


class SupportedLanguages(Enum):
    """Supported languages for evaluation, using ISO standard language codes."""

    Spanish = "es"
    Italian = "it"
    French = "fr"
    German = "de"
    SimplifiedChinese = "zh-cn"
    Portuguese = "pt"
    Japanese = "ja"
    English = "en"
