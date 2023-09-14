import pytest
import json
from promptflow.contracts._run_management import VisualizationRender
from promptflow._sdk._constants import VIS_LIB_CDN_LINK_TMPL


@pytest.mark.unittest
def test_visualization_render():
    data = {"key": "value"}
    version = "1.0"

    viz = VisualizationRender(data, version)

    assert viz.data == json.dumps(json.dumps(data))
    assert viz.js_link == VIS_LIB_CDN_LINK_TMPL.format(version=version)
