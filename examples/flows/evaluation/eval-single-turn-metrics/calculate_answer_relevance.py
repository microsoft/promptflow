from promptflow.core import tool
from typing import List
import numpy as np


def calculate_similarity(question_embedding: List, generated_question_embedding: List):
    embedding1 = np.array(question_embedding)
    embedding2 = np.array(generated_question_embedding)

    # Compute the dot product of the two embeddings
    dot_product = np.dot(embedding1, embedding2)

    # Compute the L2 norms (i.e., the lengths) of each embedding
    norm_embedding1 = np.linalg.norm(embedding1)
    norm_embedding2 = np.linalg.norm(embedding2)

    # Compute the cosine similarity
    return dot_product / (norm_embedding1 * norm_embedding2)


@tool
def calculate(question_embedding: List, generated_question_embedding: List, noncommittal: bool) -> str:
    cosine_sim = calculate_similarity(question_embedding, generated_question_embedding)
    print("noncommittal: ")
    print(noncommittal)
    print(cosine_sim)
    score = 5 * cosine_sim * int(not noncommittal)

    return score if score >= 1 else 1
