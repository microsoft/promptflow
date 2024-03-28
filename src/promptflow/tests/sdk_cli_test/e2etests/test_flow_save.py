import os
import sys
from pathlib import Path

import pytest

import promptflow
from promptflow._sdk._pf_client import PFClient

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
    def test_pf_save_simple(self):
        pf = PFClient()
        # or follow spec: import promptflow as pf? seems that we don't have such interface now.
        pf.save(
            # should we support save to a yaml file and do not copy code?
            path=f"{FLOWS_DIR}/saved/hello_world",
            # this should be entry instead of flow as we don't have a flow now in concept level before saving
            entry="hello:hello_world",
            # question: should the requirements be related to code?
            # or should we copy it based on current working directory?
            requirements=f"{TEST_ROOT}/test_configs/functions/requirements",
            image="python:3.8-slim",
            # all content in code will be copied
            code=f"{TEST_ROOT}/test_configs/functions/hello_world",
            # what if the signature doesn't match the code? should we do any validation?
            signature={
                "inputs": {
                    "text": {
                        "type": "str",
                        "description": "The text to be printed",
                    }
                },
                "outputs": {
                    "answer": {
                        "type": "str",
                        "description": "The answer",
                    }
                },
            },
            # this field looks a little unnecessary. If we want it for pf flow test, seems that we should use it to
            # set default values for flow inputs; if we want it for run create, we should create a jsonl.
            input_sample={"text": "promptflow"},
            # or we should infer it from entry?
            language="python",
            force=True,
        )

        _ = promptflow.load_flow(f"{FLOWS_DIR}/saved/hello_world")
        # will we support flow as function for flex flow?
        # TODO: invoke is also not supported for flex flow for now
        # assert hello.invoke(inputs={"text": "promptflow"}) == "Hello World promptflow!"

    def test_pf_save_class_constructor(self):
        pf = PFClient()
        # or follow spec: import promptflow as pf? seems that we don't have such interface now.
        pf.save(
            path=f"{FLOWS_DIR}/saved/hello_world",
            entry="hello:hello_world",
            code=f"{TEST_ROOT}/test_configs/functions/hello_world",
            signature={
                "inputs": {
                    "text": {
                        "type": "str",
                        "description": "The text to be printed",
                    }
                },
                "outputs": {
                    "answer": {
                        "type": "str",
                        "description": "The answer",
                    }
                },
                # what about use this instead of a separate init_signature?
                "init": {
                    "the_model": {
                        "type": "str",
                    }
                },
            },
            force=True,
        )

    def test_pf_load_metadata(self):
        # so, this metadata should be the same as content of current flow.json
        pass

    def test_pf_load_with_configuration(self):
        import promptflow as pf
        from promptflow.connections import AzureOpenAIConnection

        configuration = {
            "azure_open_ai_connection": AzureOpenAIConnection(
                api_base=os.environ["AZURE_OPENAI_API_BASE"],
                api_type="azure",
                api_version="2023-11-06-preview",
            ),
            "chat_model_deployment_name": "gpt-35-turbo-0125",
            "chat_model_temperature": 0.7,
            "identity_to_use": "compute",
        }

        # what is this configuration? seems that we don't have such interface now.
        _ = pf.load_flow("path_to_save_to", configuration=configuration)

    def test_pf_save_with_required_properties(self):
        """
        inputs:
            type: object
            properties:
                topic:
                    type: string
                    description: the topic of the joke to be generated
                language:
                    type: string
                    description: the language in which the joke should be told
                    default: English
            requiredProperties: [topic]
        """
        # what is this requiredProperties?
        # TODO: according to the spec, we should support detailed schema for flow outputs?
        # https://github.com/Azure/azureml_run_specification/blob/users/anksing/evaluator_flow_asset/specs/simplified-sdk/evaluator/save_load_promptflow.md#inputsoutputs-signature-and-init_signature-details
        pass
