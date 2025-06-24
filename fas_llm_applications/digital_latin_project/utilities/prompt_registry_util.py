# Version definitions (edit here to add/remove/change prompts)
SYSTEM_PROMPT_VERSIONS = [
    ("s1.1", 1, 1), # S1.1 - System Prompt for Language Level 1 - Version 1
    ("s1.2A", 1, "2A"), # S1.2 - System Prompt for Language Level 1 - Version 2
    ("s1.2B", 1, "2B"),
    ("s1.2C", 1, "2C"),
    ("s2.1", 2, 1),
    ("s2.2A", 2, "2A"),
    ("s2.2B", 2, "2B"),
    ("s2.2C", 2, "2C"),
    # ... add as needed
]

USER_PROMPT_VERSIONS = [
    ("u1.0", "virgil"), # U1.0 - User Prompt 1 - Virgil
    ("u2.0", "cicero"), # U2.0 - User Prompt 2 - Cicero
    ("u3.0", "livy"), # U3.0 - User Prompt 3 - Livy
]

# TODO: Add LLM as Judge Prompts
LLM_AS_JUDGE_SYTEM_PROMPT_VERSIONS = []
LLM_AS_JUDGE_USER_PROMPT_VERSIONS = []

# System prompt filename pattern
def system_prompt_filename(system_key, level, version):
    return f"{system_key}_level{level}_version{version}_system.jinja2"

# User prompt file name pattern 
def user_prompt_filename(system_key, author):
    return f"{system_key}_{author}_user.jinja2"

# The registry dictionaries are built once when this module is first imported!
system_prompt_registry = {
    key: system_prompt_filename(key, level, version) for key, level, version in SYSTEM_PROMPT_VERSIONS
}

user_prompt_registry = {
    key: user_prompt_filename(key, author) for key, author in USER_PROMPT_VERSIONS
}

# A utility function for lookup & validation, returns the file name.
def get_system_prompt(key):
    lookup_key = key[0].lower() + key[1:]
    try:
        return system_prompt_registry[lookup_key]
    except KeyError:
        raise ValueError(f"Unknown system prompt key: {key}")
    
def get_user_prompt(key):
    lookup_key = key[0].lower() + key[1:]
    try:
        return user_prompt_registry[lookup_key]
    except KeyError:
        raise ValueError(f"Unknown system prompt key: {key}")
    
# TODO: If we grow to 4+ prompt registries, factor out registry+lookup-building code into a PromptRegistry class.