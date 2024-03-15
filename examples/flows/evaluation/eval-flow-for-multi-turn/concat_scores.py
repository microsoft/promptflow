from promptflow import tool
import numpy as np
import re
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
def concat_results(answer_relevancy: str = None,
                   answer_quality: str = None,
                   creativity: str = None,
                   grounding: str = None):
    
    results = {'answer_relevancy': get_score(answer_relevancy),
                'answer_quality': get_score(answer_quality),
                'creativity': get_score(creativity),
                'grounding': grounding}
   
    return results
