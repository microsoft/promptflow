from promptflow.core import tool


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def select_metrics(metrics: str) -> dict:
    supported_metrics = ('answer_relevance', 'conversation_quality', 'creativity', 'grounding')
    user_selected_metrics = [metric.strip() for metric in metrics.split(',') if metric]
    metric_selection_dict = {}
    for metric in supported_metrics:
        if metric in user_selected_metrics:
            metric_selection_dict[metric] = True
        else:
            metric_selection_dict[metric] = False
    return metric_selection_dict
