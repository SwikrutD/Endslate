from endslate.sanitize import MAX_PATH, sanitize_component, shorten_to_fit


def test_illegal_characters_are_replaced_not_dropped():
    assert sanitize_component("Face/Off") == "Face Off"
    assert sanitize_component("Ender: Game") == "Ender - Game"
    assert sanitize_component('Say "Hi"') == "Say 'Hi'"


def test_apostrophes_and_unicode_survive():
    assert sanitize_component("Murphy's Law") == "Murphy's Law"
    assert sanitize_component("Lügen") == "Lügen"
    assert sanitize_component("結婚当天") == "結婚当天"


def test_reserved_names_are_suffixed():
    assert sanitize_component("CON") == "CON_"
    assert sanitize_component("nul.mkv") == "nul.mkv_"


def test_trailing_dots_and_spaces_go():
    assert sanitize_component("Trailing. ") == "Trailing"
    assert sanitize_component("   ") == "Untitled"


def test_shorten_respects_the_path_limit():
    directory = "M:\\Media\\Movies\\" + "x" * 200
    stem = "y" * 200
    assert len(directory) + len(shorten_to_fit(directory, stem, ".mkv")) + 5 < MAX_PATH
