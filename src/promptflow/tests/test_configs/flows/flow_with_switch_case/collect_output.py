from promptflow import tool

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(
  accuracy: float=float('nan'), 
  perceived_intelligence: float=float('nan'), 
  groundedness: float=float('nan')) -> str:
  return {
    'accuracy': accuracy, 
    'perceived_intelligence': perceived_intelligence,
    'groundedness': groundedness}