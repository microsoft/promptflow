from promptflow import tool
import numpy as np
import re


@tool
def concat_results(gpt_coherence_score: str = None,
                   gpt_similarity_score: str = None,
                   gpt_fluency_score: str = None,
                   gpt_relevance_score: str = None,
                   gpt_groundedness_score: str = None,
                   f1_score: float = None,
                   ada_cosine_similarity: float = None):

    load_list = [{'name': 'gpt_coherence', 'score': gpt_coherence_score},
                 {'name': 'gpt_similarity', 'score': gpt_similarity_score},
                 {'name': 'gpt_fluency', 'score': gpt_fluency_score},
                 {'name': 'gpt_relevance', 'score': gpt_relevance_score},
                 {'name': 'gpt_groundedness', 'score': gpt_groundedness_score},
                 {'name': 'f1_score', 'score': f1_score},
                 {'name': 'ada_similarity', 'score': ada_cosine_similarity}]

    scalar_metrics = ["f1_score", "ada_similarity"]
    score_list = []
    errors = []
    for item in load_list:
        if item["name"] in scalar_metrics:
            try:
                score = float(item["score"])
            except Exception as e:
                score = np.nan
                errors.append({"name": item["name"], "msg":   str(e), "data": item["score"]})
        else:
            if item['score']:
                try:
                    score = item["score"]
                    match = re.search(r'\d', score)
                    if match:
                        score = float(match.group())
                    else:
                        score = np.nan
                except Exception as e:
                    score = np.nan
                    errors.append({"name": item["name"], "msg":   str(e), "data": item["score"]})
            else:
                score = np.nan
        score_list.append({"name": item["name"], "score": score})

    variant_level_result = {}
    for item in score_list:
        item_name = str(item["name"])
        variant_level_result[item_name] = item["score"]
        if 'gpt' in item_name:
            variant_level_result[item_name + '_pass_rate'] = 1 if item["score"] > 3 else 0
    return variant_level_result
