# Endslate: context for Claude

Endslate renames and reorganises a movie/TV library (the owner's is `M:\Media`, with
`Movies\` and `Shows\` under it) into the layout Jellyfin expects. It is a Python 3.10+
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

`scanner -> parser -> matcher -> planner -> (review in the UI) -> executor -> journal`.
Only `executor.py` writes to the library, and every filesystem call goes through `fsops.py`
(the `\\?\` long-path prefix, case-only renames). Everything above the executor is pure, so
planning against the real library is safe. Runs are journalled as JSONL in
`%LOCALAPPDATA%\Endslate\runs\` and can be undone.

App data lives in `%LOCALAPPDATA%\Endslate\`: `config.json` (TMDB and Jellyfin keys:
never print or commit them), `decisions.json`, `metadata-cache.sqlite`, `runs\`,
`endslate.log`.

## Rules the code keeps

- Never overwrite, never delete (junk goes to `<root>\_Quarantine\<run>\`), never write
  outside the library root, never open a video for writing. Tests assert these
- Matching never guesses: below the fuzzy threshold, or with no clear winner, an item
  goes to Needs you. Changes to `matcher._score` / `_decide` must keep
  `test_a_title_with_two_real_films_asks_rather_than_guesses` passing
- `tests/fixtures/names.py` is the parser spec. `tests/test_regressions.py` holds one
  test per bug found on the real library. Add to both when fixing something
- `tests/fixtures/tmdb/responses.json` is real TMDB data recorded by
  `scripts/record_tmdb.py`; `test_tmdb_live_fixtures.py` replays it
- Tests compare paths with `.as_posix()`; `str(Path)` gives backslashes on Windows

## Design system (endslate/ui/theme.py)

"Chalk on slate". Warm graphite (dark) or warm paper (light) neutrals; the accent is chalk
in dark and ink in light, so the primary button is near-white or near-black. Colour is
reserved for file state only: green planned, amber needs you, red duplicate, violet
(`blue` token) junk. The one ornament is the painted `Clapstick` stripe (widgets.py) at the
top of the rail and over the commit card on Apply. Counts and paths use the mono face
(`theme.mono_font`, with fallbacks: Cascadia Mono is not installed on the owner's machine).

Gotchas:
- Never style a container with a bare `QFrame { }` rule: QLabel is a QFrame and gets the
  border too. Give the container an object name and select `#Name`
- The app-wide `QWidget { font-family }` rule beats `setFont`; put the family in the
  widget's own stylesheet too when it must differ
- Button icons are tinted per theme by `widgets.tint_button`, rerun in `restyle_tree`

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
