from promptflow.core import tool


@tool
def create_document(text: str, language: str, id: int) -> dict:
    """
    This tool creates a document input for document-based
    language skills.

    :param text: document text.
    :param language: document language.
    :param id: document id.
    """
    return {
        "text": text,
        "language": language,
        "id": str(id)
    }
