import asyncio
from workflow import workflow


async def main():
    """Run the workflow with multiple queries to demonstrate the switch logic."""

    # Test cases targeting each switch condition
    test_cases = [
        ("When will my order be shipped?", "order_search"),
        ("Where is my order?", "order_search"),
        ("Can you track my package?", "order_search"),
        ("Tell me about this product", "product_info"),
        ("What is the specification?", "product_info"),
        ("Who manufactures this?", "product_info"),
        ("Recommend a good product", "product_recommendation"),
        ("What products do you suggest?", "product_recommendation"),
        ("Give me product recommendations", "product_recommendation"),
        ("Something completely random query", "default/unknown"),
    ]

    print("=" * 80)
    print("Testing Conditional Switch Workflow")
    print("=" * 80)
    print()

    results_by_intention = {}

    for i, (query, expected_intention) in enumerate(test_cases, 1):
        print(f"Test {i:2d}: {query}")
        print(f"         Expected intention: {expected_intention}")

        result = await workflow.run(query)
        response = result.get_outputs()[0]
        print(f"         Response: {response}")

        # Track results
        if expected_intention not in results_by_intention:
            results_by_intention[expected_intention] = []
        results_by_intention[expected_intention].append(response)

        print()

    print("=" * 80)
    print("Summary of Switch Paths:")
    print("=" * 80)

    intention_labels = {
        "order_search": "📦 Order Search",
        "product_info": "ℹ️  Product Info",
        "product_recommendation": "⭐ Product Recommendation",
        "default/unknown": "❓ Default/Unknown",
    }

    for intention, label in intention_labels.items():
        if intention in results_by_intention:
            count = len(results_by_intention[intention])
            print(f"{label}: {count} matched")
            for response in results_by_intention[intention]:
                print(f"  → {response}")
        else:
            print(f"{label}: 0 matched")

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
