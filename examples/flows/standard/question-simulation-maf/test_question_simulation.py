"""Tests for question-simulation MAF workflow.

Runs the workflow end-to-end against Azure OpenAI and verifies output format
and behaviour for both STOP and CONTINUE conversation scenarios.

Requires AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT
to be set (via .env or environment).
"""

import asyncio

from workflow import QuestionSimInput, create_workflow


# ---------------------------------------------------------------------------
# Sample inputs and expected outputs
# ---------------------------------------------------------------------------

# Case 1: Multi-turn conversation that should CONTINUE — the human keeps asking
# substantive follow-up questions, the bot gives rich answers with more to explore.
CONTINUE_INPUT = QuestionSimInput(
    chat_history=[
        {
            "inputs": {"question": "Can you introduce something about large language model?"},
            "outputs": {
                "answer": (
                    "A large language model (LLM) is a type of language model that is distinguished "
                    "by its ability to perform general-purpose language generation and understanding. "
                    "These models learn statistical relationships from text documents through a "
                    "self-supervised and semi-supervised training process that is computationally "
                    "intensive. LLMs are artificial neural networks, the largest and most capable "
                    "of which are built with a transformer-based architecture. Some recent "
                    "implementations are based on other architectures, such as recurrent neural "
                    "network variants and Mamba. LLMs can be used for text generation, a form of "
                    "generative AI, by taking an input text and repeatedly predicting the next "
                    "token or word. Notable examples include OpenAI's GPT series, Google's PaLM "
                    "and Gemini, Meta's LLaMA family, and Anthropic's Claude models."
                ),
            },
        },
        {
            "inputs": {"question": "What is the transformer architecture you mentioned?"},
            "outputs": {
                "answer": (
                    "The transformer is a deep learning architecture introduced in the 2017 "
                    "paper 'Attention Is All You Need' by Google researchers. It uses self-attention "
                    "mechanisms to process sequences in parallel, making it much faster to train "
                    "than previous recurrent models. The key innovation is multi-head attention, "
                    "which allows the model to focus on different parts of the input simultaneously."
                ),
            },
        },
    ],
    question_count=3,
)

# Case 2: Conversation that should STOP — the human said thanks with no question,
# the bot replied with just a polite closing.
STOP_INPUT = QuestionSimInput(
    chat_history=[
        {
            "inputs": {"question": "Thanks for the info. I'll look into it."},
            "outputs": {
                "answer": "You're welcome! If you need anything else, feel free to ask.",
            },
        }
    ],
    question_count=3,
)

# Case 3: Multi-turn conversation that should CONTINUE.
MULTI_TURN_INPUT = QuestionSimInput(
    chat_history=[
        {
            "inputs": {"question": "What is machine learning?"},
            "outputs": {
                "answer": (
                    "Machine learning is a subset of artificial intelligence that enables "
                    "systems to learn and improve from experience without being explicitly "
                    "programmed. It focuses on developing algorithms that can access data "
                    "and use it to learn for themselves."
                ),
            },
        },
        {
            "inputs": {"question": "What are the main types of machine learning?"},
            "outputs": {
                "answer": (
                    "There are three main types: supervised learning, unsupervised learning, "
                    "and reinforcement learning. Supervised learning uses labeled data, "
                    "unsupervised learning finds patterns in unlabeled data, and reinforcement "
                    "learning learns through trial and error with rewards."
                ),
            },
        },
    ],
    question_count=2,
)

# Case 4: Single question requested — multi-turn to ensure CONTINUE.
SINGLE_Q_INPUT = QuestionSimInput(
    chat_history=[
        {
            "inputs": {"question": "What is the transformer architecture?"},
            "outputs": {
                "answer": (
                    "The transformer is a deep learning architecture introduced in the 2017 "
                    "paper 'Attention Is All You Need' by Google researchers at NeurIPS. It "
                    "uses self-attention mechanisms to process sequences in parallel, making "
                    "it much faster to train than previous recurrent models like LSTMs."
                ),
            },
        },
        {
            "inputs": {"question": "How does self-attention work in transformers?"},
            "outputs": {
                "answer": (
                    "Self-attention computes a weighted sum of all positions in a sequence. "
                    "For each token, it creates query, key, and value vectors. The attention "
                    "score between two tokens is the dot product of the query of one with the "
                    "key of the other. These scores determine how much each token attends to "
                    "every other token, enabling the model to capture long-range dependencies."
                ),
            },
        },
    ],
    question_count=1,
)


# ---------------------------------------------------------------------------
# Helper: run a single test case
# ---------------------------------------------------------------------------

async def run_test(name: str, sim_input: QuestionSimInput, expect_stop: bool):
    """Run the workflow and verify the output."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"  chat_history turns: {len(sim_input.chat_history)}")
    print(f"  question_count: {sim_input.question_count}")
    print(f"  expect_stop: {expect_stop}")
    print(f"{'='*60}")

    workflow = create_workflow()
    result = await workflow.run(sim_input)
    output = result.get_outputs()[0]
    print(f"  Output:\n    {output!r}")

    errors = []

    # Basic type check
    if not isinstance(output, str):
        errors.append(f"Expected str output, got {type(output).__name__}")

    if expect_stop:
        # STOP case: output must be exactly "[STOP]"
        if output != "[STOP]":
            errors.append(f"Expected '[STOP]', got: {output!r}")
    else:
        # CONTINUE case: output must NOT be "[STOP]"
        if output == "[STOP]":
            errors.append("Expected generated questions but got '[STOP]'")
        # Should contain at least one non-empty line
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        if len(lines) < 1:
            errors.append("Expected at least 1 generated question, got empty output")
        # Number of questions should match question_count
        if len(lines) != sim_input.question_count:
            # This is a soft check — LLM may occasionally return fewer
            print(f"  WARNING: Expected {sim_input.question_count} questions, got {len(lines)}")

    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        return False
    else:
        print("  PASS")
        return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    test_cases = [
        ("continue_single_turn", CONTINUE_INPUT, False),
        ("stop_polite_close", STOP_INPUT, True),
        ("continue_multi_turn", MULTI_TURN_INPUT, False),
        ("continue_single_question", SINGLE_Q_INPUT, False),
    ]

    results = {}
    for name, sim_input, expect_stop in test_cases:
        passed = await run_test(name, sim_input, expect_stop)
        results[name] = passed

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
    print(f"\n  {passed}/{total} passed")

    if passed < total:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
