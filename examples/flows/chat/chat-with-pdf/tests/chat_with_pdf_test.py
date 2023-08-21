import unittest
import promptflow
from base_test import BaseTest


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
        self.assertEqual(details.shape[0], 1)

    def test_eval(self):
        run = self.create_chat_run()
        self.pf.stream(run)  # wait for completion
        self.assertEqual(run.status, "Completed")

        eval = self.create_eval_run(
            self.eval_groundedness_flow_path,
            run,
            {
                "question": "${run.inputs.question}",
                "answer": "${run.outputs.answer}",
                "context": "${run.outputs.context}",
            },
        )
        self.pf.stream(eval)  # wait for completion
        self.assertEqual(eval.status, "Completed")

        details = self.pf.get_details(eval)
        self.assertEqual(details.shape[0], 1)

        metrics = self.pf.get_metrics(eval)
        self.assertGreaterEqual(metrics["groundedness"], 0.0)

        eval = self.create_eval_run(
            self.eval_perceived_intelligence_flow_path,
            run,
            {
                "question": "${run.inputs.question}",
                "answer": "${run.outputs.answer}",
                "context": "${run.outputs.context}",
            },
        )
        self.pf.stream(eval)  # wait for completion
        self.assertEqual(eval.status, "Completed")

        details = self.pf.get_details(eval)
        self.assertEqual(details.shape[0], 1)

        metrics = self.pf.get_metrics(eval)
        self.assertGreaterEqual(metrics["perceived_intelligence_score"], 0.0)

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
        self.assertEqual(details.shape[0], 1)

    def test_bulk_run_mapping_missing_one_column(self):
        run = self.create_chat_run(
            column_mapping={
                "question": "${data.question}",
                "pdf_url": "${data.pdf_url}",
            }
        )
        self.pf.stream(run)  # wait for completion

        self.assertEqual(run.status, "Failed")
        with self.assertRaises(Exception):
            print(self.pf.get_details(run))

    def test_bulk_run_invalid_mapping(self):
        run = self.create_chat_run(
            column_mapping={
                "question": "${data.question_not_exist}",
                "pdf_url": "${data.pdf_url}",
                "chat_history": "${data.chat_history}",
            }
        )
        self.pf.stream(run)  # wait for completion

        self.assertEqual(run.status, "Failed")
        with self.assertRaises(Exception):
            print(self.pf.get_details(run))


if __name__ == "__main__":
    unittest.main()
