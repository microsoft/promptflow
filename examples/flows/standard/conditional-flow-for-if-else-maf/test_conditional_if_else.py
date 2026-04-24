import asyncio
from workflow import workflow


async def main():
    """Run the workflow with multiple inputs to demonstrate random conditions."""

    test_questions = [
        "What is Prompt flow?",
        "How does it work?",
        "Tell me more about the features",
        "What is machine learning?",
    ]

    print("=" * 70)
    print("Testing Conditional Workflow with Random Conditions")
    print("=" * 70)
    print()

    safe_count = 0
    unsafe_count = 0

    for i, question in enumerate(test_questions, 1):
        result = await workflow.run(question)
        output = result.get_outputs()[0]

        # Determine which path was taken based on the output
        is_safe_path = "Prompt flow is a suite" in output

        if is_safe_path:
            safe_count += 1
            status = "✓ SAFE"
        else:
            unsafe_count += 1
            status = "✗ UNSAFE"

        print(f"Test {i:2d} [{status}]: {question}")
        print(f"          → {output}")
        print()

    print("=" * 70)
    print("Results Summary:")
    print(f"  Safe paths:   {safe_count}/{len(test_questions)}")
    print(f"  Unsafe paths: {unsafe_count}/{len(test_questions)}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
