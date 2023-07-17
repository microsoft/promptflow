from promptflow import tool
import re

# TODO: import from another file is not supported yet?
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
    final_score: str,
    conversation_id: str,
    query: str,
    config: dict,
) -> object:
    responses = {
        'relevance' : relevance_response,
        'engagement' : engagement_response,
        'detail' : detail_response,
        'clarity' : clarity_response,
    }
    score_dict = get_score_dict(responses)
    
    output_payload = {
        'meta': {
            "metric_key": "stewieleo", 
            "exp_name": config["conversations"]["exp_configs"][0]["exp_name"], 
            "ConversationId": conversation_id,
            "query": query,
        },
        "stewieleo_score": float(final_score),
    }
    
    for key in responses.keys():
        output_payload[key] = {
            'request_payload' : {
                "max_tokens": 1500, 
                "temperature": 0,
                "top_p":1,
                "n": 1,
                "frequency_penalty":0,
                "presence_penalty":0,
                "stop": ["# Overall"],  
            },
            'response_payload' : {
                "choices" : [{
                "text" : responses[key],
                "index" : 0,
                }]
            },
            'score' : score_dict[key],
        }

    return output_payload
