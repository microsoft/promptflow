from promptflow.core import tool
from promptflow.core import log_metric

@tool
def average(input: list):
  avg, cnt = 0, 0
  for num in input:
    if num!=None:
      avg += num
      cnt += 1
  if len(input) > 0:
    avg = avg/cnt
  log_metric("average", avg)
  return avg
