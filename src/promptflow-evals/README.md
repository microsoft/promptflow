# Prompt flow evaluators

[![Python package](https://img.shields.io/pypi/v/promptflow-evals)](https://pypi.org/project/promptflow-evals/)
[![License: MIT](https://img.shields.io/github/license/microsoft/promptflow)](https://github.com/microsoft/promptflow/blob/main/LICENSE)

## Introduction
Evaluators are prebuilt promptflow pipelines that are designed to measure the quality of the outputs from large language models.
The package includes
 - F1 score evaluator.
   The F1 score evaluator computes the F1 score based on the actual and predicted answer. 
 - Chat evaluator. Chat evaluator is an ensemble of other evaluators. It accepts the list of dialog turns, which include questions, answers and contexts and apply the evaluators. It calculates coherence and fluency of answers and if all the data points have context, the RAG-based metrics are being calculated by groundness and relevance evaluators.
 - Coherence evaluator
   This evaluator calculates coherence of an answer, which is measured by how well all the sentences fit together and sound naturally as a whole.
 - Fluency evaluator.
   Fluency measures the quality of individual sentences in the answer, and whether they are well-written and grammatically correct. 
 - Groundness evaluator. The Groundness evaluator is being applied if the context is provided. It estimates the integer score between 1 and 5 measuring, how logically answer is following from context, where one is a false statement, and five is true statement.
 - QA evaluator is an ensemble of evaluator, which calculates groundness, relevance, coherence, fluency, similarity and F1 score of question and answer.
 - Relevance evaluator. Relevance measures how well the answer addresses the main aspects of the question, based on the context. This evaluator also return integer value from 1 to 5 where 1 means that the answer completely lacks the relevance and 5 means that the relevance is perfect.
 - Similarity evaluator measures similarity between the predicted answer and the correct answer using nubers from 1 to 5, where one means no similarity and five absolute similarity.
 - Content safety evaluators score the answer received from model based on presence of inappropriate contents. Evaluators package includes three content safety evaluators.
   * Self harm evaluator
   * Hate/unfairness evaluator
   * Sexual evaluator
