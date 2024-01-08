from promptflow import tool
import re


@tool
def parse_retrieval_output(retrieval_output: str) -> str:
    score_response = [sent.strip() for sent in
                      retrieval_output.strip("\"").split("# Result")[-1].strip().split('.') if sent.strip()]
    parsed_score_response = re.findall(r"\d+", score_response[-1])
    if len(parsed_score_response) > 0:
        score = parsed_score_response[-1].strip()
        if float(score) < 1.0 or float(score) > 5.0:
            score = float('nan')
    else:
        score = float('nan')
    try:
        reasoning_response, _ = retrieval_output.split("# Result")
    except Exception:
        reasoning_response = retrieval_output
    return {"quality_score": float(score), "quality_reasoning": reasoning_response}
