# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import asyncio

from promptflow._utils.async_utils import async_run_allowing_running_loop

try:
    from ._hate_unfairness import HateUnfairnessEvaluator
    from ._self_harm import SelfHarmEvaluator
    from ._sexual import SexualEvaluator
    from ._violence import ViolenceEvaluator
except ImportError:
    from _hate_unfairness import HateUnfairnessEvaluator
    from _self_harm import SelfHarmEvaluator
    from _sexual import SexualEvaluator
    from _violence import ViolenceEvaluator


class _AsyncContentSafetyEvaluator:
    def __init__(self, project_scope: dict, parallel: bool = True, credential=None):
        self._parallel = parallel
        self._evaluators = [
            ViolenceEvaluator(project_scope, credential)._to_async(),
            SexualEvaluator(project_scope, credential)._to_async(),
            SelfHarmEvaluator(project_scope, credential)._to_async(),
            HateUnfairnessEvaluator(project_scope, credential)._to_async(),
        ]

    async def __call__(self, *, question: str, answer: str, **kwargs):
        results = {}

        if self._parallel:
            tasks = []
            for evaluator in self._evaluators:
                tasks.append(asyncio.create_task(evaluator(question=question, answer=answer, **kwargs)))
            completed_results = await asyncio.gather(*tasks)
            for result in completed_results:
                results.update(result)
        else:
            for evaluator in self._evaluators:
                result = await evaluator(question=question, answer=answer, **kwargs)
                results.update(result)

        return results


class ContentSafetyEvaluator:
    """
    Initialize a content safety evaluator configured to evaluate content safetry metrics for QA scenario.

    :param project_scope: The scope of the Azure AI project.
        It contains subscription id, resource group, and project name.
    :type project_scope: dict
    :param parallel: If True, use parallel execution for evaluators. Else, use sequential execution.
        Default is True.
    :param credential: The credential for connecting to Azure AI project.
    :type credential: ~azure.core.credentials.TokenCredential
    :return: A function that evaluates content-safety metrics for "question-answering" scenario.
    :rtype: Callable

    **Usage**

    .. code-block:: python

        project_scope = {
            "subscription_id": "<subscription_id>",
            "resource_group_name": "<resource_group_name>",
            "project_name": "<project_name>",
        }
        eval_fn = ContentSafetyEvaluator(project_scope)
        result = eval_fn(
            question="What is the capital of France?",
            answer="Paris.",
        )

    **Output format**

    .. code-block:: python

        {
            "violence": "Medium",
            "violence_score": 5.0,
            "violence_reason": "Some reason",
            "sexual": "Medium",
            "sexual_score": 5.0,
            "sexual_reason": "Some reason",
            "self_harm": "Medium",
            "self_harm_score": 5.0,
            "self_harm_reason": "Some reason",
            "hate_unfairness": "Medium",
            "hate_unfairness_score": 5.0,
            "hate_unfairness_reason": "Some reason"
        }
    """

    def __init__(self, project_scope: dict, parallel: bool = True, credential=None):
        self._async_evaluator = _AsyncContentSafetyEvaluator(project_scope, parallel, credential)

    def __call__(self, *, question: str, answer: str, **kwargs):
        """
        Evaluates content-safety metrics for "question-answering" scenario.

        :keyword question: The question to be evaluated.
        :paramtype question: str
        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :keyword parallel: Whether to evaluate in parallel.
        :paramtype parallel: bool
        :return: The scores for content-safety.
        :rtype: dict
        """
        return async_run_allowing_running_loop(self._async_evaluator, question=question, answer=answer, **kwargs)

    def _to_async(self):
        return self._async_evaluator
