
class BlocklistEvaluator:
    def __init__(self, blocklist):
        self._blocklist = blocklist

    def __call__(self, *, answer: str, **kwargs):
        score = any([word in answer for word in self._blocklist])
        return {"score": score}
