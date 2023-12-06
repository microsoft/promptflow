import os
import unittest
import promptflow
from base_test import BaseTest
from promptflow._sdk._errors import InvalidRunStatusError


class TestChatWithPDF(BaseTest):
    def setUp(self):
        super().setUp()
        self.pf = promptflow.PFClient()

    def tearDown(self) -> None:
        return super().tearDown()

    def test_run_chat_with_pdf(self):
        result = self.pf.test(
            flow=self.flow_path,
            inputs={
                "chat_history": [],
                "pdf_url": "https://arxiv.org/pdf/1810.04805.pdf",
                "question": "BERT stands for?",
                "config": self.config_2k_context,
            },
        )
        print(result)
        self.assertTrue(
            result["answer"].find(
                "Bidirectional Encoder Representations from Transformers"
            )
            != -1
        )

    def test_bulk_run_chat_with_pdf(self):
        run = self.create_chat_run()
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
        run = self.create_chat_run(
            column_mapping={
                "question": "${data.question}",
                "pdf_url": "${data.pdf_url}",
                "chat_history": "${data.chat_history}",
                "config": self.config_2k_context,
            }
        )
        self.pf.stream(run)  # wait for completion

        self.assertEqual(run.status, "Completed")
        details = self.pf.get_details(run)
        self.assertEqual(details.shape[0], 3)

    def test_bulk_run_mapping_missing_one_column(self):
        data_path = os.path.join(
            self.flow_path, "data/invalid-data-missing-column.jsonl"
        )
        with self.assertRaises(InvalidRunStatusError):
            self.create_chat_run(
                column_mapping={
                    "question": "${data.question}",
                },
                data=data_path
            )

    def test_bulk_run_invalid_mapping(self):
        with self.assertRaises(InvalidRunStatusError):
            self.create_chat_run(
                column_mapping={
                    "question": "${data.question_not_exist}",
                    "pdf_url": "${data.pdf_url}",
                    "chat_history": "${data.chat_history}",
                }
            )


if __name__ == "__main__":
    unittest.main()
