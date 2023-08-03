from promptflow import tool


@tool
def generate_goal(items: list = []) -> str:
    """
    Generate a numbered list from given items based on the item_type.

    Args:
        items (list): A list of items to be numbered.

    Returns:
        str: The formatted numbered list.
    """
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))
