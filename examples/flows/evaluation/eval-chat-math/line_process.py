from promptflow import tool

def string_to_number(raw_string: str) -> float:
    ''' Try to parse the prediction string and groundtruth string to float number. 
    Support parse int, float, fraction and recognize non-numeric string with wrong format.
    Wrong format cases: 'the answer is \box{2/3}', '0, 5, or any number greater than 11', '4/7//9'
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
                    return None
            else:
                return None 
        else:
            return None
    return float_number

@tool
def line_process(groundtruth: str, prediction: str) -> int:
    pred_float = string_to_number(prediction)
    '''Early stop'''
    if (pred_float is None):
        return -1
    
    gt_float = string_to_number(groundtruth)
    if (gt_float is None):
        return -1
    
    ''' both pred_float and gt_float are valid'''
    if round(pred_float, 10) == round(gt_float, 10):
        return 1
    else:
        return -1


if __name__ == "__main__":
    processed_result = line_process("3/5", "6/10")
    print("The processed result is", processed_result)

    processed_result = line_process("1/2", "0.5")
    print("The processed result is", processed_result)

    processed_result = line_process("3", "5")
    print("The processed result is", processed_result)

    processed_result = line_process("2/3", "the answer is \box{2/3}")
    print("The processed result is", processed_result)

