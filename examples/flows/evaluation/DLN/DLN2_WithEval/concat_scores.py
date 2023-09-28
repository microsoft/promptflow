from promptflow import tool
import numpy as np
import re


@tool
def concat_results(trainable_prompt_pi_num:int,return_result: str):
    return {    
        "trainable_prompt_pi_num": trainable_prompt_pi_num,
        "return_result": return_result
    }
