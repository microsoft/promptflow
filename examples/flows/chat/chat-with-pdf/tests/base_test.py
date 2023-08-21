import unittest
import os
import json
import traceback


class BaseTest(unittest.TestCase):
    def setUp(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../")
        self.flow_path = os.path.join(root, "chat-with-pdf")
        self.data_path = os.path.join(
            self.flow_path, "data/bert-paper-qna-1-line.jsonl"
        )
        self.eval_groundedness_flow_path = os.path.join(root, "../evaluation/groundedness-eval")
        self.eval_perceived_intelligence_flow_path = os.path.join(
            root, "../evaluation/perceived-intelligence-eval"
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
        # TODO remove this when object passing is supported
        self.config_3k_context = json.dumps(self.config_3k_context)
        self.config_2k_context = json.dumps(self.config_2k_context)

        # Switch current working directory to the folder of this file
        self.cwd = os.getcwd()
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

    def tearDown(self):
        # Switch back to the original working directory
        os.chdir(self.cwd)

        for run in self.all_runs_generated:
            try:
                self.pf.runs.archive(run.name)
            except Exception as e:
                print(e)
                traceback.print_exc()

    def create_chat_run(self, data=None, column_mapping=None, connections=None, runtime=None, display_name='chat_run'):
        if column_mapping is None:
            column_mapping = {
                "chat_history": "${data.chat_history}",
                "pdf_url": "${data.pdf_url}",
                "question": "${data.question}",
                "config": self.config_2k_context,
            }
        data = self.data_path if data is None else data

        run = self.pf.run(
            flow=self.flow_path,
            data=data,
            column_mapping=column_mapping,
            connections=connections,
            runtime=runtime,
            display_name=display_name,
            tags={"unittest": "true"},
            stream=True,
        )
        self.all_runs_generated.append(run)
        self.check_run_basics(run, display_name)
        return run

    def create_eval_run(
        self, eval_flow_path, base_run, column_mapping, connections=None, runtime=None, display_name=None
    ):
        eval = self.pf.run(
            flow=eval_flow_path,
            run=base_run,
            column_mapping=column_mapping,
            connections=connections,
            runtime=runtime,
            display_name=display_name,
            tags={"unittest": "true"},
            stream=True,
        )
        self.all_runs_generated.append(eval)
        self.check_run_basics(eval, display_name)
        return eval

    def check_run_basics(self, run, display_name):
        self.assertTrue(run is not None)
        self.assertEqual(run.display_name, display_name)
        self.assertEqual(run.tags["unittest"], "true")
