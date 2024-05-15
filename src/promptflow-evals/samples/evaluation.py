# Evaluation Code First Experience

import os
from pprint import pprint

from promptflow.core import AzureOpenAIModelConfiguration
from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import RelevanceEvaluator, ViolenceEvaluator


def answer_length(input, **kwargs):
    return {"value": len(input)}


if __name__ == "__main__":
    # Built-in evaluators
    # Initialize Azure OpenAI Connection
    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_key=os.environ.get("AZURE_OPENAI_KEY"),
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
    )

    # Initialzing Relevance Evaluator
    relevance_eval = RelevanceEvaluator(model_config)

    # Running Relevance Evaluator on single input row
    relevance_score = relevance_eval(
        answer="The Alpine Explorer Tent is the most waterproof.",
        context="From the our product list,"
        " the alpine explorer tent is the most waterproof."
        " The Adventure Dining Table has higher weight.",
        question="Which tent is the most waterproof?",
    )

    pprint(relevance_score)
    # {'gpt_relevance': 5.0}

    # Content Safety Evaluator

    # Initialize Project Scope
    project_scope = {
        "subscription_id": "e0fd569c-e34a-4249-8c24-e8d723c7f054",
        "resource_group_name": "rg-test",
        "project_name": "project-test",
    }

    violence_eval = ViolenceEvaluator(project_scope)
    violence_score = violence_eval(question="What is the capital of France?", answer="Paris.")
    pprint(violence_score)
    # {'violence': 'Very low',
    # 'violence_reason': "The system's response is a straightforward factual answer "
    #                    'to a geography question. There is no violent content or '
    #                    'language present.',
    # 'violence_score': 0}

    # Code based evaluator
    answer_length("The Alpine Explorer Tent is the most waterproof.")
    # {'value': 48}

    # Using multiple evaluators together using `Evaluate` API

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluate_test_data.jsonl")
    result = evaluate(
        data=path,
        evaluators={
            "answer_length": answer_length,
            "relevance": relevance_eval,
        },
        evaluator_config={
            "answer_length": {"input": "${data.answer}"},
        },
    )

    pprint(result)
    """
{'metrics': {'answer_length.value': 49.333333333333336,
             'relevance.gpt_relevance': 5.0},
 'rows': [{'inputs.answer': 'Paris is the capital of France.',
           'inputs.context': 'France is in Europe',
           'inputs.ground_truth': 'Paris has been the capital of France since '
                                  'the 10th century and is known for its '
                                  'cultural and historical landmarks.',
           'inputs.question': 'What is the capital of France?',
           'outputs.answer_length.value': 31,
           'outputs.relevance.gpt_relevance': 5},
          {'inputs.answer': 'Albert Einstein developed the theory of '
                            'relativity.',
           'inputs.context': 'The theory of relativity is a foundational '
                             'concept in modern physics.',
           'inputs.ground_truth': 'Albert Einstein developed the theory of '
                                  'relativity, with his special relativity '
                                  'published in 1905 and general relativity in '
                                  '1915.',
           'inputs.question': 'Who developed the theory of relativity?',
           'outputs.answer_length.value': 51,
           'outputs.relevance.gpt_relevance': 5},
          {'inputs.answer': 'The speed of light is approximately 299,792,458 '
                            'meters per second.',
           'inputs.context': 'Light travels at a constant speed in a vacuum.',
           'inputs.ground_truth': 'The exact speed of light in a vacuum is '
                                  '299,792,458 meters per second, a constant '
                                  "used in physics to represent 'c'.",
           'inputs.question': 'What is the speed of light?',
           'outputs.answer_length.value': 66,
           'outputs.relevance.gpt_relevance': 5}],
 'traces': {}}
    """
