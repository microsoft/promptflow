from promptflow.core import tool


@tool
def select_metrics(metrics: str) -> str:
    supported_metrics = ('grounding',
                         'answer_relevance',
                         'answer_quality',
                         'context_recall',
                         'context_precision',
                         'answer_similarity',
                         'answer_correctness',
                         'creativity')
    user_selected_metrics = [metric.strip() for metric in metrics.split(',') if metric]
    metric_selection_dict = {}
    for metric in supported_metrics:
        if metric in user_selected_metrics:
            metric_selection_dict[metric] = True
        else:
            metric_selection_dict[metric] = False
    return metric_selection_dict
