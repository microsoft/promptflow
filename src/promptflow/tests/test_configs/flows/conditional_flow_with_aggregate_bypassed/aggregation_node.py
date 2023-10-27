from promptflow import tool
from promptflow import log_metric

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def average(input: list):
  avg, cnt = 0, 0
  for num in input:
    if num!=None:
      avg += num
      cnt += 1
  if len(input) > 0:
    avg = avg/cnt
  return avg
