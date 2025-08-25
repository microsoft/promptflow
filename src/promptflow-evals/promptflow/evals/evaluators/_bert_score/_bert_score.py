# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Optional

from promptflow._utils.async_utils import async_run_allowing_running_loop


class _AsyncBertScoreEvaluator:
    """
    Async implementation of BERTScore evaluator for semantic similarity measurement.
    BERTScore leverages pre-trained contextual embeddings from BERT to evaluate
    text generation quality by computing similarity scores for tokens in candidate
    and reference sentences.
    """

    def __init__(self, model_name: str = "microsoft/deberta-xlarge-mnli", lang: str = "en"):
        """
        Initialize the async BERTScore evaluator.
        
        :param model_name: Pre-trained model name for computing embeddings
        :type model_name: str
        :param lang: Language code for the text (affects tokenization)
        :type lang: str
        """
        self._model_name = model_name
        self._lang = lang
        self._bert_score = None

    def _initialize_bert_score(self):
        """
        Lazy initialization of BERTScore to avoid import errors if package not installed.
        """
        if self._bert_score is None:
            try:
                from bert_score import score
                self._bert_score = score
            except ImportError:
                raise ImportError(
                    "BERTScore package is required for BertScoreEvaluator. "
                    "Please install it with: pip install bert-score"
                )

    async def __call__(self, *, answer: str, ground_truth: str, **kwargs) -> dict:
        """
        Evaluate semantic similarity using BERTScore.
        
        :keyword answer: The generated answer to evaluate
        :paramtype answer: str
        :keyword ground_truth: The reference/ground truth text
        :paramtype ground_truth: str
        :return: Dictionary containing BERTScore metrics (precision, recall, f1)
        :rtype: dict
        """
        # Validate inputs
        if not (answer and answer.strip() and answer != "None") or not (
            ground_truth and ground_truth.strip() and ground_truth != "None"
        ):
            raise ValueError("Both 'answer' and 'ground_truth' must be non-empty strings.")

        # Initialize BERTScore if not already done
        self._initialize_bert_score()

        # Compute BERTScore
        # BERTScore expects lists of strings for batch processing
        candidates = [answer]
        references = [ground_truth]

        try:
            # Compute precision, recall, and F1 scores
            precision, recall, f1 = self._bert_score(
                candidates, 
                references, 
                model_type=self._model_name,
                lang=self._lang,
                verbose=False
            )
            
            # Extract scores (BERTScore returns tensors, convert to float)
            precision_score = float(precision[0])
            recall_score = float(recall[0])
            f1_score = float(f1[0])

            return {
                "bert_score_precision": precision_score,
                "bert_score_recall": recall_score,
                "bert_score_f1": f1_score
            }

        except Exception as e:
            # Handle potential errors gracefully
            raise RuntimeError(f"Error computing BERTScore: {str(e)}")


class BertScoreEvaluator:
    """
    BERTScore evaluator for measuring semantic similarity between generated text and reference text.
    
    BERTScore is a reference-free evaluation metric that leverages pre-trained contextual 
    embeddings from BERT to evaluate text generation quality. Unlike traditional metrics 
    like BLEU or ROUGE that rely on exact lexical matching, BERTScore computes similarity 
    scores based on contextual embeddings, making it more robust to paraphrasing and 
    semantic variations.
    
    The metric computes three scores:
    - Precision: How well the generated text matches the reference
    - Recall: How much of the reference is covered by the generated text  
    - F1: Harmonic mean of precision and recall
    
    **Usage**
    
    .. code-block:: python
    
        # Basic usage with default model
        evaluator = BertScoreEvaluator()
        result = evaluator(
            answer="The capital of France is Paris.",
            ground_truth="Paris is the capital city of France."
        )
        print(result)
        # Output: {
        #     "bert_score_precision": 0.95,
        #     "bert_score_recall": 0.92, 
        #     "bert_score_f1": 0.93
        # }
        
        # Usage with custom model
        evaluator = BertScoreEvaluator(
            model_name="bert-base-uncased",
            lang="en"
        )
        result = evaluator(
            answer="Machine learning is a subset of AI.",
            ground_truth="ML is a branch of artificial intelligence."
        )
    
    **Output format**
    
    .. code-block:: python
    
        {
            "bert_score_precision": 0.89,
            "bert_score_recall": 0.87,
            "bert_score_f1": 0.88
        }
    
    :param model_name: Pre-trained BERT model for computing embeddings. 
                      Defaults to 'microsoft/deberta-xlarge-mnli'
    :type model_name: str
    :param lang: Language code for proper tokenization. Defaults to 'en'
    :type lang: str
    """

    def __init__(self, model_name: str = "microsoft/deberta-xlarge-mnli", lang: str = "en"):
        """
        Initialize the BERTScore evaluator.
        
        :param model_name: Pre-trained model name for computing embeddings
        :type model_name: str
        :param lang: Language code for the text (affects tokenization)
        :type lang: str
        """
        self._async_evaluator = _AsyncBertScoreEvaluator(model_name, lang)

    def __call__(self, *, answer: str, ground_truth: str, **kwargs) -> dict:
        """
        Evaluate semantic similarity using BERTScore.
        
        :keyword answer: The generated answer to evaluate
        :paramtype answer: str
        :keyword ground_truth: The reference/ground truth text
        :paramtype ground_truth: str
        :return: Dictionary containing BERTScore metrics
        :rtype: dict
        """
        return async_run_allowing_running_loop(
            self._async_evaluator, answer=answer, ground_truth=ground_truth, **kwargs
        )

    def _to_async(self):
        """
        Get the async version of this evaluator.
        
        :return: The async evaluator instance
        :rtype: _AsyncBertScoreEvaluator
        """
        return self._async_evaluator
