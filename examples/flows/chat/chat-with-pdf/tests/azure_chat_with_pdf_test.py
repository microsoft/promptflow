import unittest
import promptflow.azure as azure
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from azure.ai.ml import MLClient
from base_test import BaseTest
import time
import os


class TestChatWithPDFAzure(BaseTest):
    def setUp(self):
        super().setUp()
        self.data_path = os.path.join(self.flow_path, "test_data/bert-paper-qna.jsonl")

        try:
            credential = DefaultAzureCredential()
            # Check if given credential can get token successfully.
            credential.get_token("https://management.azure.com/.default")
        except Exception as ex:
            # Fall back to InteractiveBrowserCredential in case DefaultAzureCredential not work
            credential = InteractiveBrowserCredential()

        ml_client = MLClient(
            credential=credential,
            subscription_id="d128f140-94e6-4175-87a7-954b9d27db16",
            resource_group_name="jietong-test",
            workspace_name="jietong-test-4"
        )

        self.pf = azure.PFClient(ml_client)

    def tearDown(self) -> None:
        return super().tearDown()
    
    def test_bulk_run_chat_with_pdf(self):
        run = self.create_chat_run(
            runtime="chat_with_pdf_runtime")
        self.pf.stream(run) # wait for completion

        self.assertEqual(run.status, "Completed")
        details = self.pf.get_details(run)
        self.assertEqual(details.shape[0], 11)
    
    def test_eval(self):
        run2k = self.create_chat_run(
            column_mapping={
                "question": "${data.question}", 
                "pdf_url": "${data.pdf_url}", 
                "chat_history": "${data.chat_history}",
                "config": self.config_2k_context},
            runtime="chat_with_pdf_runtime",
            display_name="chat_with_pdf_2k_context")
        self.pf.stream(run2k) # wait for completion
        self.check_run_basics(run2k)

        eval2k_groundedness = self.create_eval_run(
            self.eval_groundedness_flow_path,
            run2k, 
            {
                "question": "${run.inputs.question}", 
                "answer": "${run.outputs.answer}",
                "context": "${run.outputs.context}"
            },
            runtime="chat_with_pdf_runtime",
            display_name="eval_groundedness_2k_context")
        self.pf.stream(eval) # wait for completion
        self.check_run_basics(eval2k_groundedness)

        details = self.pf.get_details(eval)
        self.assertGreater(details.shape[0], 5)

        metrics, elapsed = self.wait_for_metrics(eval)
        self.assertGreaterEqual(metrics["groundedness"], 0.0)
        self.assertLessEqual(elapsed, 5) # metrics should be available within 5 seconds

        eval2k_pi = self.create_eval_run(
            self.eval_perceived_intelligence_flow_path,
            run2k, 
            {
                "question": "${run.inputs.question}", 
                "answer": "${run.outputs.answer}",
                "context": "${run.outputs.context}"
            },
            runtime="chat_with_pdf_runtime",
            display_name="eval_perceived_intelligence_2k_context")
        self.pf.stream(eval2k_pi) # wait for completion
        self.check_run_basics(eval2k_pi)

        details = self.pf.get_details(eval)
        self.assertGreater(details.shape[0], 5)

        metrics, elapsed = self.wait_for_metrics(eval)
        self.assertGreaterEqual(metrics["perceived_intelligence_score"], 0.0)
        self.assertLessEqual(elapsed, 5) # metrics should be available within 60 seconds

    def test_bulk_run_valid_mapping(self):
        run = self.create_chat_run(
            column_mapping={
                "question": "${data.question}", 
                "pdf_url": "${data.pdf_url}", 
                "chat_history": "${data.chat_history}",
                "config": self.config_2k_context},
                runtime="chat_with_pdf_runtime")
        self.pf.stream(run) # wait for completion

        self.assertEqual(run.status, "Completed")
        details = self.pf.get_details(run)
        self.assertEqual(details.shape[0], 1)

    def test_bulk_run_mapping_missing_one_column(self):
        run = self.create_chat_run(
            column_mapping={
                "question": "${data.question}", 
                "pdf_url": "${data.pdf_url}"},
            runtime="chat_with_pdf_runtime")
        self.pf.stream(run) # wait for completion

        self.assertEqual(run.status, "Failed")
        with self.assertRaises(Exception):
            details = self.pf.get_details(run)

    def test_bulk_run_invalid_mapping(self):
        run = self.create_chat_run(
            column_mapping={
                "question": "${data.question_not_exist}", 
                "pdf_url": "${data.pdf_url}", 
                "chat_history": "${data.chat_history}"},
            connections={"setup_env": {"conn": "chat_with_pdf_custom_connection"}},
            runtime="chat_with_pdf_runtime")

        self.pf.stream(run) # wait for completion

        self.assertEqual(run.status, "Failed")
        with self.assertRaises(Exception):
            details = self.pf.get_details(run)

    def wait_for_metrics(self, run):
        start = time.time()
        metrics = self.pf.get_metrics(run)
        while len(metrics) == 0:
            time.sleep(5)
            metrics = self.pf.get_metrics(run)

        end = time.time()
        return metrics, end - start

if __name__ == '__main__':
    unittest.main()
