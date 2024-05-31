import json
import os
import tempfile
import time
import uuid
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import sleep

import pytest
from _constants import PROMPTFLOW_ROOT
from mock import mock
from ruamel.yaml import YAML

from promptflow._sdk._constants import PF_TRACE_CONTEXT, ExperimentStatus, RunStatus, RunTypes
from promptflow._sdk._errors import ExperimentValueError, RunOperationError
from promptflow._sdk._load_functions import _load_experiment, load_common
from promptflow._sdk._orchestrator.experiment_orchestrator import ExperimentOrchestrator, ExperimentTemplateTestContext
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities._experiment import CommandNode, Experiment, ExperimentTemplate, FlowNode

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
EXP_ROOT = TEST_ROOT / "test_configs/experiments"
FLOW_ROOT = TEST_ROOT / "test_configs/flows"
EAGER_FLOW_ROOT = TEST_ROOT / "test_configs/eager_flows"


yaml = YAML(typ="safe")


@pytest.mark.e2etest
@pytest.mark.usefixtures("setup_experiment_table")
class TestExperiment:
    def wait_for_experiment_terminated(self, client, experiment):
        while experiment.status in [ExperimentStatus.IN_PROGRESS, ExperimentStatus.QUEUING]:
            experiment = client._experiments.get(experiment.name)
            sleep(10)
        return experiment

    def test_experiment_from_template_with_script_node(self):
        template_path = EXP_ROOT / "basic-script-template" / "basic-script.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        # Assert command node load correctly
        assert len(experiment.nodes) == 4
        expected = dict(yaml.load(open(template_path, "r", encoding="utf-8").read()))
        experiment_dict = experiment._to_dict()
        assert isinstance(experiment.nodes[0], CommandNode)
        assert isinstance(experiment.nodes[1], FlowNode)
        assert isinstance(experiment.nodes[2], FlowNode)
        assert isinstance(experiment.nodes[3], CommandNode)
        gen_data_snapshot_path = experiment._output_dir / "snapshots" / "gen_data"
        echo_snapshot_path = experiment._output_dir / "snapshots" / "echo"
        expected["nodes"][0]["code"] = gen_data_snapshot_path.absolute().as_posix()
        expected["nodes"][3]["code"] = echo_snapshot_path.absolute().as_posix()
        expected["nodes"][3]["environment_variables"] = {}
        expected["nodes"][3]["outputs"]["output_path"] = Path(template_path).parent.absolute().as_posix()
        assert experiment_dict["nodes"][0].items() == expected["nodes"][0].items()
        assert experiment_dict["nodes"][3].items() == expected["nodes"][3].items()
        # Assert snapshots
        assert gen_data_snapshot_path.exists()
        file_count = len(list(gen_data_snapshot_path.rglob("*")))
        assert file_count == 1
        assert (gen_data_snapshot_path / "generate_data.py").exists()
        # Assert no file exists in echo path
        assert echo_snapshot_path.exists()
        file_count = len(list(echo_snapshot_path.rglob("*")))
        assert file_count == 0

    def test_experiment_create_and_get(self):
        template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        client = PFClient()
        exp = client._experiments.create_or_update(experiment)
        assert len(client._experiments.list()) > 0
        exp_get = client._experiments.get(name=exp.name)
        assert exp_get._to_dict() == exp._to_dict()

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_start(self):
        template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        client = PFClient()
        exp = client._experiments.create_or_update(experiment)
        session = str(uuid.uuid4())
        if pytest.is_live:
            # Async start
            exp = client._experiments.start(exp, session=session)
            # Test the experiment in progress cannot be started.
            with pytest.raises(RunOperationError) as e:
                client._experiments.start(exp)
            assert f"Experiment {exp.name} is {exp.status}" in str(e.value)
            assert exp.status in [ExperimentStatus.IN_PROGRESS, ExperimentStatus.QUEUING]
            exp = self.wait_for_experiment_terminated(client, exp)
        else:
            exp = client._experiments.get(exp.name)
            exp = ExperimentOrchestrator(client, exp).start(session=session)
        # Assert record log in experiment folder
        assert (Path(exp._output_dir) / "logs" / "exp.attempt_0.log").exists()

        # Assert main run
        assert len(exp.node_runs["main"]) > 0
        main_run = client.runs.get(name=exp.node_runs["main"][0]["name"])
        assert main_run.status == RunStatus.COMPLETED
        assert main_run.variant == "${summarize_text_content.variant_0}"
        assert main_run.display_name == "main"
        assert len(exp.node_runs["eval"]) > 0
        # Assert eval run and metrics
        eval_run = client.runs.get(name=exp.node_runs["eval"][0]["name"])
        assert eval_run.status == RunStatus.COMPLETED
        assert eval_run.display_name == "eval"
        metrics = client.runs.get_metrics(name=eval_run.name)
        assert "accuracy" in metrics
        # Assert Trace
        line_runs = client.traces.list_line_runs(collection=session)
        if len(line_runs) > 0:
            assert len(line_runs) == 3
            line_run = line_runs[0]
            assert len(line_run.evaluations) == 1, "line run evaluation not exists!"
            assert "eval_classification_accuracy" == list(line_run.evaluations.values())[0].display_name

        # Test experiment restart
        exp = client._experiments.start(exp)
        exp = self.wait_for_experiment_terminated(client, exp)
        for name, runs in exp.node_runs.items():
            assert all(run["status"] == RunStatus.COMPLETED for run in runs)
        assert (Path(exp._output_dir) / "logs" / "exp.attempt_1.log").exists()

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_with_script_start(self):
        template_path = EXP_ROOT / "basic-script-template" / "basic-script.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        client = PFClient()
        exp = client._experiments.create_or_update(experiment)
        if pytest.is_live:
            # Async start
            exp = client._experiments.start(exp)
            exp = self.wait_for_experiment_terminated(client, exp)
        else:
            exp = client._experiments.get(exp.name)
            exp = ExperimentOrchestrator(client, exp).start()
        assert exp.status == ExperimentStatus.TERMINATED
        assert len(exp.node_runs) == 4
        for key, val in exp.node_runs.items():
            assert val[0]["status"] == RunStatus.COMPLETED, f"Node {key} run failed"
        run = client.runs.get(name=exp.node_runs["echo"][0]["name"])
        assert run.type == RunTypes.COMMAND

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_start_with_prompty(self):
        template_path = EXP_ROOT / "experiment-with-prompty-template" / "basic-script.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        client = PFClient()
        exp = client._experiments.create_or_update(experiment)
        session = str(uuid.uuid4())
        if pytest.is_live:
            # Async start
            exp = client._experiments.start(exp, session=session)
            # Test the experiment in progress cannot be started.
            with pytest.raises(RunOperationError) as e:
                client._experiments.start(exp)
            assert f"Experiment {exp.name} is {exp.status}" in str(e.value)
            assert exp.status in [ExperimentStatus.IN_PROGRESS, ExperimentStatus.QUEUING]
            exp = self.wait_for_experiment_terminated(client, exp)
        else:
            exp = client._experiments.get(exp.name)
            exp = ExperimentOrchestrator(client, exp).start(session=session)
        # Assert record log in experiment folder
        assert (Path(exp._output_dir) / "logs" / "exp.attempt_0.log").exists()
        assert exp.status == ExperimentStatus.TERMINATED
        assert len(exp.node_runs) > 0
        for name, runs in exp.node_runs.items():
            assert all(run["status"] == RunStatus.COMPLETED for run in runs)

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Injection cannot passed to detach process.")
    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_start_from_nodes(self):
        template_path = EXP_ROOT / "basic-script-template" / "basic-script.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        client = PFClient()
        exp = client._experiments.create_or_update(experiment)
        exp = client._experiments.start(exp)
        exp = self.wait_for_experiment_terminated(client, exp)

        # Test start experiment from nodes
        exp = client._experiments.start(exp, from_nodes=["main"])
        exp = self.wait_for_experiment_terminated(client, exp)

        assert exp.status == ExperimentStatus.TERMINATED
        assert len(exp.node_runs) == 4
        for key, val in exp.node_runs.items():
            assert all(item["status"] == RunStatus.COMPLETED for item in val), f"Node {key} run failed"
        assert len(exp.node_runs["main"]) == 2
        assert len(exp.node_runs["eval"]) == 2
        assert len(exp.node_runs["echo"]) == 2

        # Test run nodes in experiment
        exp = client._experiments.start(exp, nodes=["main"])
        exp = self.wait_for_experiment_terminated(client, exp)

        assert exp.status == ExperimentStatus.TERMINATED
        assert len(exp.node_runs) == 4
        for key, val in exp.node_runs.items():
            assert all(item["status"] == RunStatus.COMPLETED for item in val), f"Node {key} run failed"
        assert len(exp.node_runs["main"]) == 3
        assert len(exp.node_runs["echo"]) == 2

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Injection cannot passed to detach process.")
    def test_cancel_experiment(self):
        template_path = EXP_ROOT / "command-node-exp-template" / "basic-command.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        client = PFClient()
        exp = client._experiments.create_or_update(experiment)
        exp = client._experiments.start(exp)
        assert exp.status in [ExperimentStatus.IN_PROGRESS, ExperimentStatus.QUEUING]
        sleep(10)
        client._experiments.stop(exp)
        exp = client._experiments.get(exp.name)
        assert exp.status == ExperimentStatus.TERMINATED

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_flow_test_with_experiment(self, monkeypatch):
        # set queue size to 1 to make collection faster
        monkeypatch.setenv("OTEL_BSP_MAX_EXPORT_BATCH_SIZE", "1")
        monkeypatch.setenv("OTEL_BSP_SCHEDULE_DELAY", "1")

        def _assert_result(result):
            assert "main" in result, "Node main not in result"
            assert "category" in result["main"], "Node main.category not in result"
            assert "evidence" in result["main"], "Node main.evidence not in result"
            assert "eval" in result, "Node eval not in result"
            assert "grade" in result["eval"], "Node eval.grade not in result"

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True

            template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
            target_flow_path = FLOW_ROOT / "web_classification" / "flow.dag.yaml"
            client = PFClient()
            session = str(uuid.uuid4())
            # Test with inputs, use separate thread to avoid OperationContext somehow cleared by other tests
            with ThreadPoolExecutor() as pool:
                task = pool.submit(
                    client.flows.test,
                    flow=target_flow_path,
                    experiment=template_path,
                    session=session,
                    inputs={"url": "https://www.youtube.com/watch?v=kYqRtjDBci8", "answer": "Channel"},
                    environment_variables={"PF_TEST_FLOW_TEST_WITH_EXPERIMENT": "1"},
                )
                futures.wait([task], return_when=futures.ALL_COMPLETED)
                result = task.result()
            assert result
            # Assert line run id is set by executor when running test
            assert PF_TRACE_CONTEXT in os.environ
            attributes = json.loads(os.environ[PF_TRACE_CONTEXT]).get("attributes")
            assert os.environ.get("PF_TEST_FLOW_TEST_WITH_EXPERIMENT") == "1"
            assert attributes.get("experiment") == template_path.resolve().absolute().as_posix()
            assert attributes.get("referenced.line_run_id", "").startswith("main")
            expected_output_path = (
                Path(tempfile.gettempdir()) / ".promptflow/sessions/default" / "basic-no-script-template"
            )
            assert expected_output_path.resolve().exists()
            # Assert eval metric exists
            assert (expected_output_path / "eval" / "flow.metrics.json").exists()
            # Assert session exists
            # TODO: Task 2942400, avoid sleep/if and assert traces
            time.sleep(10)  # TODO fix this
            line_runs = client.traces.list_line_runs(collection=session)
            if len(line_runs) > 0:
                assert len(line_runs) == 1
                line_run = line_runs[0]
                assert len(line_run.evaluations) == 1, "line run evaluation not exists!"
                assert "eval_classification_accuracy" == list(line_run.evaluations.values())[0].display_name
            # Test with default data and custom path
            expected_output_path = Path(tempfile.gettempdir()) / ".promptflow/my_custom"
            result = client.flows.test(target_flow_path, experiment=template_path, output_path=expected_output_path)
            _assert_result(result)
            assert expected_output_path.resolve().exists()
            # Assert eval metric exists
            assert (expected_output_path / "eval" / "flow.metrics.json").exists()

        monkeypatch.delenv("OTEL_BSP_MAX_EXPORT_BATCH_SIZE")
        monkeypatch.delenv("OTEL_BSP_SCHEDULE_DELAY")

    def test_flow_not_in_experiment(self):
        template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
        target_flow_path = FLOW_ROOT / "chat_flow" / "flow.dag.yaml"
        client = PFClient()
        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            with pytest.raises(ExperimentValueError) as error:
                client.flows.test(
                    target_flow_path,
                    experiment=template_path,
                )
            assert "not found in experiment" in str(error.value)

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_test(self):
        template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
        client = PFClient()
        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            result = client._experiments.test(
                experiment=template_path,
            )
            assert len(result) == 2

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_test_with_script_node(self):
        template_path = EXP_ROOT / "basic-script-template" / "basic-script.exp.yaml"
        client = PFClient()
        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            result = client._experiments.test(
                experiment=template_path,
                # Test only read 1 line
                inputs={"count": 1},  # To replace experiment.inputs
            )
            assert len(result) == 4
            assert "output_path" in result["gen_data"]
            assert "category" in result["main"]
            assert "grade" in result["eval"]
            assert "output_path" in result["echo"]
            # Assert reference resolved for command node
            assert "main.json" in open(Path(result["echo"]["output_path"]) / "output.txt", "r").read()

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_test_with_skip_node(self):
        template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
        client = PFClient()
        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            result = client._experiments._test_flow(
                experiment=template_path,
                context={
                    "node": FLOW_ROOT / "web_classification" / "flow.dag.yaml",
                    "outputs": {"category": "Channel", "evidence": "Both"},
                    "run_id": "123",
                },
            )
            assert len(result) == 1

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_eager_flow_test_with_experiment(self, monkeypatch):

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True

            template_path = EXP_ROOT / "eager-flow-exp-template" / "flow.exp.yaml"
            target_flow_path = EAGER_FLOW_ROOT / "flow_with_dataclass_output" / "flow.flex.yaml"
            client = PFClient()
            result = client.flows.test(target_flow_path, experiment=template_path)
            assert result == {
                "main": {"models": ["model"], "text": "text"},
                "main2": {"output": "Hello world! text"},
                "main3": {"output": "Hello world! Hello world! text"},
            }

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_with_script_run(self):
        experiment_path = EXP_ROOT / "basic-script-template" / "basic-script.exp.yaml"
        experiment = _load_experiment(experiment_path)
        client = PFClient()
        exp = client._experiments.start(experiment, stream=True, inputs={"count": 3})
        assert exp.status == ExperimentStatus.TERMINATED
        assert len(exp.node_runs) == 4
        for key, val in exp.node_runs.items():
            assert val[0]["status"] == RunStatus.COMPLETED, f"Node {key} run failed"

    @pytest.mark.skip("Enable when chat group node run is ready")
    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_with_chat_group(self, pf: PFClient):
        template_path = EXP_ROOT / "chat-group-node-exp-template" / "exp.yaml"
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        exp = pf._experiments.create_or_update(experiment)

        if pytest.is_live:
            # Async start
            exp = pf._experiments.start(exp)
            exp = self.wait_for_experiment_terminated(pf, exp)
        else:
            exp = pf._experiments.get(exp.name)
            exp = ExperimentOrchestrator(pf, exp).start()

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_test_chat_group_node(self, pf: PFClient):
        template_path = EXP_ROOT / "chat-group-node-exp-template" / "exp.yaml"
        template = load_common(ExperimentTemplate, source=template_path)
        orchestrator = ExperimentOrchestrator(pf)
        test_context = ExperimentTemplateTestContext(template=template)
        chat_group_node = template.nodes[0]
        assert chat_group_node.name == "multi_turn_chat"

        history = orchestrator._test_node(chat_group_node, test_context)
        assert len(history) == 4
        assert history[0][0] == history[2][0] == "assistant"
        assert history[1][0] == history[3][0] == "user"
