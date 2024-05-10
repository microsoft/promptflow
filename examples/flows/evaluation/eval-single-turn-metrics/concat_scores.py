from promptflow.core import tool
import json


def get_score(result):
    try:
        if result is not None:
            # Parse the JSON string
            result_dict = json.loads(result)

            # Extract the score value
            score = result_dict.get('score', None)
            print("result: ")
            print(score)
            return score
        else:
            return None
    except json.JSONDecodeError:
        print("Invalid JSON string.")
        return None


@tool
def concat_results(answer_relevance: str = None,
                   answer_quality: str = None,
                   creativity: str = None,
                   grounding: str = None,
                   context_recall: str = None,
                   context_precision: str = None,
                   answer_similarity: str = None,
                   answer_correctness: str = None):

    results = {'answer_relevance': answer_relevance,
               'answer_quality': get_score(answer_quality),
               'creativity': get_score(creativity),
               'grounding': grounding,
               'context_recall': context_recall,
               'context_precision': context_precision,
               'answer_similarity': answer_similarity,
               'answer_correctness': answer_correctness}

    return results
