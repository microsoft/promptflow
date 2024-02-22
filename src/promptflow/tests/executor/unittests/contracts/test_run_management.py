import json

import pytest

from promptflow.contracts._run_management import VisualizationRender


@pytest.mark.unittest
def test_visualization_render():
    data = {"key": "value"}

    viz = VisualizationRender(data)

    assert viz.data == json.dumps(json.dumps(data))
