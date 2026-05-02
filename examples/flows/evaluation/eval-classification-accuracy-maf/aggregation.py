from typing import Dict, List


def aggregate(grades: List[str]) -> Dict[str, float]:
    accuracy = round((grades.count("Correct") / len(grades)), 2) if grades else 0.0
    return {"accuracy": accuracy}
