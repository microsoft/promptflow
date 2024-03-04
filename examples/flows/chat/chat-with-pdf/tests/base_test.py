import unittest
import os
import time
import traceback


class BaseTest(unittest.TestCase):
    def setUp(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../")
        self.flow_path = os.path.join(root, "chat-with-pdf")
        self.data_path = os.path.join(
            self.flow_path, "data/bert-paper-qna-3-line.jsonl"
        )
        self.eval_groundedness_flow_path = os.path.join(
            root, "../evaluation/eval-groundedness"
        )
        self.eval_perceived_intelligence_flow_path = os.path.join(
            root, "../evaluation/eval-perceived-intelligence"
        )
        self.all_runs_generated = []
        self.config_3k_context = {
            "EMBEDDING_MODEL_DEPLOYMENT_NAME": "text-embedding-ada-002",
            "CHAT_MODEL_DEPLOYMENT_NAME": "gpt-35-turbo",
            "PROMPT_TOKEN_LIMIT": 3000,
            "MAX_COMPLETION_TOKENS": 256,
            "VERBOSE": True,
            "CHUNK_SIZE": 1024,
            "CHUNK_OVERLAP": 64,
        }
        self.config_2k_context = {
            "EMBEDDING_MODEL_DEPLOYMENT_NAME": "text-embedding-ada-002",
            "CHAT_MODEL_DEPLOYMENT_NAME": "gpt-35-turbo",
            "PROMPT_TOKEN_LIMIT": 2000,
            "MAX_COMPLETION_TOKENS": 256,
            "VERBOSE": True,
            "CHUNK_SIZE": 1024,
            "CHUNK_OVERLAP": 64,
        }

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

    def create_chat_run(
        self,
        data=None,
        column_mapping=None,
        connections=None,
        display_name="chat_run",
        stream=True,
    ):
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
            display_name=display_name,
            tags={"unittest": "true"},
            stream=stream,
        )
        self.all_runs_generated.append(run)
        self.check_run_basics(run, display_name)
        return run

    def create_eval_run(
        self,
        eval_flow_path,
        base_run,
        column_mapping,
        connections=None,
        display_name_postfix="",
    ):
        display_name = eval_flow_path.split("/")[-1] + display_name_postfix
        eval = self.pf.run(
            flow=eval_flow_path,
            run=base_run,
            column_mapping=column_mapping,
            connections=connections,
            display_name=display_name,
            tags={"unittest": "true"},
            stream=True,
        )
        self.all_runs_generated.append(eval)
        self.check_run_basics(eval, display_name)
        return eval

    def check_run_basics(self, run, display_name=None):
        self.assertTrue(run is not None)
        if display_name is not None:
            self.assertTrue(run.display_name.find(display_name) != -1)
        self.assertEqual(run.tags["unittest"], "true")

    def run_eval_with_config(self, config: dict, display_name: str = None):
        run = self.create_chat_run(
            column_mapping={
                "question": "${data.question}",
                "pdf_url": "${data.pdf_url}",
                "chat_history": "${data.chat_history}",
                "config": config,
            },
            display_name=display_name,
        )
        self.pf.stream(run)  # wait for completion
        self.check_run_basics(run)

        eval_groundedness = self.create_eval_run(
            self.eval_groundedness_flow_path,
            run,
            {
                "question": "${run.inputs.question}",
                "answer": "${run.outputs.answer}",
                "context": "${run.outputs.context}",
            },
            display_name_postfix="_" + display_name,
        )
        self.pf.stream(eval_groundedness)  # wait for completion
        self.check_run_basics(eval_groundedness)

        details = self.pf.get_details(eval_groundedness)
        self.assertGreater(details.shape[0], 2)

        metrics, elapsed = self.wait_for_metrics(eval_groundedness)
        self.assertGreaterEqual(metrics["groundedness"], 0.0)
        self.assertLessEqual(elapsed, 5)  # metrics should be available within 5 seconds

        eval_pi = self.create_eval_run(
            self.eval_perceived_intelligence_flow_path,
            run,
            {
                "question": "${run.inputs.question}",
                "answer": "${run.outputs.answer}",
                "context": "${run.outputs.context}",
            },
            display_name_postfix="_" + display_name,
        )
        self.pf.stream(eval_pi)  # wait for completion
        self.check_run_basics(eval_pi)

        details = self.pf.get_details(eval_pi)
        self.assertGreater(details.shape[0], 2)

        metrics, elapsed = self.wait_for_metrics(eval_pi)
        self.assertGreaterEqual(metrics["perceived_intelligence_score"], 0.0)
        self.assertLessEqual(elapsed, 5)  # metrics should be available within 5 seconds

        return run, eval_groundedness, eval_pi

    def wait_for_metrics(self, run):
        start = time.time()
        metrics = self.pf.get_metrics(run)
        cnt = 3
        while len(metrics) == 0 and cnt > 0:
            time.sleep(5)
            metrics = self.pf.get_metrics(run)
            cnt -= 1

        end = time.time()
        return metrics, end - start
