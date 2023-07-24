import json

import pytest
from runtime_test.conftest import PROMOTFLOW_ROOT

from promptflow.contracts.runtime import MetaV2Request


@pytest.mark.unittest
def test_deserialize_meta_v2_payload():

    file_path = (
        (PROMOTFLOW_ROOT / "tests/test_configs/meta_v2_samples/meta_v2_endpoint_payload.json").resolve().absolute()
    )
    assert file_path.exists()
    content = json.loads(file_path.read_text())
    result = MetaV2Request.deserialize(content)
    assert len(result.tools) == 4
    assert result.flow_source_info.working_dir == "test_working_dir"
    assert result.flow_source_info.sas_url == "test_sas_url"
