import unittest
import traceback
import os
import promptflow.azure as azure
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from azure.ai.ml import MLClient
import promptflow


class BaseTest(unittest.TestCase):
    def setUp(self) -> None:
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../")
        self.flow_path = os.path.join(root, "named_entity_recognition")
        self.data_path = os.path.join(self.flow_path, "test_data.jsonl")
        self.eval_match_rate_flow_path = os.path.join(root, "eval_entity_match_rate")
        self.all_runs_generated = []

        return super().setUp()

    def tearDown(self):
        for run in self.all_runs_generated:
            try:
                self.pf.runs.archive(run.name)
            except Exception as e:
                print(e)
                traceback.print_exc()

        return super().setUp()

    def check_run_basics(self, run, name):
        self.assertTrue(run is not None)
        self.assertEqual(run.display_name, name)
        self.assertEqual(run.tags["unittest"], "true")


class TestEvalAzure(BaseTest):
    def setUp(self) -> None:
        try:
            credential = DefaultAzureCredential()
            # Check if given credential can get token successfully.
            credential.get_token("https://management.azure.com/.default")
        except Exception:
            # Fall back to InteractiveBrowserCredential in case DefaultAzureCredential not work
            credential = InteractiveBrowserCredential()

        ml_client = MLClient.from_config(
            credential=credential,
        )

        self.pf = azure.PFClient(ml_client)
        return super().setUp()

    def test_bulk_run_and_eval(self):
        run = self.pf.run(
            flow=self.flow_path,
            data=self.data_path,
            column_mapping={
                "text": "${data.text}",
                "entity_type": "${data.entity_type}"
            },
            connections={"NER_LLM": {"connection": "azure_open_ai_connection"}},
            runtime="chat_with_pdf_runtime",
            display_name="ner_bulk_run",
            tags={"unittest": "true"},
            stream=True)
        self.all_runs_generated.append(run)
        self.check_run_basics(run, "ner_bulk_run")

        eval = self.pf.run(
            flow=self.eval_match_rate_flow_path,
            run=run,
            data=self.data_path,
            column_mapping={
                "entities": "${run.outputs.entities}",
                "ground_truth": "${data.results}"
            },
            runtime="chat_with_pdf_runtime",
            display_name="eval_match_rate",
            tags={"unittest": "true"},
            stream=True)
        self.all_runs_generated.append(eval)
        self.check_run_basics(eval, "eval_match_rate")

        return eval


class TestEval(BaseTest):
    def setUp(self) -> None:
        self.pf = promptflow.PFClient()
        return super().setUp()

    def test_bulk_run_and_eval(self):
        run = self.pf.run(
            flow=self.flow_path,
            data=self.data_path,
            column_mapping={
                "text": "${data.text}",
                "entity_type": "${data.entity_type}"
            },
            display_name="ner_bulk_run",
            tags={"unittest": "true"},
            stream=True)
        self.all_runs_generated.append(run)
        self.check_run_basics(run, "ner_bulk_run")

        eval = self.pf.run(
            flow=self.eval_match_rate_flow_path,
            run=run,
            data=self.data_path,
            column_mapping={
                "entities": "${run.outputs.entities}",
                "ground_truth": "${data.results}"
            },
            display_name="eval_match_rate",
            tags={"unittest": "true"},
            stream=True)
        self.all_runs_generated.append(eval)
        self.check_run_basics(eval, "eval_match_rate")

        return eval
