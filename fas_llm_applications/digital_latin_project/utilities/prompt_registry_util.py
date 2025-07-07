# Version definitions (edit here to add/remove/change prompts)
SYSTEM_PROMPT_VERSIONS = [
    ("s1.1", 1, 1), # S1.1 - System Prompt for Language Level 1 - Version 1
    ("s1.2A", 1, "2A"), # S1.2A - System Prompt for Language Level 1 - Version 2A
    ("s1.2B", 1, "2B"),
    ("s1.2C", 1, "2C"),
    ("s2.1", 2, 1),
    ("s2.2A", 2, "2A"),
    ("s2.2B", 2, "2B"),
    ("s2.2C", 2, "2C"),
    ("s1.3B", 1, "3B"),
    ("s1.3C", 1, "3C"),
    ("s2.3B", 2, "3B"),
    ("s2.3C", 2, "3C")
    # ... add as needed
]

USER_PROMPT_VERSIONS = [
    ("u1.0", "virgil"), # U1.0 - User Prompt 1 - Virgil
    ("u2.0", "cicero"), # U2.0 - User Prompt 2 - Cicero
    ("u3.0", "livy"), # U3.0 - User Prompt 3 - Livy
]


LLM_AS_JUDGE_SYTEM_PROMPT_VERSIONS = [
    ("j1.1", 1, 1), # J1.1 - Judge Prompt for Language Level 1 - Version 1
    ("j2.1", 2, 1)  # J2.2 - Judge Prompt for Language Level 2 - Version 1
]

LLM_AS_JUDGE_USER_PROMPT_VERSIONS = [
    ("ju1.0",),
]

# System prompt filename pattern
def system_prompt_filename(system_key, level, version):
    return f"{system_key}_level{level}_version{version}_system.jinja2"

# User prompt file name pattern 
def user_prompt_filename(system_key, author):
    return f"{system_key}_{author}_user.jinja2"

# Judge prompt file name pattern
def judge_prompt_filename(system_key, level, version):
    return f"{system_key}_level{level}_version{version}_judge.jinja2"

def judge_system_prompt_filename(system_key, level, version):
    return f"{system_key}_level{level}_version{version}_judge_system.jinja2"

def judge_user_prompt_filename(user_key,):
    return f"{user_key}_judge_user.jinja2"

# The registry dictionaries are built once when this module is first imported!
system_prompt_registry = {
    key: system_prompt_filename(key, level, version) for key, level, version in SYSTEM_PROMPT_VERSIONS
}

user_prompt_registry = {
    key: user_prompt_filename(key, author) for key, author in USER_PROMPT_VERSIONS
}

judge_system_prompt_registry = {
    key: judge_system_prompt_filename(key, level, version) for key, level, version in LLM_AS_JUDGE_SYTEM_PROMPT_VERSIONS
}

judge_user_prompt_registry = {
    key: judge_user_prompt_filename(key) for (key,) in LLM_AS_JUDGE_USER_PROMPT_VERSIONS
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
    
def get_judge_prompt(key, prompt_type="system"):
    lookup_key = key[0].lower() + key[1:]
    if prompt_type == "system":
        try:
            return judge_system_prompt_registry[lookup_key]
        except KeyError:
            raise ValueError(f"Unknown judge system prompt key: {key}")
    elif prompt_type == "user":
        try:
            return judge_user_prompt_registry[lookup_key]
        except KeyError:
            raise ValueError(f"Unknown judge user prompt key: {key}")
    else:
        raise ValueError(f"Unknown prompt_type for judge prompt: {prompt_type}")
    
# TODO: If we grow to 4+ prompt registries, factor out registry+lookup-building code into a PromptRegistry class.