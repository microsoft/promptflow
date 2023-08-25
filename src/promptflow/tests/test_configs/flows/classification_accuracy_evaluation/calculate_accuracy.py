from typing import List

from promptflow import log_metric, tool


@tool
def calculate_accuracy(grades: List[str], variant_ids: List[str]):
    aggregate_grades = {}
    for index in range(len(grades)):
        grade = grades[index]
        variant_id = variant_ids[index]
        if variant_id not in aggregate_grades.keys():
            aggregate_grades[variant_id] = []
        aggregate_grades[variant_id].append(grade)

    # calculate accuracy for each variant
    for name, values in aggregate_grades.items():
        accuracy = round((values.count("Correct") / len(values)), 2)
        log_metric("accuracy", accuracy, variant_id=name)

    return aggregate_grades
