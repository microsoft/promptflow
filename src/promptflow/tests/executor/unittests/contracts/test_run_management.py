import json

import pytest

from promptflow._sdk._constants import VIS_JS_BUNDLE_FILENAME
from promptflow.contracts._run_management import VisualizationRender


@pytest.mark.unittest
def test_visualization_render():
    data = {"key": "value"}

    viz = VisualizationRender(data)

    assert viz.data == json.dumps(json.dumps(data))
    assert viz.js_path == VIS_JS_BUNDLE_FILENAME
