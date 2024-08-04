from promptflow.evals.evaluators.aoai import BleuScoreEvaluator

# Single row test
bleu_eval = BleuScoreEvaluator()
score = bleu_eval(
    reference="The quick brown fox jumps over the lazy dog", hypothesis="The quick brown fox jumps over the lazy dog"
)
print(score)

# Batch run
