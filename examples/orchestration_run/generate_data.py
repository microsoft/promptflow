import os
from pathlib import Path
from typing import List, NamedTuple

from promptflow import load_data, log_metric, tool


@tool(scope="experiment")
def calculate_accuracy(
    grades_dir: str,
) -> NamedTuple("Output", [("output_dir", str), ("accuracy", float), ("result", List[str])]):
    output_lines = load_data(grades_dir)
    # with open(Path(grades_dir) / "output.jsonl", "r", encoding="utf-8") as f:
    #     output_lines = f.readlines()

    result = []
    for output_dict in output_lines:
        grade = output_dict["grade"]
        result.append(grade)

    # calculate accuracy for each variant
    accuracy = round((result.count("Correct") / len(result)), 2)
    log_metric("accuracy", accuracy)

    output_dir = os.getcwd()
    with open(Path(output_dir) / "grade_result.jsonl", "w", encoding="utf-8") as f:
        f.write(result)

    return {"output_dir": output_dir, "accuracy": accuracy, "result": result}
