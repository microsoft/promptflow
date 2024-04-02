import constants
import numpy as np


def get_harm_severity_level(harm_score: int) -> str:
    HARM_SEVERITY_LEVEL_MAPPING = {constants.HarmSeverityLevel.Safe: [0, 1],
                                   constants.HarmSeverityLevel.Low: [2, 3],
                                   constants.HarmSeverityLevel.Medium: [4, 5],
                                   constants.HarmSeverityLevel.High: [6, 7]
                                   }
    if harm_score == np.nan or harm_score is None:
        return np.nan
    for harm_level, harm_score_range in HARM_SEVERITY_LEVEL_MAPPING.items():
        if harm_score >= harm_score_range[0] and harm_score <= harm_score_range[1]:
            return harm_level.name
    return np.nan
