from promptflow import log_metric


def pass_rate(aggregate_results):
    metrics = {}
    pass_count = 0
    for name, value in aggregate_results.items():
        if name == "score" and value > 3:
            pass_count += 1
    metrics["pass_rate"] = pass_count / len(aggregate_results)
    # metrics["metric2"] = ...
    for name, val in metrics.items():
        log_metric(name, val)
    return metrics
