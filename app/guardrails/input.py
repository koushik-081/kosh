import re

MAX_QUESTION_CHARS = 2000

# Common prompt-injection phrasings. Patterns, not an LLM: instant, and the 3b
# would cost ~15 s per question while still missing clever attacks.
INJECTION = re.compile(
    r"ignore (all |any |the )?(previous |prior |above |earlier |your )*(instructions|rules|prompts?)"
    r"|disregard (all |any |the )?(previous |prior |above |your )*(instructions|rules|prompts?)"
    r"|forget (all |everything|your (instructions|rules))"
    r"|(reveal|show|print|repeat|tell me) (me )?(your|the) (system )?(prompt|instructions|rules)"
    r"|system prompt"
    r"|(hidden|secret) (rules|instructions|prompt)|(rules|instructions|prompt) you (were|have been) given"
    r"|you are now\b|from now on,? you\b|pretend (to be|you are)|act as (an? )?(unrestricted|jailbroken|evil|dan)\b"
    r"|developer mode|jailbreak|\bDAN\b",
    re.IGNORECASE,
)


def check_question(question: str) -> str | None:
    """Return why the question is blocked, or None if it may go to the LLM."""
    if len(question) > MAX_QUESTION_CHARS:
        return f"the question is longer than {MAX_QUESTION_CHARS} characters"
    if INJECTION.search(question):
        return "it looks like an attempt to override Kosh's instructions"
    return None