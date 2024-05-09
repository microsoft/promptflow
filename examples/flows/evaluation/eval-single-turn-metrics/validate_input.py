from promptflow.core import tool


@tool
def validate_input(question: str, answer: str, context: str, ground_truth: str, selected_metrics: dict) -> dict:
    input_data = {"question": question, "answer": answer, "context": context, "ground_truth": ground_truth}
    expected_input_cols = set(input_data.keys())
    dict_metric_required_fields = {"answer_relevance": set(["question", "answer"]),
                                   "answer_quality": set(["question", "answer"]),
                                   "creativity": set(["question", "answer"]),
                                   "grounding": set(["answer", "context"]),
                                   "context_recall": set(["question", "context", "ground_truth"]),
                                   "context_precision": set(["question", "context", "ground_truth"]),
                                   "answer_similarity": set(["question", "answer", "ground_truth"]),
                                   "answer_correctness": set(["question", "answer", "ground_truth"])}
    actual_input_cols = set()
    for col in expected_input_cols:
        if input_data[col] and input_data[col].strip():
            actual_input_cols.add(col)
    data_validation = selected_metrics
    for metric in selected_metrics:
        if selected_metrics[metric]:
            metric_required_fields = dict_metric_required_fields[metric]
            if metric_required_fields <= actual_input_cols:
                data_validation[metric] = True
            else:
                data_validation[metric] = False

    if data_validation['answer_correctness']:
        data_validation['answer_similarity'] = True

    return data_validation
