import nltk.translate.bleu_score

from ._utils import nltk_tokenize


class BleuScoreEvaluator:
    def __init__(self):
        pass

    def __call__(self, *, reference: str, hypothesis: str, **kwargs):
        """Evaluate BLEU score."""
        reference_tokens = nltk_tokenize(reference)
        hypothesis_tokens = nltk_tokenize(hypothesis)

        smoothing_function = nltk.translate.bleu_score.SmoothingFunction().method4
        score = nltk.translate.bleu_score.sentence_bleu(
            [reference_tokens], hypothesis_tokens, smoothing_function=smoothing_function
        )
        assert isinstance(score, (float, int))

        return {"bleu_score": score}
