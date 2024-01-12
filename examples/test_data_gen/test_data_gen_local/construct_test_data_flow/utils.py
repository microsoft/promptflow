from __future__ import annotations

import typing as t
import warnings
from collections import defaultdict

try:
    from llama_index.schema import BaseNode
except ImportError:
    raise ImportError(
        "llama_index must be installed to use this function. " "Please, install it with `pip install llama_index`."
    )

import numpy as np
import numpy.testing as npt
from langchain.embeddings import OpenAIEmbeddings
from langchain.embeddings.base import Embeddings
from langchain.prompts import ChatPromptTemplate
from numpy.random import default_rng
from ragas.llms import llm_factory
from ragas.testset.prompts import (
    ANSWER_FORMULATE,
    COMPRESS_QUESTION,
    CONDITIONAL_QUESTION,
    CONTEXT_FORMULATE,
    CONVERSATION_QUESTION,
    FILTER_QUESTION,
    MULTICONTEXT_QUESTION,
    REASONING_QUESTION,
    SCORE_CONTEXT,
    SEED_QUESTION,
)
from ragas.testset.utils import load_as_json, load_as_score

if t.TYPE_CHECKING:
    from ragas.llms.base import RagasLLM


DEFAULT_TEST_DISTRIBUTION = {
    "simple": 0.4,
    "reasoning": 0.2,
    "multi_context": 0.2,
    "conditional": 0.2,
}


