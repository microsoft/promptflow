from promptflow.evals import evaluate
from pprint import pprint

def answer_length(answer, **kwargs):
    return {
        "value": len(answer)
    }


def answer_length_percentage(answer, **kwargs):
    return {
        "value": len(answer)/100
    }


if __name__ == "__main__":
    result = evaluate(
        data="eval_results.jsonl",
        evaluators={
            "answer_length": answer_length,
            "answer_length_percentage": answer_length_percentage,
        },
    )

    pprint(result)
