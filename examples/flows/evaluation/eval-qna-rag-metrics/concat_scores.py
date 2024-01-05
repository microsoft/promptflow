from promptflow import tool
import numpy as np


@tool
def concat_results(rag_retrieval_score: dict = None,
                   rag_grounding_score: dict = None, rag_generation_score: dict = None):

    load_list = [{'name': 'gpt_groundedness', 'result': rag_grounding_score},
                 {'name': 'gpt_retrieval_score', 'result': rag_retrieval_score},
                 {'name': 'gpt_relevance', 'result': rag_generation_score}]
    score_list = []
    errors = []
    for item in load_list:
        if item['result']:
            try:
                score = float(item['result']["quality_score"])
            except Exception as e:
                score = np.nan
                errors.append({"name": item["name"], "msg":  str(e), "data": item['result']})
            reasoning = item['result']['quality_reasoning']
        else:
            score = np.nan
            reasoning = None
        score_list.append({"name": item["name"], "score": score, "quality_reasoning": reasoning})
    variant_level_result = {}
    for item in score_list:
        item_name = str(item["name"])
        variant_level_result[item_name] = item["score"]
    return variant_level_result
