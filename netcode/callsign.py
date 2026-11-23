from config.constants import CALLSIGN_CHARS, CALLSIGN_MAX


def clean_callsign(text):
    """Upper case, letters/digits/dashes only, at most CALLSIGN_MAX long."""
    text = str(text or "").upper()
    return "".join(c for c in text if c in CALLSIGN_CHARS)[:CALLSIGN_MAX].strip('-')
