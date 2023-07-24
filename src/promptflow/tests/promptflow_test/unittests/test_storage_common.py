import pytest

from promptflow.storage.common import reconstruct_metrics_dict


@pytest.mark.unittest
def test_reconstruct_metrics_dict():
    input_metrics = {
        "accuracy": [
            {"value": 0.9, "variant_id": "variant0"},
            {"value": 0.8, "variant_id": "variant1"},
            {"value": 0.7},
        ]
    }

    ground_truth_metrics = {
        'accuracy.variant0': 0.9,
        'accuracy.variant1': 0.8,
    }

    assert reconstruct_metrics_dict(input_metrics) == ground_truth_metrics
