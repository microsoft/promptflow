import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable, TypedDict

import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities import AzureOpenAIConnection
from promptflow.client import load_flow
from promptflow.exceptions import UserErrorException

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/flows"
EAGER_FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/eager_flows"
FLOW_RESULT_KEYS = ["category", "evidence"]
PROMPTY_DIR = (TEST_ROOT / "test_configs/prompty").resolve().absolute().as_posix()

_client = PFClient()


def clear_module_cache(module_name):
    try:
        del sys.modules[module_name]
    except Exception:
        pass


class GlobalHello:
    def __init__(self, connection: AzureOpenAIConnection):
        self.connection = connection

    def __call__(self, text: str) -> str:
        return f"Hello {text} via {self.connection.name}!"


class GlobalHelloWithInvalidInit:
    def __init__(self, connection: AzureOpenAIConnection, words: GlobalHello):
        self.connection = connection

    def __call__(self, text: str) -> str:
        return f"Hello {text} via {self.connection.name}!"


def global_hello(text: str) -> str:
    return f"Hello {text}!"


def global_hello_no_hint(text) -> str:
    return f"Hello {text}!"


def global_hello_typed_dict(text: str) -> TypedDict("TypedOutput", {"text": str}):
    return {"text": text}


class TypedOutput(TypedDict):
    text: str


def global_hello_inherited_typed_dict(text: str) -> TypedOutput:
    return TypedOutput(text=text)


def global_hello_int_return(text: str) -> int:
    return len(text)


def global_hello_strong_return(text: str) -> GlobalHello:
    return GlobalHello(AzureOpenAIConnection("test"))


