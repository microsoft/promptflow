import os
import uuid
from dataclasses import asdict
from pathlib import Path

import pytest

import promptflow as pf
from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow.connections import AzureOpenAIConnection
from promptflow.sdk._constants import RunStatus
from promptflow.sdk._load_functions import load_flow
from promptflow.sdk._run_functions import create_yaml_run
from promptflow.sdk.entities import AzureOpenAIConnection as AzureOpenAIConnectionEntity
from promptflow.sdk.entities._flow import Flow
from promptflow.sdk.exceptions import InvalidRunStatusError
from promptflow.sdk.operations._run_submitter import RunSubmitter

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
MODEL_ROOT = TEST_ROOT / "test_configs/e2e_samples"
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = "./tests/test_configs/flows"


@pytest.fixture()
def local_aoai_connection(local_client, azure_open_ai_connection: AzureOpenAIConnection):
    conn = AzureOpenAIConnectionEntity(
        name="azure_open_ai_connection",
        api_key=azure_open_ai_connection.api_key,
        api_base=azure_open_ai_connection.api_base,
    )
    local_client.connections.create_or_update(conn)
    return conn


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection")
@pytest.mark.community_control_plane_sdk_test
@pytest.mark.e2etest
class TestFlowRun:
    def test_basic_flow_bulk_run(self, azure_open_ai_connection: AzureOpenAIConnection) -> None:
        data_path = f"{FLOWS_DIR}/webClassification3.jsonl"
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }

        pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path, connections=connections)
        pf.run(flow=f"{FLOWS_DIR}/web_classification_v1", data=data_path, connections=connections)
        pf.run(flow=f"{FLOWS_DIR}/web_classification_v2", data=data_path, connections=connections)

        # TODO: check details
        # df = pf.show_details(baseline, v1, v2)

    def test_basic_run_bulk(self, azure_open_ai_connection: AzureOpenAIConnection, local_client):
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{FLOWS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            connections=connections,
        )
        details = local_client.runs._get_details(run=result)
        tuning_node = next((x for x in details["node_runs"] if x["node"] == "summarize_text_content"), None)
        # used default variant config
        assert tuning_node["inputs"]["temperature"] == 0.3

        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"

    def test_basic_flow_with_variant(self, azure_open_ai_connection: AzureOpenAIConnection, local_client) -> None:
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }

        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{FLOWS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            connections=connections,
        )
        details = local_client.runs._get_details(run=result)
        tuning_node = next((x for x in details["node_runs"] if x["node"] == "summarize_text_content"), None)
        # used variant_0 config
        assert tuning_node["inputs"]["temperature"] == 0.2
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{FLOWS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_1}",
            connections=connections,
        )
        details = local_client.runs._get_details(run=result)
        tuning_node = next((x for x in details["node_runs"] if x["node"] == "summarize_text_content"), None)
        # used variant_1 config
        assert tuning_node["inputs"]["temperature"] == 0.3

    def test_run_bulk_error(self):

        # path not exist
        with pytest.raises(FileNotFoundError) as e:
            pf.run(
                flow=f"{MODEL_ROOT}/not_exist",
                data=f"{FLOWS_DIR}/webClassification3.jsonl",
                column_mapping={"question": "${data.question}", "context": "${data.context}"},
                variant="${summarize_text_content.variant_0}",
            )
        assert "not exist" in str(e.value)

        # tuning_node not exist
        with pytest.raises(ValueError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                data=f"{FLOWS_DIR}/webClassification3.jsonl",
                column_mapping={"question": "${data.question}", "context": "${data.context}"},
                variant="${not_exist.variant_0}",
            )
        assert "Node not_exist not found in flow" in str(e.value)

        # invalid variant format
        with pytest.raises(ValueError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                data=f"{FLOWS_DIR}/webClassification3.jsonl",
                column_mapping={"question": "${data.question}", "context": "${data.context}"},
                variant="v",
            )
        assert "Invalid variant format: v, variant should be in format of ${TUNING_NODE.VARIANT}" in str(e.value)

    def test_basic_evaluation(self, azure_open_ai_connection: AzureOpenAIConnection, local_client):
        data_path = f"{FLOWS_DIR}/webClassification3.jsonl"
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }

        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
            connections=connections,
        )
        assert local_client.runs.get(result.name).status == "Completed"

        eval_result = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            data=data_path,
            run=result.name,
            column_mapping={
                "groundtruth": "${data.answer}",
                "prediction": "${run.outputs.category}",
                # evaluation reference run.inputs
                "url": "${run.inputs.url}",
            },
        )
        assert local_client.runs.get(eval_result.name).status == "Completed"

    def test_basic_flow_run(self, azure_open_ai_connection: AzureOpenAIConnection) -> None:
        data_path = f"{FLOWS_DIR}/webClassification3.jsonl"
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }

        flow = load_flow(f"{FLOWS_DIR}/web_classification")
        flow1 = load_flow(f"{FLOWS_DIR}/web_classification_v1")
        flow2 = load_flow(f"{FLOWS_DIR}/web_classification_v2")

        flow.run(data_path, connections=connections)
        flow1.run(data_path, connections=connections)
        flow2.run(data_path, connections=connections)
        # we do not dump BulkFlowRun to db any more, so cannot show details on these for now.

    def test_flow_demo(self, azure_open_ai_connection):
        data_path = f"{FLOWS_DIR}/webClassification3.jsonl"
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }

        column_mapping = {"groundtruth": "data.answer", "prediction": "variants.output.category"}

        metrics = {}
        for flow_name, output_key in [
            ("web_classification", "baseline"),
            ("web_classification_v1", "v1"),
            ("web_classification_v2", "v2"),
        ]:
            v = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path, connections=connections)

            metrics[output_key] = pf.run(
                flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
                data=data_path,
                run=v,
                column_mapping=column_mapping,
                connections=connections,
            )

        # TODO: compare metrics

    def test_submit_run_from_yaml(self, local_client):
        run_id = str(uuid.uuid4())
        run = create_yaml_run(source=f"{FLOWS_DIR}/runs/sample_bulk_run.yaml", params_override=[{"name": run_id}])

        assert local_client.runs.get(run.name).status == "Completed"

        eval_run = create_yaml_run(
            source=f"{FLOWS_DIR}/runs/sample_eval_run.yaml",
            params_override=[{"run": run_id}],
        )
        assert local_client.runs.get(eval_run.name).status == "Completed"

    def test_run_with_connection(self, local_client, local_aoai_connection):

        # remove connection file to test connection resolving
        os.environ.pop(PROMPTFLOW_CONNECTIONS)
        result = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{FLOWS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
        )
        details = local_client.runs._get_details(run=result)
        tuning_node = next((x for x in details["node_runs"] if x["node"] == "summarize_text_content"), None)
        # used default variant config
        assert tuning_node["inputs"]["temperature"] == 0.3

        run = local_client.runs.get(name=result.name)
        assert run.status == "Completed"

    def test_resolve_connection(self, local_client, local_aoai_connection):
        flow = Flow.load(f"{FLOWS_DIR}/web_classification_no_variants")
        submitter = RunSubmitter(local_client.runs)
        connections = submitter._resolve_connections(flow)
        assert local_aoai_connection.name in connections

    def test_run_with_env_overwrite(self, local_client, local_aoai_connection):
        run = create_yaml_run(
            source=f"{FLOWS_DIR}/runs/run_with_env.yaml",
        )
        outputs = local_client.runs.get_outputs(run=run)
        assert "openai.azure.com" in outputs["output"][0]

    def test_flow_single_node_run(self, azure_open_ai_connection) -> None:
        connections = {
            "azure_open_ai_connection": {
                "type": "AzureOpenAIConnection",
                "module": "promptflow.connections",
                "value": asdict(azure_open_ai_connection),
            },
        }

        node_name = "fetch_text_content_from_url"
        data_path = f"{FLOWS_DIR}/fetch_text_content_from_url_input.jsonl"
        flow = load_flow(source=f"{FLOWS_DIR}/web_classification")
        result = flow._single_node_run(node=node_name, input=data_path, connections=connections)
        assert len(result.detail["node_runs"]) == 1
        node_run = result.detail["node_runs"][0]
        assert node_run["node"] == node_name
        assert node_run["status"] == "Completed"

    def test_flow_single_node_debug(self, azure_open_ai_connection) -> None:
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }

        data_path = f"{FLOWS_DIR}/fetch_text_content_from_url_input.jsonl"
        flow = load_flow(f"{FLOWS_DIR}/web_classification")
        flow._single_node_debug(node_name="fetch_text_content_from_url", input=data_path, connections=connections)

    def test_run_dump(self, azure_open_ai_connection: AzureOpenAIConnection) -> None:
        data_path = f"{FLOWS_DIR}/webClassification3.jsonl"
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }
        run = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path, connections=connections)
        # in fact, `pf.run` will internally query the run from db in `RunSubmitter`
        # explicitly call ORM get here to emphasize the dump operatoin
        pf_client = pf.PFClient()
        pf_client.runs.get(run.name)

        # test list API here, so that we don't need to use @pytest.mark.last
        runs = pf_client.runs.list(max_results=1)
        assert len(runs) == 1

    def test_stream_run_summary(self, azure_open_ai_connection: AzureOpenAIConnection, local_client, capfd) -> None:
        data_path = f"{FLOWS_DIR}/webClassification3.jsonl"
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }
        run = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path, connections=connections)
        local_client.runs.stream(run.name)
        out, _ = capfd.readouterr()
        print(out)
        assert 'Run status: "Completed"' in out

    def test_stream_incomplete_run_summary(
        self, azure_open_ai_connection: AzureOpenAIConnection, local_client, capfd
    ) -> None:
        # use wrong data to create a failed run
        data_path = f"{FLOWS_DIR}/fetch_text_content_from_url_input.jsonl"
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }
        run = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path, connections=connections)
        local_client.runs.stream(run.name)
        out, _ = capfd.readouterr()
        print(out)
        assert 'Run status: "Failed"' in out
        assert "Error:" in out

    def test_run_data_not_provided(self):
        with pytest.raises(ValueError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
            )
        assert "at least one of data or run must be provided" in str(e)

    def test_visualize_run(self, azure_open_ai_connection: AzureOpenAIConnection) -> None:
        data_path = f"{FLOWS_DIR}/webClassification3.jsonl"
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }
        run1 = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
            connections=connections,
        )
        run2 = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            data=data_path,
            run=run1.name,
            column_mapping={
                "groundtruth": "${data.answer}",
                "prediction": "${run.outputs.category}",
                "url": "${run.inputs.url}",
            },
        )
        pf.visualize([run1, run2])

    def test_incomplete_run_visualize(self, azure_open_ai_connection: AzureOpenAIConnection) -> None:
        data_path = f"{FLOWS_DIR}/webClassification3.jsonl"
        connections = {
            "azure_open_ai_connection": azure_open_ai_connection,
        }
        run = pf.run(flow=f"{FLOWS_DIR}/web_classification", data=data_path, connections=connections)
        # modify status in memory
        run._status = RunStatus.FAILED
        with pytest.raises(InvalidRunStatusError):
            pf.visualize(run)
