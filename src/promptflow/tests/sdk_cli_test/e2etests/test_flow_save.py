import os
import re
import shutil
import sys
from pathlib import Path

import pytest

from promptflow._sdk._pf_client import PFClient
from promptflow.exceptions import UserErrorException

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
MODEL_ROOT = TEST_ROOT / "test_configs/e2e_samples"
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = (TEST_ROOT / "test_configs/flows").resolve().absolute().as_posix()
EAGER_FLOWS_DIR = (TEST_ROOT / "test_configs/eager_flows").resolve().absolute().as_posix()
FLOW_RESULT_KEYS = ["category", "evidence"]

_client = PFClient()


def clear_module_cache(module_name):
    try:
        del sys.modules[module_name]
    except Exception:
        pass


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestFlowSave:
    @pytest.mark.parametrize(
        "save_args_overrides, expected_signature",
        [
            pytest.param(
                {
                    "entry": "hello:hello_world",
                    "python_requirements": f"{TEST_ROOT}/test_configs/functions/requirements",
                    "image": "python:3.8-slim",
                    "signature": {
                        "inputs": {
                            "text": {
                                "type": "string",
                                "description": "The text to be printed",
                            }
                        },
                        "outputs": {
                            "output": {
                                "type": "string",
                                "description": "The answer",
                            }
                        },
                    },
                    "input_sample": {"text": "promptflow"},
                },
                {
                    "inputs": {
                        "text": {
                            "type": "string",
                            "description": "The text to be printed",
                        }
                    },
                    "outputs": {
                        "output": {
                            "type": "string",
                            "description": "The answer",
                        }
                    },
                },
                id="hello_world.main",
            ),
            pytest.param(
                {
                    "entry": "hello:hello_world",
                    "signature": {
                        "inputs": {
                            "text": {
                                "type": "string",
                                "description": "The text to be printed",
                            }
                        },
                    },
                },
                {
                    "inputs": {
                        "text": {
                            "type": "string",
                            "description": "The text to be printed",
                        }
                    },
                    "outputs": {
                        "output": {
                            "type": "string",
                        }
                    },
                },
                id="hello_world.partially_generate_signature",
            ),
            pytest.param(
                {
                    "entry": "hello:hello_world",
                },
                {
                    "inputs": {
                        "text": {
                            "type": "string",
                        }
                    },
                    "outputs": {
                        "output": {
                            "type": "string",
                        }
                    },
                },
                id="hello_world.generate_signature",
            ),
            pytest.param(
                {
                    "entry": "hello:hello_world",
                },
                {
                    "inputs": {
                        "text": {
                            "type": "string",
                        }
                    },
                    "outputs": {
                        "response": {
                            "type": "string",
                        },
                        "length": {
                            "type": "int",
                        },
                    },
                },
                id="data_class_output",
            ),
            pytest.param(
                {
                    "entry": "hello:Hello",
                },
                {
                    "init": {
                        "background": {
                            "type": "string",
                            "default": "World",
                        }
                    },
                    "inputs": {
                        "text": {
                            "type": "string",
                        }
                    },
                    "outputs": {
                        "output": {
                            "type": "string",
                        },
                    },
                },
                id="class_init",
            ),
            pytest.param(
                {
                    "entry": "hello:Hello",
                },
                {
                    "init": {
                        "connection": {
                            "type": "AzureOpenAIConnection",
                        }
                    },
                    "inputs": {
                        "words": {
                            "type": "list",
                        }
                    },
                    "outputs": {
                        "output": {
                            "type": "object",
                        },
                    },
                },
                id="class_init_with_connection",
            ),
        ],
    )
    def test_pf_save_succeed(self, save_args_overrides, request, expected_signature: dict):
        target_path = f"{FLOWS_DIR}/saved/{request.node.callspec.id}"
        if os.path.exists(target_path):
            shutil.rmtree(target_path)

        target_code_dir = request.node.callspec.id
        target_code_dir = re.sub(r"\.[a-z_]+$", "", target_code_dir)
        save_args = {
            # should we support save to a yaml file and do not copy code?
            "path": target_path,
            # code should be required, or we can't locate entry along with code; we can check if it's possible to infer
            # code from entry
            # all content in code will be copied
            "code": f"{TEST_ROOT}/test_configs/functions/{target_code_dir}",
        }
        save_args.update(save_args_overrides)

        pf = PFClient()
        pf.flows._save(**save_args)

        from promptflow.client import load_flow

        flow = load_flow(target_path)
        for key, value in expected_signature.items():
            assert flow._data[key] == value, f"key: {key}, expected value: {value}, flow._data[key]: {flow._data[key]}"

        # will we support flow as function for flex flow?
        # TODO: invoke is also not supported for flex flow for now
        # assert hello.invoke(inputs={"text": "promptflow"}) == "Hello World promptflow!"

    @pytest.mark.parametrize(
        "save_args_overrides, expected_error_type, expected_error_regex",
        [
            pytest.param(
                {
                    "entry": "hello:hello_world",
                    "signature": {
                        "inputs": {
                            "non-exist": {
                                "type": "str",
                                "description": "The text to be printed",
                            }
                        },
                    },
                },
                UserErrorException,
                r"Ports with signature: non-exist",
                id="hello_world.inputs_mismatch",
            ),
            pytest.param(
                {
                    "entry": "hello:hello_world",
                    "signature": {
                        "outputs": {
                            "non-exist": {
                                "type": "str",
                                "description": "The text to be printed",
                            }
                        },
                    },
                },
                UserErrorException,
                r"Ports with signature: non-exist",
                id="hello_world.outputs_mismatch",
            ),
            pytest.param(
                {
                    "entry": "hello:Hello",
                },
                UserErrorException,
                r"Schema validation failed: {'init.words.type'",
                id="class_init_with_list_init",
            ),
            # TODO: check if ports are of dict type
            # pytest.param(
            #     {
            #         "entry": "hello:Hello",
            #     },
            #     UserErrorException,
            #     r"Schema validation failed: {'init.words.type'",
            #     id="class_init_with_entity_inputs",
            # ),
        ],
    )
    def test_pf_save_failed(self, save_args_overrides, request, expected_error_type, expected_error_regex: str):
        target_path = f"{FLOWS_DIR}/saved/{request.node.callspec.id}"
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
        target_code_dir = request.node.callspec.id
        target_code_dir = re.sub(r"\.[a-z_]+$", "", target_code_dir)
        save_args = {
            # should we support save to a yaml file and do not copy code?
            "path": target_path,
            # code should be required, or we can't locate entry along with code; we can check if it's possible to infer
            # code from entry
            # all content in code will be copied
            "code": f"{TEST_ROOT}/test_configs/functions/{target_code_dir}",
        }
        save_args.update(save_args_overrides)

        pf = PFClient()
        with pytest.raises(expected_error_type, match=expected_error_regex):
            pf.flows._save(**save_args)
