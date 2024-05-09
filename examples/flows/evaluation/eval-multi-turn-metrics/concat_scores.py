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
                   conversation_quality: str = None,
                   creativity: str = None,
                   grounding: str = None):
    results = {'answer_relevance': get_score(answer_relevance),
               'conversation_quality': get_score(conversation_quality),
               'creativity': get_score(creativity),
               'grounding': grounding}

    return results