def global_hello_kwargs(text: str, **kwargs) -> str:
    return f"Hello {text}!"


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
                    "python_requirements_txt": f"{TEST_ROOT}/test_configs/functions/requirements",
                    "image": "python:3.8-slim",
                    "signature": {
                        "inputs": {
                            "text": {
                                "type": "string",
                                "description": "The text to be printed",
                            }
                        },
                    },
                    "sample": {"inputs": {"text": "promptflow"}},
                },
                {
                    "inputs": {
                        "text": {
                            "type": "string",
                            "description": "The text to be printed",
                        }
                    },
                    "environment": {
                        "image": "python:3.8-slim",
                        "python_requirements_txt": "requirements",
                    },
                    "sample": {"inputs": {"text": "promptflow"}},
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
                        },
                        "s": {
                            "type": "string",
                        },
                        "i": {
                            "type": "int",
                        },
                        "f": {
                            "type": "double",
                        },
                        "b": {
                            "type": "bool",
                        },
                        "li": {
                            "type": "list",
                        },
                        "d": {
                            "type": "object",
                        },
                    },
                    "inputs": {
                        "s": {
                            "type": "string",
                        },
                        "i": {
                            "type": "int",
                        },
                        "f": {
                            "type": "double",
                        },
                        "b": {
                            "type": "bool",
                        },
                        "li": {
                            "type": "list",
                        },
                        "d": {
                            "type": "object",
                        },
                    },
                    "outputs": {
                        "s": {
                            "type": "string",
                        },
                        "i": {
                            "type": "int",
                        },
                        "f": {
                            "type": "double",
                        },
                        "b": {
                            "type": "bool",
                        },
                        "l": {
                            "type": "list",
                        },
                        "d": {
                            "type": "object",
                        },
                    },
                },
                id="class_init_complicated_ports",
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

        flow = load_flow(target_path)
        data = flow._data
        data.pop("entry", None)
        assert flow._data == expected_signature

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
                r"Ports from signature: non-exist",
                id="hello_world.inputs_mismatch",
            ),
            pytest.param(
                {
                    "entry": "hello:hello_world",
                    "sample": {"inputs": {"non-exist": "promptflow"}},
                },
                UserErrorException,
                r"Sample keys non-exist do not match the inputs text.",
                id="hello_world.sample_mismatch",
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
                r"Provided signature for outputs, which can't be overridden according to the entry.",
                id="hello_world.outputs_mismatch",
            ),
            pytest.param(
                {
                    "entry": "hello:Hello",
                },
                UserErrorException,
                r"The input 'words' is of a complex python type. Please use a dict instead",
                id="class_init_with_entity_init",
            ),
            pytest.param(
                {
                    "entry": "hello:Hello",
                },
                UserErrorException,
                r"The input 'text' is of a complex python type. Please use a dict instead",
                id="class_init_with_entity_inputs",
            ),
            pytest.param(
                {
                    "entry": "hello:Hello",
                },
                UserErrorException,
                r"The return annotation of the entry function must be",
                id="class_init_with_entity_outputs",
            ),
            pytest.param(
                {
                    "entry": "hello:Hello",
                },
                UserErrorException,
                r"The output 'entity' is of a complex python type. Please use a dict instead",
                id="class_init_with_dataclass_entity_fields",
            ),
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

    def test_pf_save_callable_class(self):
        pf = PFClient()
        target_path = f"{FLOWS_DIR}/saved/hello_callable"
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
        pf.flows._save(
            entry=GlobalHello,
            path=target_path,
        )

        flow = load_flow(target_path)
        assert flow._data == {
            "entry": "test_flow_save:GlobalHello",
            "init": {
                "connection": {
                    "type": "AzureOpenAIConnection",
                }
            },
            "inputs": {
                "text": {
                    "type": "string",
                }
            },
        }

    def test_pf_infer_signature_include_primitive_output(self):
        pf = PFClient()
        flow_meta = pf.flows._infer_signature(entry=global_hello, include_primitive_output=True)
        assert flow_meta == {
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
        }

    def test_pf_save_callable_function(self):
        pf = PFClient()
        target_path = f"{FLOWS_DIR}/saved/hello_callable"
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
        pf.flows._save(
            entry=global_hello,
            path=target_path,
        )

        flow = load_flow(target_path)
        assert flow._data == {
            "entry": "test_flow_save:global_hello",
            "inputs": {
                "text": {
                    "type": "string",
                }
            },
        }

    @pytest.mark.parametrize(
        "target_function, expected_signature",
        [
            pytest.param(
                global_hello,
                {
                    "inputs": {
                        "text": {
                            "type": "string",
                        }
                    },
                },
                id="simple",
            ),
            pytest.param(
                global_hello_typed_dict,
                {
                    "inputs": {
                        "text": {
                            "type": "string",
                        }
                    },
                    "outputs": {
                        "text": {
                            "type": "string",
                        },
                    },
                },
                id="typed_dict_output",
            ),
            pytest.param(
                global_hello_inherited_typed_dict,
                {
                    "inputs": {
                        "text": {
                            "type": "string",
                        }
                    },
                    "outputs": {
                        "text": {
                            "type": "string",
                        },
                    },
                },
                id="inherited_typed_dict_output",
            ),
            pytest.param(
                global_hello_no_hint,
                {
                    "inputs": {
                        "text": {
                            # port without type hint will be treated as a dict
                            "type": "object",
                        }
                    },
                },
                id="inherited_typed_dict_output",
            ),
            pytest.param(
                global_hello_kwargs,
                {
                    "inputs": {
                        "text": {
                            "type": "string",
                        }
                    },
                },
                id="kwargs",
            ),
        ],
    )
    def test_infer_signature(
        self, target_function: Callable, expected_signature: TypedDict("Signature", {"inputs": dict, "outputs": dict})
    ):
        pf = PFClient()
        flow_meta = pf.flows.infer_signature(entry=target_function)
        assert flow_meta == expected_signature

    def test_infer_signature_failed(self):
        pf = PFClient()
        with pytest.raises(UserErrorException, match="The input 'words' is of a complex python type"):
            pf.flows.infer_signature(entry=GlobalHelloWithInvalidInit)

        with pytest.raises(UserErrorException, match="Parse interface for 'global_hello_strong_return' failed"):
            pf.flows.infer_signature(entry=global_hello_strong_return)

        with pytest.raises(UserErrorException, match="Parse interface for 'global_hello_int_return' failed"):
            pf.flows.infer_signature(entry=global_hello_int_return)

    def test_public_save(self):
        pf = PFClient()
        with tempfile.TemporaryDirectory() as tempdir:
            pf.flows.save(entry=global_hello, path=tempdir)
            assert load_flow(tempdir)._data == {
                "entry": "test_flow_save:global_hello",
                "inputs": {
                    "text": {
                        "type": "string",
                    }
                },
            }

    def test_public_save_with_path_sample(self):
        pf = PFClient()
        with tempfile.TemporaryDirectory() as tempdir:
            with open(f"{tempdir}/sample.json", "w") as f:
                json.dump(
                    {
                        "inputs": {
                            "text": "promptflow",
                        }
                    },
                    f,
                )
            pf.flows.save(entry=global_hello, path=f"{tempdir}/flow", sample=f"{tempdir}/sample.json")
            assert load_flow(f"{tempdir}/flow")._data == {
                "entry": "test_flow_save:global_hello",
                "inputs": {
                    "text": {
                        "type": "string",
                    }
                },
                "sample": {
                    "inputs": {
                        "text": "promptflow",
                    }
                },
            }

    def test_flow_save_file_code(self):
        pf = PFClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            pf.flows.save(
                entry="hello_world",
                code=f"{TEST_ROOT}/test_configs/functions/file_code/hello.py",
                path=temp_dir,
            )
            flow = load_flow(temp_dir)
            assert flow._data == {
                "entry": "hello:hello_world",
                "inputs": {
                    "text": {
                        "type": "string",
                    }
                },
            }
            assert set(os.listdir(temp_dir)) == {"flow.flex.yaml", "hello.py"}

    def test_flow_infer_signature(self):
        pf = PFClient()
        # Prompty
        prompty = load_flow(source=Path(PROMPTY_DIR) / "prompty_example.prompty")
        meta = pf.flows.infer_signature(entry=prompty, include_primitive_output=True)
        assert meta == {
            "inputs": {
                "firstName": {"type": "string", "default": "John"},
                "lastName": {"type": "string", "default": "Doh"},
                "question": {"type": "string"},
            },
            "outputs": {"output": {"type": "string"}},
            "init": {
                "configuration": {"type": "object"},
                "parameters": {"type": "object"},
                "api": {"type": "string", "default": "chat"},
                "response": {"type": "string", "default": "first"},
            },
        }

        meta = pf.flows.infer_signature(entry=prompty)
        assert meta == {
            "inputs": {
                "firstName": {"type": "string", "default": "John"},
                "lastName": {"type": "string", "default": "Doh"},
                "question": {"type": "string"},
            },
            "init": {
                "configuration": {"type": "object"},
                "parameters": {"type": "object"},
                "api": {"type": "string", "default": "chat"},
                "response": {"type": "string", "default": "first"},
            },
        }

        # sample as input signature
        prompty = load_flow(source=Path(PROMPTY_DIR) / "sample_as_input_signature.prompty")
        meta = pf.flows.infer_signature(entry=prompty, include_primitive_output=True)
        assert meta == {
            "inputs": {
                "firstName": {"type": "string"},
                "lastName": {"type": "string"},
                "question": {"type": "string"},
            },
            "outputs": {"output": {"type": "string"}},
            "init": {
                "configuration": {"type": "object"},
                "parameters": {"type": "object"},
                "api": {"type": "string", "default": "chat"},
                "response": {"type": "string", "default": "first"},
            },
        }

        # Flex flow
        flex_flow = load_flow(source=Path(EAGER_FLOWS_DIR) / "builtin_llm")
        meta = pf.flows.infer_signature(entry=flex_flow, include_primitive_output=True)
        assert meta == {
            "inputs": {
                "chat_history": {"default": "[]", "type": "list"},
                "question": {"default": "What is ChatGPT?", "type": "string"},
                "stream": {"default": "False", "type": "bool"},
            },
            "outputs": {"output": {"type": "string"}},
        }

        meta = pf.flows.infer_signature(entry=flex_flow)
        assert meta == {
            "inputs": {
                "chat_history": {"default": "[]", "type": "list"},
                "question": {"default": "What is ChatGPT?", "type": "string"},
                "stream": {"default": "False", "type": "bool"},
            },
        }

        with pytest.raises(UserErrorException) as ex:
            pf.flows.infer_signature(entry="invalid_entry")
        assert "only support callable object or prompty" in ex.value.message

        # Test update flex flow
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(Path(temp_dir) / "flow.flex.yaml", "w") as f:
                f.write("entry: entry:my_flow")

            with open(Path(temp_dir) / "entry.py", "w") as f:
                f.write(
                    """
def my_flow(input_val: str = "gpt") -> str:
    pass
"""
                )
            flex_flow = load_flow(source=temp_dir)
            meta = pf.flows.infer_signature(entry=flex_flow, include_primitive_output=True)
            assert meta == {
                "inputs": {"input_val": {"default": "gpt", "type": "string"}},
                "outputs": {"output": {"type": "string"}},
            }
            # Update flex flow
            with open(Path(temp_dir) / "entry.py", "w") as f:
                f.write(
                    """
def my_flow(input_val: str, new_input_val: str) -> str:
    pass
"""
                )
            meta = pf.flows.infer_signature(entry=flex_flow, include_primitive_output=True)
            assert meta == {
                "inputs": {"input_val": {"type": "string"}, "new_input_val": {"type": "string"}},
                "outputs": {"output": {"type": "string"}},
            }
