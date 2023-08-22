import unittest
import promptflow.azure as azure
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from base_test import BaseTest
import time
import os


class TestChatWithPDFAzure(BaseTest):
    def setUp(self):
        super().setUp()
        self.data_path = os.path.join(self.flow_path, "data/bert-paper-qna-3-line.jsonl")

        try:
            credential = DefaultAzureCredential()
            # Check if given credential can get token successfully.
            credential.get_token("https://management.azure.com/.default")
        except Exception:
            # Fall back to InteractiveBrowserCredential in case DefaultAzureCredential not work
            credential = InteractiveBrowserCredential()

        self.pf = azure.PFClient.from_config(credential=credential)
        self.runtime = "chat_with_pdf_runtime"
        # self.runtime = None  # serverless

    def tearDown(self) -> None:
        return super().tearDown()

    def test_bulk_run_chat_with_pdf(self):
        run = self.create_chat_run(runtime=self.runtime)
        self.pf.stream(run)  # wait for completion

        self.assertEqual(run.status, "Completed")
        details = self.pf.get_details(run)
        self.assertEqual(details.shape[0], 3)

    def test_eval(self):
        display_name = "chat_with_pdf_2k_context"
        run2k = self.create_chat_run(
            column_mapping={
                "question": "${data.question}",
                "pdf_url": "${data.pdf_url}",
                "chat_history": "${data.chat_history}",
                "config": self.config_2k_context,
            },
            runtime=self.runtime,
            display_name=display_name,
        )
        self.pf.stream(run2k)  # wait for completion
        self.check_run_basics(run2k, display_name)

        display_name = "eval_groundedness_2k_context"
        eval2k_groundedness = self.create_eval_run(
            self.eval_groundedness_flow_path,
            run2k,
            {
                "question": "${run.inputs.question}",
                "answer": "${run.outputs.answer}",
                "context": "${run.outputs.context}",
            },
            runtime=self.runtime,
            display_name=display_name,
        )
        self.pf.stream(eval2k_groundedness)  # wait for completion
        self.check_run_basics(eval2k_groundedness, display_name)

        details = self.pf.get_details(eval2k_groundedness)
        self.assertGreater(details.shape[0], 2)

        metrics, elapsed = self.wait_for_metrics(eval2k_groundedness)
        self.assertGreaterEqual(metrics["groundedness"], 0.0)
        self.assertLessEqual(elapsed, 5)  # metrics should be available within 5 seconds

        display_name = "eval_perceived_intelligence_2k_context"
        eval2k_pi = self.create_eval_run(
            self.eval_perceived_intelligence_flow_path,
            run2k,
            {
                "question": "${run.inputs.question}",
                "answer": "${run.outputs.answer}",
                "context": "${run.outputs.context}",
            },
            runtime=self.runtime,
            display_name=display_name,
        )
        self.pf.stream(eval2k_pi)  # wait for completion
        self.check_run_basics(eval2k_pi, display_name)

        details = self.pf.get_details(eval2k_pi)
        self.assertGreater(details.shape[0], 2)

        metrics, elapsed = self.wait_for_metrics(eval2k_pi)
        self.assertGreaterEqual(metrics["perceived_intelligence_score"], 0.0)
        self.assertLessEqual(elapsed, 5)  # metrics should be available within 5 seconds

    def test_bulk_run_valid_mapping(self):
        data = os.path.join(self.flow_path, "data/bert-paper-qna-1-line.jsonl")
        run = self.create_chat_run(
            data=data,
            column_mapping={
                "question": "${data.question}",
                "pdf_url": "${data.pdf_url}",
                "chat_history": "${data.chat_history}",
                "config": self.config_2k_context,
            },
            runtime=self.runtime,
        )
        self.pf.stream(run)  # wait for completion

        self.assertEqual(run.status, "Completed")
        details = self.pf.get_details(run)
        self.assertEqual(details.shape[0], 1)

    def test_bulk_run_mapping_missing_one_column(self):
        run = self.create_chat_run(
            column_mapping={
                "question": "${data.question}",
                "pdf_url": "${data.pdf_url}",
            },
            runtime=self.runtime,
        )
        self.pf.stream(run)  # wait for completion

        self.assertEqual(run.status, "Failed")
        with self.assertRaises(Exception):
            _ = self.pf.get_details(run)

    def test_bulk_run_invalid_mapping(self):
        run = self.create_chat_run(
            column_mapping={
                "question": "${data.question_not_exist}",
                "pdf_url": "${data.pdf_url}",
                "chat_history": "${data.chat_history}",
            },
            runtime=self.runtime,
        )

        self.pf.stream(run)  # wait for completion

        self.assertEqual(run.status, "Failed")
        with self.assertRaises(Exception):
            _ = self.pf.get_details(run)

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


if __name__ == "__main__":
    unittest.main()