class TestsetGeneratorV2:

    """
    Ragas Test Set Generator

    Attributes
    ----------
    generator_llm: LangchainLLM
        LLM used for all the generator operations in the TestGeneration paradigm.
    critique_llm: LangchainLLM
        LLM used for all the filtering and scoring operations in TestGeneration
        paradigm.
    embeddings_model: Embeddings
        Embeddings used for vectorizing nodes when required.
    chat_qa: float
        Determines the fraction of conversational questions the resulting test set.
    chunk_size: int
        The chunk size of nodes created from data.
    test_distribution : dict
        Distribution of different types of questions to be generated from given
        set of documents. Defaults to {"easy":0.1, "reasoning":0.4, "conversation":0.5}
    """

    def __init__(
        self,
        generator_llm: RagasLLM,
        critic_llm: RagasLLM,
        embeddings_model: Embeddings,
        testset_distribution: t.Optional[t.Dict[str, float]] = None,
        chat_qa: float = 0.0,
        chunk_size: int = 1024,
        seed: int = 42,
    ) -> None:
        self.generator_llm = generator_llm
        self.critic_llm = critic_llm
        self.embedding_model = embeddings_model
        testset_distribution = testset_distribution or DEFAULT_TEST_DISTRIBUTION
        npt.assert_almost_equal(
            1,
            sum(testset_distribution.values()),
            err_msg="Sum of distribution should be 1",
        )

        prob = np.cumsum(list(testset_distribution.values()))
        types = testset_distribution.keys()
        self.testset_distribution = dict(zip(types, prob))

        self.chat_qa = chat_qa
        self.chunk_size = chunk_size
        self.threshold = 7.5
        self.rng = default_rng(seed)

    @classmethod
    def from_default(
        cls,
        openai_generator_llm: str = "gpt-3.5-turbo-16k",
        openai_filter_llm: str = "gpt-4",
        chat_qa: float = 0.3,
        chunk_size: int = 512,
        testset_distribution: dict = DEFAULT_TEST_DISTRIBUTION,
    ):
        generator_llm = llm_factory(openai_generator_llm)
        critic_llm = llm_factory(openai_filter_llm)
        embeddings_model = OpenAIEmbeddings()  # type: ignore
        return cls(
            generator_llm=generator_llm,
            critic_llm=critic_llm,
            embeddings_model=embeddings_model,
            chat_qa=chat_qa,
            chunk_size=chunk_size,
            testset_distribution=testset_distribution,
        )

    def _get_evolve_type(self) -> str:
        """
        Decides question evolution type based on probability
        """
        prob = self.rng.uniform(0, 1)
        print("yao-debug: evolve type prob:", prob)
        return next(
            (key for key in self.testset_distribution.keys() if prob <= self.testset_distribution[key]),
            "simple",
        )

    def _filter_context(self, context: str) -> bool:
        """
        context: str
            The input context

        Checks if the context is has information worthy of framing a question
        """
        human_prompt = SCORE_CONTEXT.format(context=context)
        prompt = ChatPromptTemplate.from_messages([human_prompt])
        results = self.critic_llm.generate(prompts=[prompt])
        output = results.generations[0][0].text.strip()
        score = load_as_score(output)
        return score >= self.threshold

    def _seed_question(self, context: str) -> str:
        human_prompt = SEED_QUESTION.format(context=context)
        prompt = ChatPromptTemplate.from_messages([human_prompt])
        results = self.generator_llm.generate(prompts=[prompt])
        return results.generations[0][0].text.strip()

    def _filter_question(self, question: str) -> bool:
        human_prompt = FILTER_QUESTION.format(question=question)
        prompt = ChatPromptTemplate.from_messages([human_prompt])

        results = self.critic_llm.generate(prompts=[prompt])
        results = results.generations[0][0].text.strip()
        json_results = load_as_json(results)
        return json_results.get("verdict") != "No"

    def _reasoning_question(self, question: str, context: str) -> str:
        return self._qc_template(REASONING_QUESTION, question, context)

    def _condition_question(self, question: str, context: str) -> str:
        return self._qc_template(CONDITIONAL_QUESTION, question, context)

    def _multicontext_question(self, question: str, context1: str, context2: str) -> str:
        human_prompt = MULTICONTEXT_QUESTION.format(question=question, context1=context1, context2=context2)
        prompt = ChatPromptTemplate.from_messages([human_prompt])
        results = self.generator_llm.generate(prompts=[prompt])
        return results.generations[0][0].text.strip()

    def _compress_question(self, question: str) -> str:
        return self._question_transformation(COMPRESS_QUESTION, question=question)

    def _conversational_question(self, question: str) -> str:
        return self._question_transformation(CONVERSATION_QUESTION, question=question)

    def _question_transformation(self, prompt, question: str) -> str:
        human_prompt = prompt.format(question=question)
        prompt = ChatPromptTemplate.from_messages([human_prompt])
        results = self.generator_llm.generate(prompts=[prompt])
        return results.generations[0][0].text.strip()

    def _qc_template(self, prompt, question, context) -> str:
        human_prompt = prompt.format(question=question, context=context)
        prompt = ChatPromptTemplate.from_messages([human_prompt])
        results = self.generator_llm.generate(prompts=[prompt])
        return results.generations[0][0].text.strip()

    def _generate_answer(self, question: str, context: t.List[str]) -> t.List[str]:
        return [self._qc_template(ANSWER_FORMULATE, ques, context[i]) for i, ques in enumerate(question.split("\n"))]

    def _generate_context(self, question: str, text_chunk: str) -> t.List[str]:
        return [self._qc_template(CONTEXT_FORMULATE, ques, text_chunk) for ques in question.split("\n")]

    def _remove_nodes(self, available_indices: t.List[BaseNode], node_idx: t.List) -> t.List[BaseNode]:
        for idx in node_idx:
            available_indices.remove(idx)
        return available_indices

    def _generate_doc_nodes_map(self, document_nodes: t.List[BaseNode]) -> t.Dict[str, t.List[BaseNode]]:
        doc_nodes_map: t.Dict[str, t.List[BaseNode]] = defaultdict(list)
        for node in document_nodes:
            if node.ref_doc_id:
                doc_nodes_map[node.ref_doc_id].append(node)

        return doc_nodes_map  # type: ignore

    def _get_neighbour_node(self, node: BaseNode, related_nodes: t.List[BaseNode]) -> t.List[BaseNode]:
        if len(related_nodes) < 2:
            warnings.warn("No neighbors exists")
            return [node]
        idx = related_nodes.index(node)
        ids = [idx - 1, idx] if idx == (len(related_nodes) - 1) else [idx, idx + 1]
        return [related_nodes[idx] for idx in ids]

    def _embed_nodes(self, nodes: t.List[BaseNode]) -> t.Dict[str, t.List[float]]:
        embeddings = {}
        for node in nodes:
            embeddings[node.id_] = list(self.embedding_model.embed_query(node.get_content()))

        return embeddings

    def generate(
        self,
        document_node: BaseNode,
    ) -> dict:
        text_chunk = document_node.get_content()
        score = self._filter_context(text_chunk)
        if not score:
            print("Failed to validate context.")
            return {}
        seed_question = self._seed_question(text_chunk)
        # is_valid_question = self._filter_question(seed_question)
        # if not is_valid_question:
        #     print("The seed question is not valid.")
        #     return {}

        question = seed_question
        context = self._generate_context(question, text_chunk)
        answer = self._generate_answer(question, context)
        for i, (ques, ctx, ans) in enumerate(zip(question.split("\n"), context, answer)):
            my_data_row = {
                "question": ques,
                "ground_truth_context": ctx,
                "ground_truth": ans,
                "question_type": "simple",
            }

        return my_data_row
