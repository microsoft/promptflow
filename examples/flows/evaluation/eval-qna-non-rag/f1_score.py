from promptflow import tool
from collections import Counter


@tool
def compute_f1_score(ground_truth: str, answer: str) -> str:
    import string
    import re

    class QASplitTokenizer:
        def __call__(self, line):
            """Tokenizes an input line using split() on whitespace

            :param line: a segment to tokenize
            :return: the tokenized line
            """

            return line.split()

    def normalize_text(text) -> str:
        """Lower text and remove punctuation, articles and extra whitespace."""

        def remove_articles(text):
            return re.sub(r"\b(a|an|the)\b", " ", text)

        def white_space_fix(text):
            return " ".join(text.split())

        def remove_punctuation(text):
            exclude = set(string.punctuation)
            return "".join(ch for ch in text if ch not in exclude)

        def lower(text):
            return text.lower()

        return white_space_fix(remove_articles(remove_punctuation(lower(text))))
    prediction_tokens = normalize_text(answer)
    reference_tokens = normalize_text(ground_truth)
    tokenizer = QASplitTokenizer()
    prediction_tokens = tokenizer(prediction_tokens)
    reference_tokens = tokenizer(reference_tokens)

    common_tokens = Counter(prediction_tokens) & Counter(reference_tokens)
    num_common_tokens = sum(common_tokens.values())

    if num_common_tokens == 0:
        f1 = 0.0
    else:
        precision = 1.0 * num_common_tokens / len(prediction_tokens)
        recall = 1.0 * num_common_tokens / len(reference_tokens)

        f1 = (2.0 * precision * recall) / (precision + recall)

    return f1
