import re
import unicodedata
from pathlib import Path

REPLACEMENTS = [
    "LOSER", "REDDITOR", "BOOT LICKER", "CUCK", "JOBLESS",
    "REDDIT MOD", "DISCORD MOD", "CHUD", "CRINGE", "GOY"
]

_LEET = {
    "a": "[a4@]", "e": "[e3]", "g": "[g9q]", "i": "[i1l!|]", "l": "[l1|i]",
    "o": "[o0]", "s": "[s5$z]", "t": "[t7+]", "u": "[uv]",
}
_SEP = r"[\W_]{0,2}"

def _load_words() -> list[str]:
    path = Path(__file__).with_name("profanity_words.txt")
    seen: dict[str, None] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        word = line.strip()
        if word and not word.startswith("#"):
            seen.setdefault(word.lower())
    return list(seen)


_WORDS = _load_words()


def _pattern(word: str) -> str:
    return "".join(f"(?:{_LEET.get(c, re.escape(c))}{_SEP})+" for c in word)


# Short entries (and bare numbers) are matched as whole words so they don't flag
# innocent text (e.g. "hun" in "HUNTER", "nip" in "SNIPER"). Long entries stay substring.
_SUBSTRING_MIN_LEN = 6
_WB_BEFORE = r"(?<![A-Za-z0-9])"
_WB_AFTER = r"(?![A-Za-z0-9])"


def _entry(word: str) -> str:
    word = word.strip()
    pat = _pattern(word)
    if len(word.replace(" ", "")) < _SUBSTRING_MIN_LEN:
        return f"{_WB_BEFORE}{pat}{_WB_AFTER}"
    return pat


_BANNED_RE = re.compile("|".join(_entry(w) for w in _WORDS), re.IGNORECASE)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", text)


def check_for_profanity(text: str) -> bool:
    return bool(_BANNED_RE.search(_normalize(text)))
