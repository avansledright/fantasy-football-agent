import re

def normalize_name(name: str) -> str:
    # Extend as needed: remove suffixes, punctuation, double spaces, etc.
    name = re.sub(r"\s+Jr\.?$", "", name)
    name = name.replace("’", "'")
    return name.strip()
