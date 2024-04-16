from promptflow.core import tool


@tool
def extract_language_code(ld_output: dict) -> str:
    """
    This tool extracts the ISO 639-1 language code
    from language detection output.

    :param ld_output: language detection output (parsed).
    """
    return ld_output["detectedLanguage"]["iso6391Name"]
