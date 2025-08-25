# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
from unittest.mock import MagicMock, patch

from promptflow.evals.evaluators import BertScoreEvaluator


@pytest.mark.unittest
class TestBertScoreEvaluator:
    """Test cases for BertScoreEvaluator."""

    def test_bert_score_evaluator_initialization(self):
        """Test that BertScoreEvaluator initializes correctly with default parameters."""
        evaluator = BertScoreEvaluator()
        assert evaluator._async_evaluator is not None
        assert evaluator._async_evaluator._model_name == "microsoft/deberta-xlarge-mnli"
        assert evaluator._async_evaluator._lang == "en"

    def test_bert_score_evaluator_custom_initialization(self):
        """Test that BertScoreEvaluator initializes correctly with custom parameters."""
        evaluator = BertScoreEvaluator(model_name="bert-base-uncased", lang="fr")
        assert evaluator._async_evaluator._model_name == "bert-base-uncased"
        assert evaluator._async_evaluator._lang == "fr"

    def test_bert_score_evaluator_invalid_inputs(self):
        """Test that BertScoreEvaluator raises ValueError for invalid inputs."""
        evaluator = BertScoreEvaluator()
        
        # Test empty answer
        with pytest.raises(ValueError, match="Both 'answer' and 'ground_truth' must be non-empty strings"):
            evaluator(answer="", ground_truth="Valid ground truth")
        
        # Test empty ground truth
        with pytest.raises(ValueError, match="Both 'answer' and 'ground_truth' must be non-empty strings"):
            evaluator(answer="Valid answer", ground_truth="")
        
        # Test None values
        with pytest.raises(ValueError, match="Both 'answer' and 'ground_truth' must be non-empty strings"):
            evaluator(answer="None", ground_truth="Valid ground truth")
        
        # Test whitespace-only strings
        with pytest.raises(ValueError, match="Both 'answer' and 'ground_truth' must be non-empty strings"):
            evaluator(answer="   ", ground_truth="Valid ground truth")

    @patch('bert_score.score')
    def test_bert_score_evaluator_successful_evaluation(self, mock_bert_score):
        """Test successful BERTScore evaluation with mocked bert_score."""
        # Mock the bert_score function to return sample scores
        mock_precision = MagicMock()
        mock_precision.__getitem__ = MagicMock(return_value=0.85)
        mock_recall = MagicMock()
        mock_recall.__getitem__ = MagicMock(return_value=0.82)
        mock_f1 = MagicMock()
        mock_f1.__getitem__ = MagicMock(return_value=0.835)
        
        mock_bert_score.return_value = (mock_precision, mock_recall, mock_f1)
        
        evaluator = BertScoreEvaluator()
        result = evaluator(
            answer="The capital of France is Paris.",
            ground_truth="Paris is the capital city of France."
        )
        
        # Verify the result structure and values
        assert isinstance(result, dict)
        assert "bert_score_precision" in result
        assert "bert_score_recall" in result
        assert "bert_score_f1" in result
        
        assert result["bert_score_precision"] == 0.85
        assert result["bert_score_recall"] == 0.82
        assert result["bert_score_f1"] == 0.835
        
        # Verify bert_score was called with correct parameters
        mock_bert_score.assert_called_once_with(
            ["The capital of France is Paris."],
            ["Paris is the capital city of France."],
            model_type="microsoft/deberta-xlarge-mnli",
            lang="en",
            verbose=False
        )

    @patch('bert_score.score')
    def test_bert_score_evaluator_custom_model(self, mock_bert_score):
        """Test BERTScore evaluation with custom model parameters."""
        # Mock the bert_score function
        mock_precision = MagicMock()
        mock_precision.__getitem__ = MagicMock(return_value=0.75)
        mock_recall = MagicMock()
        mock_recall.__getitem__ = MagicMock(return_value=0.78)
        mock_f1 = MagicMock()
        mock_f1.__getitem__ = MagicMock(return_value=0.765)
        
        mock_bert_score.return_value = (mock_precision, mock_recall, mock_f1)
        
        evaluator = BertScoreEvaluator(model_name="bert-base-uncased", lang="fr")
        result = evaluator(
            answer="Bonjour le monde",
            ground_truth="Salut tout le monde"
        )
        
        # Verify the result
        assert result["bert_score_precision"] == 0.75
        assert result["bert_score_recall"] == 0.78
        assert result["bert_score_f1"] == 0.765
        
        # Verify bert_score was called with custom parameters
        mock_bert_score.assert_called_once_with(
            ["Bonjour le monde"],
            ["Salut tout le monde"],
            model_type="bert-base-uncased",
            lang="fr",
            verbose=False
        )

    def test_bert_score_evaluator_import_error(self):
        """Test that ImportError is raised when bert_score package is not available."""
        evaluator = BertScoreEvaluator()
        
        # Simulate ImportError by setting _bert_score to None and patching the import
        evaluator._async_evaluator._bert_score = None
        
        with patch('builtins.__import__', side_effect=ImportError("No module named 'bert_score'")):
            with pytest.raises(ImportError, match="BERTScore package is required for BertScoreEvaluator"):
                evaluator(
                    answer="Test answer",
                    ground_truth="Test ground truth"
                )

    @patch('bert_score.score')
    def test_bert_score_evaluator_computation_error(self, mock_bert_score):
        """Test that RuntimeError is raised when bert_score computation fails."""
        # Mock bert_score to raise an exception
        mock_bert_score.side_effect = RuntimeError("CUDA out of memory")
        
        evaluator = BertScoreEvaluator()
        
        with pytest.raises(RuntimeError, match="Error computing BERTScore: CUDA out of memory"):
            evaluator(
                answer="Test answer",
                ground_truth="Test ground truth"
            )

    def test_bert_score_evaluator_to_async(self):
        """Test that _to_async returns the async evaluator."""
        evaluator = BertScoreEvaluator()
        async_evaluator = evaluator._to_async()
        
        assert async_evaluator is evaluator._async_evaluator
        assert hasattr(async_evaluator, '__call__')

    @patch('bert_score.score')
    def test_bert_score_evaluator_perfect_match(self, mock_bert_score):
        """Test BERTScore evaluation with identical texts (should have high scores)."""
        # Mock perfect scores for identical texts
        mock_precision = MagicMock()
        mock_precision.__getitem__ = MagicMock(return_value=1.0)
        mock_recall = MagicMock()
        mock_recall.__getitem__ = MagicMock(return_value=1.0)
        mock_f1 = MagicMock()
        mock_f1.__getitem__ = MagicMock(return_value=1.0)
        
        mock_bert_score.return_value = (mock_precision, mock_recall, mock_f1)
        
        evaluator = BertScoreEvaluator()
        identical_text = "This is exactly the same text."
        
        result = evaluator(
            answer=identical_text,
            ground_truth=identical_text
        )
        
        # Perfect match should yield perfect scores
        assert result["bert_score_precision"] == 1.0
        assert result["bert_score_recall"] == 1.0
        assert result["bert_score_f1"] == 1.0

    @patch('bert_score.score')
    def test_bert_score_evaluator_semantic_similarity(self, mock_bert_score):
        """Test BERTScore evaluation with semantically similar but different texts."""
        # Mock high but not perfect scores for semantically similar texts
        mock_precision = MagicMock()
        mock_precision.__getitem__ = MagicMock(return_value=0.92)
        mock_recall = MagicMock()
        mock_recall.__getitem__ = MagicMock(return_value=0.89)
        mock_f1 = MagicMock()
        mock_f1.__getitem__ = MagicMock(return_value=0.905)
        
        mock_bert_score.return_value = (mock_precision, mock_recall, mock_f1)
        
        evaluator = BertScoreEvaluator()
        
        result = evaluator(
            answer="Machine learning is a subset of artificial intelligence.",
            ground_truth="ML is a branch of AI that enables computers to learn."
        )
        
        # Semantically similar texts should have high scores
        assert result["bert_score_precision"] > 0.9
        assert result["bert_score_recall"] > 0.85
        assert result["bert_score_f1"] > 0.9
