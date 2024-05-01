from typing import List, Dict


class BlocklistEvaluator:
    def __init__(self, blocklist: str):
        self.blocklist = blocklist

    def __call__(self, *, answer, **kwargs):
        score = any([word in answer for word in self.blocklist.split(",")])
        return {"score": score}
