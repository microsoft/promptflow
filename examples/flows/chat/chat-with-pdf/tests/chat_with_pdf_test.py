import unittest
import promptflow
from base_test import BaseTest
from promptflow.executor._errors import InputNotFoundInInputsMapping


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

        display_name = 'groundedness_eval'
        eval_run = self.create_eval_run(
            self.eval_groundedness_flow_path,
            run,
            {
                "question": "${run.inputs.question}",
                "answer": "${run.outputs.answer}",
                "context": "${run.outputs.context}",
            },
            display_name=display_name,
        )
        self.pf.stream(eval_run)  # wait for completion
        self.assertEqual(eval_run.status, "Completed")

        details = self.pf.get_details(eval_run)
        self.assertEqual(details.shape[0], 1)

        metrics = self.pf.get_metrics(eval_run)
        self.assertGreaterEqual(metrics["groundedness"], 0.0)

        eval_run = self.create_eval_run(
            self.eval_perceived_intelligence_flow_path,
            run,
            {
                "question": "${run.inputs.question}",
                "answer": "${run.outputs.answer}",
                "context": "${run.outputs.context}",
            },
            display_name=display_name,
        )
        self.pf.stream(eval_run)  # wait for completion
        self.assertEqual(eval_run.status, "Completed")

        details = self.pf.get_details(eval_run)
        self.assertEqual(details.shape[0], 1)

        metrics = self.pf.get_metrics(eval_run)
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
        # in this case, run won't be created.
        with self.assertRaises(InputNotFoundInInputsMapping):
            self.create_chat_run(
                column_mapping={
                    "question": "${data.question}",
                    "pdf_url": "${data.pdf_url}",
                }
            )

    def test_bulk_run_invalid_mapping(self):
        # in this case, run won't be created.
        with self.assertRaises(InputNotFoundInInputsMapping):
            self.create_chat_run(
                column_mapping={
                    "question": "${data.question_not_exist}",
                    "pdf_url": "${data.pdf_url}",
                    "chat_history": "${data.chat_history}",
                }
            )


if __name__ == "__main__":
    unittest.main()
