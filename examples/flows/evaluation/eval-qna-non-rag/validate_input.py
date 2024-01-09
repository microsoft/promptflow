from promptflow import tool


@tool
def validate_input(question: str, answer: str, context: str, ground_truth: str, selected_metrics: dict) -> dict:
    input_data = {"question": question, "answer": answer, "context": context, "ground_truth": ground_truth}
    expected_input_cols = set(input_data.keys())
    dict_metric_required_fields = {"gpt_groundedness": set(["answer", "context"]),
                                   "gpt_relevance": set(["question", "answer", "context"]),
                                   "gpt_coherence": set(["question", "answer"]),
                                   "gpt_similarity": set(["question", "answer", "ground_truth"]),
                                   "gpt_fluency": set(["question", "answer"]),
                                   "f1_score": set(["answer", "ground_truth"]),
                                   "ada_similarity": set(["answer", "ground_truth"])}
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
    return data_validation
