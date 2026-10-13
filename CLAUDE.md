# Endslate: context for Claude

Endslate renames and reorganises a movie/TV/anime library (the owner's is `M:\Media`, with
`Movies\` and `Shows\` under it, and `Anime\` when there is one) into the layout Jellyfin
expects. An optional
`Downloads\` folder at the same level is a mixed staging area: each run classifies
episode files from season/episode markers, sends recognized media to `Movies\` or
`Shows\`, and leaves unrecognized contents there. It is a Python 3.10+
app with a PySide6 GUI (the main interface) and a small CLI. Windows is the only platform
it has to work on. The README is the user-facing documentation; read it first. This file
records what the README does not.

## Commands

```powershell
python -m pip install -r requirements.txt pytest
python -m pytest -q                               # whole suite, about 35 s, no network
python -m endslate gui                            # the app
python -m endslate plan "M:\Media" --offline      # read-only plan, printed
$env:QT_QPA_FONTDIR="C:/Windows/Fonts"; python scripts/screenshots.py "M:\Media" shots
```

`screenshots.py` renders every page in both themes offscreen and never writes to the
library. Without `QT_QPA_FONTDIR` the offscreen platform has no fonts and draws boxes.

## How it fits together

`scanner -> parser -> matching (matcher for TMDB, tvdb for anime) -> planner -> (review in
the UI) -> executor -> journal`. `matching.Resolver` puts remembered decisions on top and is
used by both the window and the CLI.
Only `executor.py` writes to the library, and every filesystem call goes through `fsops.py`
(the `\\?\` long-path prefix, case-only renames). Everything above the executor is pure, so
planning against the real library is safe. Runs are journalled as JSONL in
`%LOCALAPPDATA%\Endslate\runs\` and can be undone.

App data lives in `%LOCALAPPDATA%\Endslate\`: `config.json` (TMDB, TheTVDB and Jellyfin
keys: never print or commit them), `decisions.json`, `metadata-cache.sqlite`, `runs\`,
`endslate.log`.

## Rules the code keeps

- Never overwrite, never delete (junk goes to `<root>\_Quarantine\<run>\`), never write
  outside the library root, never open a video for writing. Tests assert these
- `Downloads\` is scanned on demand with the rest of the library. Recognized media can
  move out, but unrecognized files and the staging folder remain in place
- Matching never guesses: below the fuzzy threshold, or with no clear winner, an item
  goes to Needs you. Changes to `matcher._score` / `_decide` must keep
  `test_a_title_with_two_real_films_asks_rather_than_guesses` passing
- `tests/fixtures/names.py` is the parser spec. `tests/test_regressions.py` holds one
  test per bug found on the real library. Add to both when fixing something
- `tests/fixtures/tmdb/responses.json` is real TMDB data recorded by
  `scripts/record_tmdb.py`; `test_tmdb_live_fixtures.py` replays it.
  `tests/fixtures/tvdb/responses.json` is the same for TheTVDB (`scripts/record_tvdb.py`,
  replayed by `tests/test_tvdb.py`)
- Anime: `Item.is_anime` means "match with TheTVDB"; `Item.destination` (movies, shows,
  anime) is where it lands, decided in `planner._collect_items` from the top-level folder.
  `ParsedName.absolute` is a fansub episode count; `tvdb.TvdbMatcher.place` turns it into a
  season and episode and refuses when both readings fit. The anime preference
  (`ANIME_BONUS`, `_narrow`) only ever breaks ties, and the Mob Psycho 100 test must keep
  asking
- Tests compare paths with `.as_posix()`; `str(Path)` gives backslashes on Windows

## Design system (endslate/ui/theme.py, endslate/ui/neu.py)

Soft UI (neumorphism) on cool clay, from the owner's `Theme.md`: light `#E0E5EC`, dark a
cool graphite. Surfaces are the canvas colour and are told apart only by a light shadow
top-left and a dark one bottom-right. Cards are raised, inputs are wells, a pressed or
selected control is inset. Violet (`accent`) is the primary action, focus ring and switch;
otherwise colour is file state only: teal planned, amber needs you, rose duplicate, blue
(`blue` token) junk. The mark is the `Orb` (widgets.py). Type: DM Sans and Plus Jakarta Sans
from `assets/fonts` (OFL), loaded by `theme.load_fonts`; paths stay mono.

How the shadows work: `neu.style(widget, "raised" | "inset", ...)` registers a widget; its
host (nearest styled ancestor, `neu.surface()` container, scroll viewport or window) paints
the body in an event filter before the widget draws its text. Styled widgets are
transparent in QSS (`[neu="true"]`). Self-painting widgets (Switch, DialButton, IconWell,
Toast, the row delegate) call `neu.paint_raised` / `paint_inset` and must leave room inside
their own rect for the shadow. the `neuPressed` property / `isChecked()` sink a widget.

Gotchas:
- A plain holder widget between a styled widget and its host is looked through; mark a new
  page-level container with `neu.surface()` or its children's shadows are clipped
- Registry is keyed by the C++ pointer, not Python attributes: PySide re-wraps
  Qt-created widgets (viewports) and loses attributes
- Never style a container with a bare `QFrame { }` rule: QLabel is a QFrame. Select `#Name`
- The app-wide `QWidget { font-family }` rule beats `setFont`; put the family in the
  widget's own stylesheet too when it must differ
- Button icons are tinted per theme by `widgets.tint_button`, rerun in `restyle_tree`
- Screenshots: `scripts/screenshots.py` waits for the 300 ms state animations to settle

## Jellyfin (context from 2026-09-26)

The owner runs Jellyfin 10.11.6 as a Windows service (`C:\ProgramData\Jellyfin\Server\`),
libraries `M:\Media\Movies` and `M:\Media\Shows`, real-time monitoring on. After Endslate
runs, some films (Nerve, Thor - The Dark World, The Witch, The Invention of Lying) stayed
in Jellyfin under their old paths and failed to play ("No such file or directory"), even
after rescans and re-adding the library. The files are correctly named on disk.

Cause, from Jellyfin's own log: `BaseItemRepository.DeleteItem` fails with
`UNIQUE constraint failed: UserData.ItemId, UserData.UserId, UserData.CustomDataKey` when
it parks a removed item's watch history on the placeholder item
`00000000-0000-0000-0000-000000000001` and that key is already parked there. The failed
delete aborts the folder's scan, so the stale entry stays and the renamed file is never
added. The README section "Jellyfin still shows the old names" gives the user-side fix.
Endslate does not and should not touch Jellyfin's database. `jellyfin.py` reports entries
whose path no longer exists (`LibraryReport.stale`), shown on the Apply page.

The owner's Jellyfin API key was not set in Endslate's config at that time, so the
stale-path report has only been tested against the fake server in `tests/test_jellyfin.py`.

## Housekeeping

- Git: work on `master`; `main` is the PR base. `core.autocrlf=true`
- `error-logs/` holds Jellyfin FFmpeg logs the owner supplied for the issue above; it is
  not part of the app
