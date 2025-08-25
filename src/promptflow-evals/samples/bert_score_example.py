#!/usr/bin/env python3
# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""
Example usage of BertScoreEvaluator for semantic similarity evaluation.

This script demonstrates how to use the BertScoreEvaluator to measure semantic
similarity between generated text and reference text using BERT-based embeddings.
"""

from promptflow.evals.evaluators import BertScoreEvaluator


def main():
    """
    Demonstrate BertScoreEvaluator usage with various examples.
    """
    print("🤖 BertScoreEvaluator Example Usage")
    print("=" * 50)
    
    # Initialize the evaluator with default settings
    print("\n1. Basic Usage with Default Model:")
    evaluator = BertScoreEvaluator()
    
    # Example 1: High semantic similarity
    print("\nExample 1: High semantic similarity")
    result1 = evaluator(
        answer="The capital of France is Paris.",
        ground_truth="Paris is the capital city of France."
    )
    print(f"Answer: 'The capital of France is Paris.'")
    print(f"Ground Truth: 'Paris is the capital city of France.'")
    print(f"Results: {result1}")
    
    # Example 2: Moderate semantic similarity
    print("\nExample 2: Moderate semantic similarity")
    result2 = evaluator(
        answer="Machine learning helps computers learn from data.",
        ground_truth="AI systems can be trained using datasets to improve performance."
    )
    print(f"Answer: 'Machine learning helps computers learn from data.'")
    print(f"Ground Truth: 'AI systems can be trained using datasets to improve performance.'")
    print(f"Results: {result2}")
    
    # Example 3: Low semantic similarity
    print("\nExample 3: Low semantic similarity")
    result3 = evaluator(
        answer="I love pizza for dinner.",
        ground_truth="The weather is sunny today."
    )
    print(f"Answer: 'I love pizza for dinner.'")
    print(f"Ground Truth: 'The weather is sunny today.'")
    print(f"Results: {result3}")
    
    # Example 4: Custom model usage
    print("\n2. Using Custom Model:")
    custom_evaluator = BertScoreEvaluator(
        model_name="bert-base-uncased",
        lang="en"
    )
    
    result4 = custom_evaluator(
        answer="Deep learning is a subset of machine learning.",
        ground_truth="Neural networks with multiple layers are part of ML."
    )
    print(f"Answer: 'Deep learning is a subset of machine learning.'")
    print(f"Ground Truth: 'Neural networks with multiple layers are part of ML.'")
    print(f"Results (custom model): {result4}")
    
    # Example 5: Batch evaluation simulation
    print("\n3. Batch Evaluation Example:")
    test_cases = [
        {
            "answer": "Python is a programming language.",
            "ground_truth": "Python is used for software development.",
            "description": "Programming language similarity"
        },
        {
            "answer": "The sun rises in the east.",
            "ground_truth": "Eastern horizon sees sunrise daily.",
            "description": "Astronomical fact paraphrasing"
        },
        {
            "answer": "Water boils at 100 degrees Celsius.",
            "ground_truth": "H2O reaches boiling point at 100°C.",
            "description": "Scientific fact with different notation"
        }
    ]
    
    print(f"{'Description':<35} {'Precision':<10} {'Recall':<10} {'F1-Score':<10}")
    print("-" * 70)
    
    for case in test_cases:
        result = evaluator(
            answer=case["answer"],
            ground_truth=case["ground_truth"]
        )
        print(f"{case['description']:<35} "
              f"{result['bert_score_precision']:<10.3f} "
              f"{result['bert_score_recall']:<10.3f} "
              f"{result['bert_score_f1']:<10.3f}")
    
    print("\n" + "=" * 50)
    print("💡 Tips for using BertScoreEvaluator:")
    print("- Higher scores indicate better semantic similarity")
    print("- F1 score is typically the most balanced metric")
    print("- Different models may give different results")
    print("- Consider the language setting for non-English text")
    print("- BERTScore is more robust to paraphrasing than exact-match metrics")


def demonstrate_comparison_with_other_metrics():
    """
    Show how BertScoreEvaluator compares to other similarity metrics.
    """
    print("\n🔍 Comparison with Other Metrics")
    print("=" * 50)
    
    from promptflow.evals.evaluators import F1ScoreEvaluator, BleuScoreEvaluator
    
    # Initialize evaluators
    bert_evaluator = BertScoreEvaluator()
    f1_evaluator = F1ScoreEvaluator()
    bleu_evaluator = BleuScoreEvaluator()
    
    # Test case: semantically similar but lexically different
    answer = "The car is red in color."
    ground_truth = "The automobile has a crimson hue."
    
    print(f"Answer: '{answer}'")
    print(f"Ground Truth: '{ground_truth}'")
    print("\nMetric Comparison:")
    
    # BERTScore (semantic similarity)
    bert_result = bert_evaluator(answer=answer, ground_truth=ground_truth)
    print(f"BERTScore F1: {bert_result['bert_score_f1']:.3f} (semantic similarity)")
    
    # F1 Score (lexical overlap)
    f1_result = f1_evaluator(answer=answer, ground_truth=ground_truth)
    print(f"F1 Score: {f1_result['f1_score']:.3f} (lexical overlap)")
    
    # BLEU Score (n-gram overlap)
    bleu_result = bleu_evaluator(answer=answer, ground_truth=ground_truth)
    print(f"BLEU Score: {bleu_result['bleu_score']:.3f} (n-gram overlap)")
    
    print("\n📊 Observation:")
    print("BERTScore typically performs better on semantically similar")
    print("but lexically different text compared to traditional metrics.")


if __name__ == "__main__":
    try:
        main()
        demonstrate_comparison_with_other_metrics()
    except ImportError as e:
        if "bert_score" in str(e):
            print("❌ Error: BERTScore package is not installed.")
            print("Please install it using: pip install bert-score")
            print("\nNote: This package requires PyTorch and may take some time to install.")
        else:
            print(f"❌ Import Error: {e}")
    except Exception as e:
        print(f"❌ Error running example: {e}")
        print("Make sure you have the required dependencies installed.")
