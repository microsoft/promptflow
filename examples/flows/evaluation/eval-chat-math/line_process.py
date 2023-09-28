from promptflow import tool


@tool
def line_process(groundtruth: str, prediction: str) -> int:

    processed_result = 0
    # process prediction
    try:
        pred_float = float(prediction)
    except Exception:
        if '/' in prediction:
            split_list = prediction.split('/')
            if len(split_list) == 2:
                numerator, denominator = split_list
                try:
                    pred_float = float(numerator) / float(denominator)
                except Exception:
                    processed_result = -1
            else:
                processed_result = -1
        else:
            processed_result = -1
    # process groundtruth
    try:
        gt_float = float(groundtruth)
    except:
        if '/' in groundtruth:
            numerator, denominator = groundtruth.split('/')
            try:
                gt_float = float(numerator) / float(denominator)
            except Exception:
                processed_result = -1
        else:
            processed_result = -1

    if processed_result == 0:
        if round(pred_float, 10) == round(gt_float, 10):
            processed_result = 1
        else:
            processed_result = -1

    return processed_result
