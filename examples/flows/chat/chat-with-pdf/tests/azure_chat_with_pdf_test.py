import unittest
import promptflow.azure as azure
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from base_test import BaseTest
import os
from promptflow._sdk._errors import InvalidRunStatusError


class TestChatWithPDFAzure(BaseTest):
    def setUp(self):
        super().setUp()
        self.data_path = os.path.join(
            self.flow_path, "data/bert-paper-qna-3-line.jsonl"
        )

        try:
            credential = DefaultAzureCredential()
            # Check if given credential can get token successfully.
            credential.get_token("https://management.azure.com/.default")
        except Exception:
            # Fall back to InteractiveBrowserCredential in case DefaultAzureCredential not work
            credential = InteractiveBrowserCredential()

        self.pf = azure.PFClient.from_config(credential=credential)

    def tearDown(self) -> None:
        return super().tearDown()

    def test_bulk_run_chat_with_pdf(self):
        run = self.create_chat_run(display_name="chat_with_pdf_batch_run")
        self.pf.stream(run)  # wait for completion

        self.assertEqual(run.status, "Completed")
        details = self.pf.get_details(run)
        self.assertEqual(details.shape[0], 3)

    def test_eval(self):
        run_2k, eval_groundedness_2k, eval_pi_2k = self.run_eval_with_config(
            self.config_2k_context,
            display_name="chat_with_pdf_2k_context",
        )
        run_3k, eval_groundedness_3k, eval_pi_3k = self.run_eval_with_config(
            self.config_3k_context,
            display_name="chat_with_pdf_3k_context",
        )

        self.check_run_basics(run_2k)
        self.check_run_basics(run_3k)
        self.check_run_basics(eval_groundedness_2k)
        self.check_run_basics(eval_pi_2k)
        self.check_run_basics(eval_groundedness_3k)
        self.check_run_basics(eval_pi_3k)

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
        )
        self.pf.stream(run)  # wait for completion

        # run won't be failed, only line runs inside it will be failed.
        self.assertEqual(run.status, "Completed")
        # TODO: get line run results when supported.

    def test_bulk_run_invalid_mapping(self):
        run = self.create_chat_run(
            column_mapping={
                "question": "${data.question_not_exist}",
                "pdf_url": "${data.pdf_url}",
                "chat_history": "${data.chat_history}",
            },
            stream=False,
        )

        with self.assertRaises(InvalidRunStatusError):
            self.pf.stream(run)  # wait for completion


if __name__ == "__main__":
    unittest.main()
