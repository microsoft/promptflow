def target_fn(question: str) -> str:
    """An example target function."""
    if "LV-426" in question:
        return {"answer": "There is nothing good there."}
    if "central heating" in question:
        return {"answer": "There is no central heating on the streets today, but it will be, I promise."}
    if "strange" in question:
        return {"answer": "The life is strange..."}


def target_fn2(question: str) -> str:
    answer = target_fn(question)["answer"]
    return {"response": answer}
