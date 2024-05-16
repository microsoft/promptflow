from pathlib import Path

import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._sdk._utilities.serve_utils import _resolve_python_flow_additional_includes


@pytest.mark.unittest
def test_flow_serve_resolve_additional_includes():
    # Assert flow path not changed if no additional includes
    flow_path = (PROMPTFLOW_ROOT / "tests/test_configs/flows/web_classification").resolve().absolute()
    resolved_flow_path = _resolve_python_flow_additional_includes(flow_path / "flow.dag.yaml", flow_path)
    assert flow_path == resolved_flow_path

    # Assert additional includes are resolved correctly
    flow_path = (
        (PROMPTFLOW_ROOT / "tests/test_configs/flows/web_classification_with_additional_include").resolve().absolute()
    )
    resolved_flow_path = _resolve_python_flow_additional_includes(flow_path / "flow.dag.yaml", flow_path)

    assert (Path(resolved_flow_path) / "convert_to_dict.py").exists()
    assert (Path(resolved_flow_path) / "fetch_text_content_from_url.py").exists()
    assert (Path(resolved_flow_path) / "summarize_text_content.jinja2").exists()
