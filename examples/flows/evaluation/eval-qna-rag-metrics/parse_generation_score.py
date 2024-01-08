from promptflow import tool
import re


@tool
def parse_generation_output(rag_generation_score: str) -> str:
    quality_score = float('nan')
    quality_reasoning = ''
    for sent in rag_generation_score.split('\n'):
        sent = sent.strip()
        if re.match(r"\s*(<)?Quality score:", sent):
            numbers_found = re.findall(r"(\d+\.*\d*)\/", sent)
            if len(numbers_found) == 0:
                continue
            quality_score = int(
                float(numbers_found[0].replace("'", "")))

    for sent in rag_generation_score.split('\n'):
        sent = sent.strip()
        if re.match(r"\s*(<)?Quality score reasoning:", sent):
            quality_reasoning += sent.strip()
            break
    return {"quality_score": quality_score, "quality_reasoning": quality_reasoning}
