from promptflow import tool

def string_to_number(raw_string: str, processed_result: int) -> list:
    ''' Try to parse the prediction string and groundtruth string to float number. 
    Support parse int, float, fraction and recognize non-numeric string with wrong format.
    For example: '3/5', '6/10', '0.5', 'the answer is \box{2/3}', '4/7//8'
    '''
    float_number = 0.0
    try:
        float_number = float(raw_string) 
    except Exception:
        if '/' in raw_string: 
            split_list = raw_string.split('/') 
            if len(split_list) == 2: 
                numerator, denominator = split_list
                try:
                    float_number = float(numerator) / float(denominator) 
                except Exception:
                    processed_result = -1
            else:
                processed_result = -1 
        else:
            processed_result = -1
    return [float_number, processed_result]

@tool
def line_process(groundtruth: str, prediction: str) -> int:
    processed_result = 0
    # process prediction
    pred_float, processed_result = string_to_number(prediction, processed_result)
    # process groundtruth
    gt_float, processed_result = string_to_number(groundtruth, processed_result)

    if processed_result == 0:
        if round(pred_float, 10) == round(gt_float, 10): 
            processed_result = 1 
        else:
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

