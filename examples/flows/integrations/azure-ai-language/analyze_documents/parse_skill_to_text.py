from promptflow.core import tool


@tool
def parse_skill_to_text(output: object, skill: str) -> str:
    """
    This tool parses a language skill result into a string,
    when possible. Not all skills give logical string parsings.

    :param output: skill output.
    :param skill: skill type to parse.
    """
    result = None
    if skill == "TRANSLATION":
        # Translation: return first translation.
        result = output["translations"][0]["text"]
    if skill == "PII":
        # PII: return redacted text.
        result = output["redactedText"]
    elif skill == "ABSTRACTIVE":
        # Abstractive summarization: return summary.
        result = output["summaries"][0]["text"]

    if result is None:
        raise RuntimeError("Unsupported skill parsing.")

    return result
