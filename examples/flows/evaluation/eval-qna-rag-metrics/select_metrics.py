from promptflow import tool


@tool
def select_metrics(metrics: str) -> str:
    supported_metrics = ('gpt_relevance', 'gpt_groundedness', 'gpt_retrieval_score')
    user_selected_metrics = [metric.strip() for metric in metrics.split(',') if metric]
    metric_selection_dict = {}
    for metric in supported_metrics:
        if metric in user_selected_metrics:
            metric_selection_dict[metric] = True
        else:
            metric_selection_dict[metric] = False
    return metric_selection_dict
