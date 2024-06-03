# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

from promptflow.parallel._config.parser import parse


def test_parse_correct_type():
    args = [
        "--amlbi_pf_model",
        "/test_model",
        "--amlbi_pf_connections",
        "con1=v1,con2=v2",
        "--amlbi_pf_deployment_names",
        "dep1=v1,dep2=v2",
        "--amlbi_pf_model_names",
        "mod1=v1,mod2=v2",
        "--output_uri_file",
        "/test_output",
        "--amlbi_pf_run_outputs",
        "/test_side_input",
        "--amlbi_pf_debug_info",
        "/test_debug",
        "--logging_level",
        "INFO",
        "--pf_input_arg1",
        "arg1",
        "--pf_input_arg2",
        "arg2",
        "--input_asset_input1",
        "/test_input1",
        "--input_asset_input2",
        "/test_input2",
    ]
    config = parse(args)

    assert config.pf_model_dir == Path("/test_model")
    assert config.input_dir == Path("/test_input1")
    assert config.output_dir == Path("/test_output")
    assert config.input_mapping == {"arg1": "arg1", "arg2": "arg2"}
    assert config.side_input_dir == Path("/test_side_input")
    assert config.connections_override == {
        "con1": "v1",
        "con2": "v2",
        "dep1": "v1",
        "dep2": "v2",
        "mod1": "v1",
        "mod2": "v2",
    }
    assert config.debug_output_dir == Path("/test_debug")
    assert config.logging_level == "INFO"
    assert not config.is_debug_enabled
