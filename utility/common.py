import pygame
from utility.constants import *
import math
from asset_handlers.audio_manager import AudioManager
audio_manager = AudioManager()


def collect_inputs():
    keys = pygame.key.get_pressed()

    inputs = {
        # Movement
        'left': keys[pygame.K_a],
        'right': keys[pygame.K_d],
        'up': keys[pygame.K_w],
        'down': keys[pygame.K_s],
        'arrow_key_left': keys[pygame.K_LEFT],
        'arrow_key_right': keys[pygame.K_RIGHT],
        'arrow_key_up': keys[pygame.K_UP],
        'arrow_key_down': keys[pygame.K_DOWN],

        # Common actions
        'space': keys[pygame.K_SPACE],
        'enter': keys[pygame.K_RETURN],
        'escape': keys[pygame.K_ESCAPE],
        'tab': keys[pygame.K_TAB],
        'esc': keys[pygame.K_ESCAPE],

        # Modifiers
        'left_shift': keys[pygame.K_LSHIFT],
        'right_shift': keys[pygame.K_RSHIFT],
        'ctrl': keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL],
        'left_alt': keys[pygame.K_LALT],
        'right_alt': keys[pygame.K_RALT],

        # Letters (your existing ones + common game keys)
        'q': keys[pygame.K_q],
        'e': keys[pygame.K_e],
        'r': keys[pygame.K_r],
        'g': keys[pygame.K_g],
        'h': keys[pygame.K_h],
        'i': keys[pygame.K_i],
        'j': keys[pygame.K_j],
        'k': keys[pygame.K_k],
        'l': keys[pygame.K_l],
        'm': keys[pygame.K_m],
        'o': keys[pygame.K_o],
        'p': keys[pygame.K_p],
        'x': keys[pygame.K_x],
        'c': keys[pygame.K_c],
        'f': keys[pygame.K_f],
        'z': keys[pygame.K_z],
        't': keys[pygame.K_t],
        'n': keys[pygame.K_n],

        # Numbers
        '1': keys[pygame.K_1],
        '2': keys[pygame.K_2],
        '3': keys[pygame.K_3],
        '4': keys[pygame.K_4],
        '5': keys[pygame.K_5],
        '6': keys[pygame.K_6],
        '7': keys[pygame.K_7],
        '8': keys[pygame.K_8],
        '9': keys[pygame.K_9],
        '0': keys[pygame.K_0],
    }

    return inputs


def blink_cursor():
    return "_" if pygame.time.get_ticks() // 500 % 2 == 0 else " "


def edit_text(events, text, allowed, max_len):
    """Apply this frame's typing to `text`: backspace, plus characters `allowed` accepts."""
    for event in events:
        if event.type != pygame.KEYDOWN:
            continue
        if event.key == pygame.K_BACKSPACE:
            text = text[:-1]
            audio_manager.play_sfx('typing_click', force=True)
        elif event.unicode and allowed(event.unicode) and len(text) < max_len:
            text += event.unicode
            audio_manager.play_sfx('typing_click', force=True)

    return text


def dfs_sqrt_distance(x1, y1, pos):
    dx = pos[0] - x1
    dy = pos[1] - y1
    return math.sqrt(dx ** 2 + dy ** 2)


def squared_distance(start, end, min_distance):
    dx = start[0] - end[0]
    dy = start[1] - end[1]
    distance = (dx ** 2) + (dy ** 2)
    state = False
    if distance < min_distance ** 2:
        state = True
    return distance, state


def sqrt_distance(start, end, min_distance):
    dx = start[0] - end[0]
    dy = start[1] - end[1]
    distance = math.sqrt((dx ** 2) + (dy ** 2))
    state = False
    if distance < min_distance:
        state = True
    return distance, state


def in_quadrant(origin_x, origin_y, direction_deg, target_pos):
    target_x, target_y = target_pos
    rel_x = target_x - origin_x
    rel_y = target_y - origin_y

    if direction_deg == 0:  # North
        return rel_y < 0
    elif direction_deg == 45:  # NE
        return rel_x > 0 > rel_y
    elif direction_deg == 90:  # East
        return rel_x > 0
    elif direction_deg == 135:  # SE
        return rel_x > 0 and rel_y > 0
    elif direction_deg == 180:  # South
        return rel_y > 0
    elif direction_deg == 225:  # SW
        return rel_x < 0 < rel_y
    elif direction_deg == 270:  # West
        return rel_x < 0
    elif direction_deg == 315:  # NW
        return rel_x < 0 and rel_y < 0

    return False


def end_blit():
    from asset_handlers.crt import crt
    crt.apply(pygame.display.get_surface())
    pygame.display.flip()




