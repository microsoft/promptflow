# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow.evals.synthetic.constants import SupportedLanguages

BASE_SUFFIX = "Make the conversation in __language__ language."

SUPPORTED_LANGUAGES_MAPPING = {
    SupportedLanguages.English: BASE_SUFFIX.replace("__language__", "english"),
    SupportedLanguages.Spanish: BASE_SUFFIX.replace("__language__", "spanish"),
    SupportedLanguages.Italian: BASE_SUFFIX.replace("__language__", "italian"),
    SupportedLanguages.French: BASE_SUFFIX.replace("__language__", "french"),
    SupportedLanguages.German: BASE_SUFFIX.replace("__language__", "german"),
    SupportedLanguages.SimplifiedChinese: BASE_SUFFIX.replace("__language__", "simplified chinese"),
    SupportedLanguages.Portuguese: BASE_SUFFIX.replace("__language__", "portuguese"),
    SupportedLanguages.Japanese: BASE_SUFFIX.replace("__language__", "japanese"),
}
