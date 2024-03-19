import pytest

from geval import parse_output


@pytest.mark.parametrize(
    "input_str, expected_output",
    [
        ("4", 4.0),
        ("4.4", 4.4),
        ("3 is the score because", 3.0),
        (" 2 ", 2.0),
        (" 2a", 2.0),
        ("0", 0.0),
        ("0/5", 0.0),
    ],
)
def test_parse_valid_score(input_str, expected_output):
    assert parse_output(input_str, max=5) == expected_output


@pytest.mark.parametrize(
    "input_str",
    [
        "No score at beginning",
        "",
        "     ",
        "aaaa2bbb",
        "-2-",
        "-2a",
        "a-2a",
        "-2",
        "-2.0",
    ],
)
def test_parse_no_number_detected(input_str):
    with pytest.raises(ValueError, match="No number detected in input"):
        parse_output(input_str, max=5)


@pytest.mark.parametrize("input_str", ["6", " 1234 is the score because", "8.8"])
def test_parse_too_large_score(input_str):
    with pytest.raises(ValueError, match="larger than max score"):
        parse_output(input_str, max=5)


@pytest.mark.parametrize("input_str", [" 1 to 3 ", "5.5   99 "])
def test_parse_multiple_number_detected(input_str):
    with pytest.raises(ValueError, match="More than one number detected in input"):
        parse_output(input_str, max=5)
