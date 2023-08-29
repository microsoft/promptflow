from promptflow import tool


@tool
def line_process(groundtruth: str, prediction: str) -> int:

    processed_result = 0

    if prediction == "JSONDecodeError" or prediction.startswith("Unknown Error:"):
        processed_result = -1
        return processed_result

    try:
        groundtruth = float(groundtruth)
        prediction = float(prediction)
    except ValueError:
        processed_result = -1
        return processed_result

    if round(prediction, 2) == round(groundtruth, 2):
        processed_result = 1

    return processed_result


if __name__ == "__main__":
    processed_result = line_process("1.0", "1")
    print("The processed result is", processed_result)

    processed_result = line_process("3.14", "3.1415926")
    print("The processed result is", processed_result)

    processed_result = line_process("2.1", "2.0")
    print("The processed result is", processed_result)

    processed_result = line_process("1.0", "JSONDecodeError")
    print("The processed result is", processed_result)

    processed_result = line_process("1.0", "No module named 'numpy'")
    print("The processed result is", processed_result)
