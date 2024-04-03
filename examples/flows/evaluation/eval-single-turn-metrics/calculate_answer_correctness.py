from promptflow.core import tool
import json
import numpy as np


@tool
def calculate(statement_result: str, similarity_score: str) -> str:
    try:
        weights: list[float] = [0.75, 0.25]

        key_map = {
                "TP": "statements that are present in both the answer and the ground truth",
                "FP": "statements present in the answer but not found in the ground truth",
                "FN": "relevant statements found in the ground truth but omitted in the answer",  # noqa: E501
            }

        score = 0
        result = json.loads(statement_result)
        if result:
            prediction = [
                result.get(key_map[k], np.nan)
                for k in key_map.keys()
            ]

            tp, fp, fn = [
                len(item) if isinstance(item, list) else np.nan
                for item in prediction
            ]
            score = 5 * tp / (tp + 0.5 * (fp + fn))

        final_score = weights[0] * score + weights[1] * int(similarity_score)

        print(score)
        print(similarity_score)

        return final_score if final_score >= 1 else 1
    except Exception as e:
        print("exception in calculate_answer_correctness: " + str(e))
        print("statement_result: " + statement_result)
        return np.nan
