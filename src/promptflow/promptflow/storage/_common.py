# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


def reconstruct_metrics_dict(metrics: dict) -> dict:
    """
    Input metrics example: {
        "accuracy": [
            {"value": 0.9, "variant_id": "variant0"},
            {"value": 0.9, "variant_id": "variant1"},
            {"value": 0.9}
        ]
    }

    Output metrics example: {
        "accurcacy": 0.9,
        "accuracy.variant0": 0.9,
        "accuracy.variant1": 0.9
    }
    """

    METRIC_VALUE_KEY = "value"
    VARIANT_ID_KEY = "variant_id"

    new_metrics = dict()
    for original_metric_name, value_list in metrics.items():
        for value_dict in value_list:
            # if variant id exists, set metric name to "<metric_name>.<variant_id>"
            metric_name = original_metric_name
            if VARIANT_ID_KEY in value_dict:
                metric_name = f"{metric_name}.{value_dict[VARIANT_ID_KEY]}"
            value = value_dict[METRIC_VALUE_KEY]
            new_metrics.update({metric_name: value})

    return new_metrics
