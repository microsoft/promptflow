from promptflow import tool
import numpy as np
from numpy.linalg import norm


@tool
def compute_ada_cosine_similarity(a, b) -> float:
    return np.dot(a, b)/(norm(a)*norm(b))
