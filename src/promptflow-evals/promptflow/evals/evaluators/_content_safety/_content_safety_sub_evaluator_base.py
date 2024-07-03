from pathlib import Path

from promptflow.client import load_flow

from .flow.constants import EvaluationMetrics
from .flow.evaluate_with_rai_service import evaluate_with_rai_service
from .flow.validate_inputs import validate_inputs

class ContentSafetySubEvaluatorBase:
    """
    Initialize a evaluator for a specified Evaluation Metric. Base class that is not
    meant to be instantiated by users.

    
    :param metric: The metric to be evaluated.
    :type metric: ~promptflow.evals.evaluators._content_safety.flow.constants.EvaluationMetrics
    :param project_scope: The scope of the Azure AI project.
        It contains subscription id, resource group, and project name.
    :type project_scope: dict
    :param credential: The credential for connecting to Azure AI project.
    :type credential: TokenCredential
    """

    def __init__(self,  metric: EvaluationMetrics, project_scope: dict, credential=None):
        self._metric = metric
        self._project_scope = project_scope
        self._credential = credential

        # Load the flow as function
        current_dir = Path(__file__).resolve().parent
        flow_dir = current_dir / "flow"
        self._flow = load_flow(source=flow_dir)

    def __call__(self, *, question: str, answer: str, **kwargs):
        """
        Evaluates content according to this evaluator's metric.

        :param question: The question to be evaluated.
        :type question: str
        :param answer: The answer to be evaluated.
        :type answer: str
        :return: The evaluation score.
        :rtype: dict
        """


        # Validate inputs
        # Raises value error if failed, so execution alone signifies success.
        _ = validate_inputs(question=question, answer=answer)

        #question: str, answer: str, metric_name: str, project_scope: dict, credential: TokenCredential
        # Run f1 score computation.
        result = evaluate_with_rai_service(
            metric_name=self._metric,
            question=question,
            answer=answer,
            project_scope=self._project_scope,
            credential=self._credential,
        )
        return {"result": result}
