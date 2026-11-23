import re

from core.session import CALLSIGN_WORDS
from utility.profanity import check_for_profanity


def test_all_generated_callsigns_are_clean():
    for word in CALLSIGN_WORDS:
        for n in range(1, 10):
            assert not check_for_profanity(f"{word}-{n}"), f"{word}-{n}"


def test_short_entries_do_not_flag_substrings():
    for text in ("HUNTER-1", "SNIPER-2", "FROGGER", "FROG-1", "HUN", "NIP", "SLOPE", "88", "A88B", "NIPPER", "HOMER"):
        assert not check_for_profanity(text), text


def test_short_entries_flag_whole_words():
    for text in ("you wog", "n1gger", "w.o.p"):
        assert check_for_profanity(text), text


def test_long_entries_still_substring_matched():
    assert check_for_profanity("xxniggerxx")
    assert check_for_profanity("n i g g e r")
    assert check_for_profanity("heil hitler")
