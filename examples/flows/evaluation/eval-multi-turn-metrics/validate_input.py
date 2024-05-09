from promptflow.core import tool


# Validate the metric's inputs.
def is_valid(metric):
    return True


@tool
def validate_input(chat_history: list, selected_metrics: dict) -> dict:
    dict_metric_required_fields = {"answer_relevance": set(["question", "answer"]),
                                   "conversation_quality": set(["question", "answer"]),
                                   "creativity": set(["question", "answer"]),
                                   "grounding": set(["answer", "context"])}
    actual_input_cols = set()
    for item in chat_history:
        actual_input_cols.update(set(item["inputs"].keys()))
        actual_input_cols.update(set(item["outputs"].keys()))
        break

    data_validation = selected_metrics
    for metric in selected_metrics:
        if selected_metrics[metric]:
            metric_required_fields = dict_metric_required_fields[metric]
            if metric_required_fields <= actual_input_cols:
                data_validation[metric] = True
            else:
                print("this path")
                data_validation[metric] = False
    return data_validation
