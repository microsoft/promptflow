from promptflow import tool

@tool
def parse_translation(translation_results:dict, language:str) -> str:  
  return translation_results[language]
