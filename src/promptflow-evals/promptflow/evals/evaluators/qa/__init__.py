# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from promptflow.entities import AzureOpenAIConnection


def init(model_config: AzureOpenAIConnection, deployment_name: str):
    """
    Initialize an evaluation function configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: AzureOpenAIConnection
    :param deployment_name: Deployment to be used which has Azure OpenAI model.
    :type deployment_name: AzureOpenAIConnection
    :return: A function that evaluates and generates metrics for "question-answering" scenario.
    :rtype: function

    **Usage**

    .. code-block:: python

        eval_fn = qa.init(model_config, deployment_name="gpt-4")
            result = qa_eval(
            question="Tokyo is the capital of which country?",
            answer="Japan",
            context="Tokyo is the capital of Japan.",
            ground_truth="Japan",
    )
    """

    from promptflow.evals.evaluators import groundedness, relevance, coherence, fluency, similarity, f1_score

    groundedness_eval = groundedness.init(model_config, deployment_name=deployment_name)
    relevance_eval = relevance.init(model_config, deployment_name=deployment_name)
    coherence_eval = coherence.init(model_config, deployment_name=deployment_name)
    fluency_eval = fluency.init(model_config, deployment_name=deployment_name)
    similarity_eval = similarity.init(model_config, deployment_name=deployment_name)
    f1_score_eval = f1_score.init()

    def eval_fn(*, answer: str, question: str = None, context: str = None, ground_truth: str = None, **kwargs):

        # TODO: How to parallelize metrics calculation

        return{
            **groundedness_eval(answer=answer, context=context),
            **relevance_eval(answer=answer, question=question, context=context),
            **coherence_eval(answer=answer, question=question),
            **fluency_eval(answer=answer, question=question),
            **similarity_eval(answer=answer, question=question, ground_truth=ground_truth),
            **f1_score_eval(answer=answer, ground_truth=ground_truth)
        }

    return eval_fn