# Profanity section
import re
import unicodedata

REPLACEMENTS = [
    "LOSER", "REDDITOR", "BOOT LICKER", "CUCK", "JOBLESS",
    "REDDIT MOD", "DISCORD MOD", "CHUD", "CRINGE", "GOY"
]

_LEET = {
    "a": "[a4@]", "e": "[e3]", "g": "[g9q]", "i": "[i1l!|]", "l": "[l1|i]",
    "o": "[o0]", "s": "[s5$z]", "t": "[t7+]", "u": "[uv]",
}
_SEP = r"[\W_]{0,2}"

_WORDS = [
    # Racial and ethnic slurs
    "nigger", "niggers", "nigga", "niggas",
    "coon", "darkie", "jigaboo", "sambo",
    "spook", "pickaninny", "porch monkey",
    "chink", "chinks", "gook", "gooks",
    "zipperhead", "slope", "slant",
    "coolie", "ching chong",
    "jap", "japs", "nip", "nips",
    "spic", "spics", "spick", "wetback",
    "beaner", "greaser", "border hopper",
    "kike", "kikes", "heeb", "yid",
    "hymie", "sheeny",
    "raghead", "towelhead", "sandnigger",
    "camel jockey", "sand monkey",
    "redskin", "injun", "squaw",
    "wagon burner", "prairie nigger",
    "gyppo", "gypo",
    "cracker", "honky", "white trash",
    "paki", "pakis",
    "kaffir", "kafir", "kaffre",
    "abbo", "abo", "boong",
    "wog", "golliwog",
    "mick", "dago", "wop", "guido",
    "kraut", "hun", "frog",
    "polack", "polak", "wetback",
    " dago", "cholo",

    # Antisemitism
    "jew rat", "jew pig", "jew bastard",
    "jewish parasite", "jewish vermin",
    "globalist cabal", "zionist parasite",
    "zionist scum", "jewish conspiracy",
    "blood libel", "jewish control",
    "gas the jews", "kill the jews",
    "death to jews", "exterminate jews",
    "heil hitler", "sieg heil",
    "white power", "white supremacy",
    "aryan supremacy", "master race",
    "race traitor", "racial purity",
    "final solution",

    # Anti-Black hate phrases
    "black people are inferior",
    "inferior race",
    "subhuman race",
    "go back to africa",
    "lynch them",
    "hang all blacks",
    "kill all blacks",
    "white is right",

    # Anti-Asian hate phrases
    "chinese virus",
    "yellow peril",
    "go back to china",
    "go back to japan",
    "asian invasion",

    # Xenophobia
    "go back to your country",
    "foreign invader",
    "illegal vermin",
    "immigrant vermin",
    "deport them all",
    "invading foreigners",
    "parasite immigrants",
    "ethnic cleansing",

    # Homophobia
    "faggot", "faggots", "fag", "fags",
    "dyke", "dykes",
    "homo", "homos",
    "tranny", "trannies",
    "sodomite", "sodomites",
    "fudgepacker", "poof", "poofter",
    "queer bait",

    # Transphobia
    "tranny freak",
    "gender freak",
    "transvestite freak",
    "mentally ill transgender",
    "fake woman",
    "fake man",
    "biological freak",

    # Religious hatred
    "muslim scum",
    "islamic vermin",
    "christian scum",
    "christian vermin",
    "jewish scum",
    "heathen filth",
    "infidel dogs",
    "kill all muslims",
    "kill all christians",
    "kill all jews",
    "death to islam",
    "death to christianity",
    "death to hinduism",

    # Disability-related slurs
    "retard", "retards", "retarded",
    "cripple", "cripples",
    "mongoloid", "spastic",
    "window licker",
    "vegetable",
    "imbecile",

    # General supremacist terminology
    "white genocide",
    "race mixing",
    "racial degeneracy",
    "racial contamination",
    "racial inferiority",
    "ethnic cleansing",
    "subhuman",
    "untermensch",
    "lebensunwertes leben",
    "blood and soil",
    "white nationalism",
    "racial separatism",
    "race war",
    "14 words",
    "88",
    "1488",
    "kkk",
    "ku klux klan",
    "nazi scum",
    "nazi bastard",
    "heil hitler"
]


def _pattern(word: str) -> str:
    return "".join(f"(?:{_LEET.get(c, re.escape(c))}{_SEP})+" for c in word)


_BANNED_RE = re.compile("|".join(_pattern(w) for w in _WORDS), re.IGNORECASE)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", text)


def check_for_profanity(text: str) -> bool:
    return bool(_BANNED_RE.search(_normalize(text)))
# end section
