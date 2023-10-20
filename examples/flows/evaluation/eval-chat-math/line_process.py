from promptflow import tool


@tool
def line_process(groundtruth: str, prediction: str) -> int:

    processed_result = 0

    # process prediction
    try:
        pred_float = float(prediction) # if the prediction string is a float number, convert it into float type.
    except Exception:
        if '/' in prediction: # if the prediction string is a fraction, try to parse it and convert it into float type.
            split_list = prediction.split('/') 
            if len(split_list) == 2: # if it is a fraction with right format
                numerator, denominator = split_list
                try:
                    pred_float = float(numerator) / float(denominator) 
                except Exception:
                    # for the wrong format with non-numeric numerator or zero denominator
                    processed_result = -1
            else:
                # for the wrong format with multiple '/'
                processed_result = -1 
        else:
            # for the wrong format without '/'
            processed_result = -1

    # process groundtruth
    try:
        gt_float = float(groundtruth) # if the groundtruth string is a float number, convert it into float type.
    except Exception:
        if '/' in groundtruth: # if the prediction string is a fraction, try to parse it and convert it into float type.
            numerator, denominator = groundtruth.split('/')
            try:
                gt_float = float(numerator) / float(denominator)
            except Exception:
                # for the wrong format with non-numeric numerator or zero denominator
                processed_result = -1
        else:
            # for the wrong format without '/'
            processed_result = -1

    if processed_result == 0:
        if round(pred_float, 10) == round(gt_float, 10): # avoid misjudgment caused by precision
            # for the correct answer
            processed_result = 1 
        else:
            # for the wrong answer
            processed_result = -1

    return processed_result


if __name__ == "__main__":
    processed_result = line_process("3/5", "6/10")
    print("The processed result is", processed_result)

    processed_result = line_process("1/2", "0.5")
    print("The processed result is", processed_result)

    processed_result = line_process("3", "5")
    print("The processed result is", processed_result)

    processed_result = line_process("2/3", "the answer is \box{2/3}")
    print("The processed result is", processed_result)

