from promptflow import tool
import re


@tool
def parse_grounding_output(rag_grounding_score: str) -> str:
    try:
        numbers_found = re.findall(r"Quality score:\s*(\d+)\/\d", rag_grounding_score)
        score = float(numbers_found[0]) if len(numbers_found) > 0 else 0
    except Exception:
        score = float("nan")
    try:
        quality_reasoning, _ = rag_grounding_score.split("Quality score: ")
    except Exception:
        quality_reasoning = rag_grounding_score
    return {"quality_score": score, "quality_reasoning": quality_reasoning}
