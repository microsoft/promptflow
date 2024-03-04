from promptflow import tool


def is_valid(input_item):
    return True if input_item and input_item.strip() else False


@tool
def validate_input(question: str, answer: str, documents: str, selected_metrics: dict) -> dict:
    input_data = {"question": is_valid(question), "answer": is_valid(answer), "documents": is_valid(documents)}
    expected_input_cols = set(input_data.keys())
    dict_metric_required_fields = {"gpt_groundedness": set(["question", "answer", "documents"]),
                                   "gpt_relevance": set(["question", "answer", "documents"]),
                                   "gpt_retrieval_score": set(["question", "documents"])}
    actual_input_cols = set()
    for col in expected_input_cols:
        if input_data[col]:
            actual_input_cols.add(col)
    data_validation = selected_metrics
    for metric in selected_metrics:
        if selected_metrics[metric]:
            metric_required_fields = dict_metric_required_fields[metric]
            if metric_required_fields <= actual_input_cols:
                data_validation[metric] = True
            else:
                data_validation[metric] = False
    return data_validation
