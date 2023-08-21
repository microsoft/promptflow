import unittest
import os
import traceback


class BaseTest(unittest.TestCase):
    def setUp(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../")
        self.flow_path = os.path.join(root, "chat_with_pdf")
        self.data_path = os.path.join(
            self.flow_path, "data/bert-paper-qna-1-line.jsonl"
        )
        self.eval_groundedness_flow_path = os.path.join(root, "eval_groundedness")
        self.eval_perceived_intelligence_flow_path = os.path.join(
            root, "eval_perceived_intelligence"
        )
        self.all_runs_generated = []
        self.config_3k_context = {
            "EMBEDDING_MODEL_DEPLOYMENT_NAME": "text-embedding-ada-002",
            "CHAT_MODEL_DEPLOYMENT_NAME": "gpt-35-turbo",
            "PROMPT_TOKEN_LIMIT": 3000,
            "MAX_COMPLETION_TOKENS": 256,
            "VERBOSE": True,
            "CHUNK_SIZE": 256,
            "CHUNK_OVERLAP": 32,
        }
        self.config_2k_context = {
            "EMBEDDING_MODEL_DEPLOYMENT_NAME": "text-embedding-ada-002",
            "CHAT_MODEL_DEPLOYMENT_NAME": "gpt-35-turbo",
            "PROMPT_TOKEN_LIMIT": 2000,
            "MAX_COMPLETION_TOKENS": 256,
            "VERBOSE": True,
            "CHUNK_SIZE": 256,
            "CHUNK_OVERLAP": 32,
        }

        # Switch current working directory to the folder of this file
        self.cwd = os.getcwd()
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        # Delete tools.json
        try:
            os.remove(os.path.join(self.flow_path, ".promptflow/flow.tools.json"))
        except Exception:
            pass

    def tearDown(self):
        # Switch back to the original working directory
        os.chdir(self.cwd)

        for run in self.all_runs_generated:
            try:
                self.pf.runs.archive(run.name)
            except Exception as e:
                print(e)
                traceback.print_exc()

    def create_chat_run(self, column_mapping=None, connections=None, runtime=None):
        if column_mapping is None:
            column_mapping = {
                "chat_history": "${data.chat_history}",
                "pdf_url": "${data.pdf_url}",
                "question": "${data.question}",
                "config": self.config_2k_context,
            }
        run = self.pf.run(
            flow=self.flow_path,
            data=self.data_path,
            column_mapping=column_mapping,
            connections=connections,
            runtime=runtime,
            display_name="test_bulk_run_chat_with_pdf",
            tags={"unittest": "true"},
            stream=True,
        )
        self.all_runs_generated.append(run)
        self.check_run_basics(run, "test_bulk_run_chat_with_pdf")
        return run

    def create_eval_run(
        self, eval_flow_path, base_run, column_mapping, connections=None, runtime=None
    ):
        run_display_name = eval_flow_path.split("/")[-1]
        eval = self.pf.run(
            flow=eval_flow_path,
            run=base_run,
            column_mapping=column_mapping,
            connections=connections,
            runtime=runtime,
            display_name=run_display_name,
            tags={"unittest": "true"},
            stream=True,
        )
        self.all_runs_generated.append(eval)
        self.check_run_basics(eval, run_display_name)
        return eval

    def check_run_basics(self, run, name):
        self.assertTrue(run is not None)
        self.assertEqual(run.display_name, name)
        self.assertEqual(run.tags["unittest"], "true")
