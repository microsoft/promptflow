def remove_prefix(text, prefix=None) -> str:
    """
    Given a string, removes specified prefix, if it has.

    >>> remove_prefix('hello world', 'world')
    'hello world'
    >>> remove_prefix('hello world', 'hello ')
    'world'
    >>> remove_prefix('promptflow_0.0.67', 'promptflow_')
    '0.0.67'

    :param text: string from which prefix will be removed.
    :param prefix: prefix to be removed.
    :return: string removed prefix.
    """
    if not text or not prefix:
        return text

    if not text.startswith(prefix):
        return text

    return text[len(prefix) :]


def convert_to_dictionary(text: str) -> dict:
    """
    Given a string like "key1/value1/key2/value2", convert it to a dictionary.

    :param text: string will be converted to dictionary.
    :return: dictionary
    """
    if not text:
        raise ValueError("Empty text")
    segments = text.strip().lstrip("/").rstrip("/").split("/")
    if len(segments) % 2 != 0:
        raise ValueError(f"Invalid text: {text}")

    dictionary = {}
    for i in range(0, len(segments), 2):
        key = segments[i]
        value = segments[i + 1]
        dictionary[key] = value
    return dictionary
