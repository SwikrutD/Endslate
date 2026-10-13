"""Language name and code handling, normalized to ISO 639-1 for output."""
from __future__ import annotations

# name or 639-2 code -> 639-1 code
_MAP = {
    "en": "en", "eng": "en", "english": "en", "en-us": "en", "en-gb": "en",
    "es": "es", "spa": "es", "spanish": "es", "espanol": "es", "castilian": "es",
    "latin american": "es", "latino": "es",
    "fr": "fr", "fre": "fr", "fra": "fr", "french": "fr",
    "de": "de", "ger": "de", "deu": "de", "german": "de", "deutsch": "de",
    "it": "it", "ita": "it", "italian": "it",
    "pt": "pt", "por": "pt", "portuguese": "pt", "brazilian": "pt", "brazilian portuguese": "pt",
    "nl": "nl", "dut": "nl", "nld": "nl", "dutch": "nl",
    "da": "da", "dan": "da", "danish": "da",
    "sv": "sv", "swe": "sv", "swedish": "sv",
    "no": "no", "nor": "no", "norwegian": "no", "nob": "no",
    "fi": "fi", "fin": "fi", "finnish": "fi",
    "pl": "pl", "pol": "pl", "polish": "pl",
    "ru": "ru", "rus": "ru", "russian": "ru",
    "uk": "uk", "ukr": "uk", "ukrainian": "uk",
    "cs": "cs", "cze": "cs", "ces": "cs", "czech": "cs",
    "sk": "sk", "slo": "sk", "slk": "sk", "slovak": "sk",
    "sl": "sl", "slv": "sl", "slovenian": "sl",
    "hu": "hu", "hun": "hu", "hungarian": "hu",
    "ro": "ro", "rum": "ro", "ron": "ro", "romanian": "ro",
    "bg": "bg", "bul": "bg", "bulgarian": "bg",
    "el": "el", "gre": "el", "ell": "el", "greek": "el",
    "tr": "tr", "tur": "tr", "turkish": "tr",
    "he": "he", "heb": "he", "hebrew": "he",
    "ar": "ar", "ara": "ar", "arabic": "ar",
    "fa": "fa", "per": "fa", "fas": "fa", "persian": "fa", "farsi": "fa",
    "hi": "hi", "hin": "hi", "hindi": "hi",
    "ta": "ta", "tam": "ta", "tamil": "ta",
    "te": "te", "tel": "te", "telugu": "te",
    "kn": "kn", "kan": "kn", "kannada": "kn",
    "ml": "ml", "mal": "ml", "malayalam": "ml",
    "bn": "bn", "ben": "bn", "bengali": "bn",
    "mr": "mr", "mar": "mr", "marathi": "mr",
    "gu": "gu", "guj": "gu", "gujarati": "gu",
    "pa": "pa", "pan": "pa", "punjabi": "pa",
    "ur": "ur", "urd": "ur", "urdu": "ur",
    "ja": "ja", "jpn": "ja", "japanese": "ja",
    "ko": "ko", "kor": "ko", "korean": "ko",
    "zh": "zh", "chi": "zh", "zho": "zh", "chinese": "zh",
    "sim chinese": "zh", "tra chinese": "zh", "cantonese": "zh", "mandarin": "zh",
    "th": "th", "tha": "th", "thai": "th",
    "vi": "vi", "vie": "vi", "vietnamese": "vi",
    "id": "id", "ind": "id", "indonesian": "id",
    "ms": "ms", "may": "ms", "msa": "ms", "malay": "ms",
    "hr": "hr", "hrv": "hr", "croatian": "hr",
    "sr": "sr", "srp": "sr", "serbian": "sr",
    "bs": "bs", "bos": "bs", "bosnian": "bs",
    "et": "et", "est": "et", "estonian": "et",
    "lv": "lv", "lav": "lv", "latvian": "lv",
    "lt": "lt", "lit": "lt", "lithuanian": "lt",
    "is": "is", "ice": "is", "isl": "is", "icelandic": "is",
    "sq": "sq", "alb": "sq", "sqi": "sq", "albanian": "sq",
    "mk": "mk", "mkd": "mk", "macedonian": "mk",
}

ALL_TOKENS = frozenset(_MAP)

# Words that mean "several languages", not one.
MULTI = frozenset({"multi", "multilang", "multisub", "dual", "dualaudio"})


def normalize(value: str) -> str:
    """Return an ISO 639-1 code, or '' if the value names no language."""
    if not value:
        return ""
    key = value.strip().lower()
    for sep in ("_", "-", "."):
        key = key.replace(sep, " ")
    key = " ".join(key.split())
    if key in _MAP:
        return _MAP[key]
    # "Latin American.spa" style: try the last whitespace-separated word too.
    parts = key.split()
    if parts and parts[-1] in _MAP:
        return _MAP[parts[-1]]
    # "English SDH" names its language first. "It Follows" and "No Country for
    # Old Men" do not, so a leading word only counts when it is a full name.
    if parts and len(parts[0]) > 3 and parts[0] in _MAP:
        return _MAP[parts[0]]
    return ""


def is_english(code: str) -> bool:
    return code == "en"


# Two-letter codes and a handful of three-letter ones are ordinary English
# words ("it", "no", "mr", "may", "per"). Treating those as release noise
# eats real titles, so the noise vocabulary is deliberately narrower.
_AMBIGUOUS = frozenset({
    "may", "per", "ice", "nor", "fin", "pan", "mar", "ben", "dan", "pol",
    "ind", "est", "bos", "sub", "ell", "ron", "srp", "lit", "kan", "mal",
    "tel", "tam", "chi", "ita", "alb", "sqi", "gre", "tur", "urd", "slo",
})

# Full language names ("Greek", "English") appear in real titles, so only the
# three-letter codes are treated as release noise, and only the unambiguous ones.
NOISE_TOKENS = frozenset(
    tok for tok in _MAP
    if len(tok) == 3 and tok not in _AMBIGUOUS
)
