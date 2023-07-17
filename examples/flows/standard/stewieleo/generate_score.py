from promptflow import tool
import re
import math

def get_score_from_response(response: str, metric: str):
    score_strs = re.findall(f"- {metric.lower()}: [0-9]+", response.lower())
    if len(score_strs) > 0:
        return float(score_strs[0].split(': ')[-1])
    else:
        return float('nan')


def get_score_dict(responses: dict):
    score_dict = {}
    for metric, response in responses.items():
        score_dict[metric] = get_score_from_response(response, metric)
    return score_dict


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(
    relevance_response: str, 
    engagement_response: str, 
    detail_response: str, 
    clarity_response: str,
    relevance_weight: float,
    engagement_weight: float,
    detail_weight: float,
    clarity_weight: float,
) -> object:
    score_dict = get_score_dict({
        'relevance' : relevance_response,
        'engagement' : engagement_response,
        'detail' : detail_response,
        'clarity' : clarity_response,
    })
    
    weight_sum, weighted_score_sum = 0.0, 0.0
    weight_dict = {
        'relevance' : relevance_weight,
        'engagement' : engagement_weight,
        'detail' : detail_weight,
        'clarity' : clarity_weight,
    }
    
    for metric, score in score_dict.items():
        if not math.isnan(score):
            weight_sum += weight_dict[metric]
            weighted_score_sum += weight_dict[metric] * score
    if weight_sum == 0:
        return float('nan')
    return weighted_score_sum / weight_sum
