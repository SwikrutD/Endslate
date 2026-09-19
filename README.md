# Endslate

Renames and reorganizes a movie and TV library into a layout Jellyfin reads without
guessing. Scan, look at every proposed change, approve, apply. Every run is journalled
and can be reversed.

Named after the clapperboard shot at the end of a take, used to label footage that was
not slated at the start.

```
Movies\Fight Club\Fight.Club.1999.REMASTERED.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv
   ->  Movies\Fight Club (1999)\Fight Club (1999).mkv

TV Shows\The 100\The.100.S01...\The.100.S01E04.Murphys.Law.1080p.AMZN.WEB-DL...mkv
   ->  Shows\The 100 (2014)\Season 01\The 100 (2014) S01E04 Murphy's Law.mkv
```

## What it will never do

- Overwrite an existing file. A collision stops that operation, it does not resolve itself
- Delete anything. Removal means a move into `_Quarantine`, except folders left empty
- Move an item it is not confident about. Those wait for you in the Needs you tab
- Write outside the library root
- Open a video file for writing. It reads names and sizes, nothing else

## Opening it

No terminal required. In the Endslate folder there are three files you can double-click:

| File | What it does |
| --- | --- |
| **Setup Endslate.cmd** | Run this once. Installs what Endslate needs and puts an icon on your Desktop and in the Start Menu. The icon opens the window with no console at all |
| **Endslate.cmd** | Opens the window. Installs anything missing first. Works whether or not you ran setup |
| **Endslate (show errors).cmd** | The same, but keeps the console open and prints everything. Use it when the normal launcher appears to do nothing |

All three need Python 3.10 or newer on PATH. If it is missing, the launcher says so and
tells you what to install. Nothing is ever installed without showing you.

If you would rather use a terminal:

```powershell
python -m pip install -r requirements.txt
python -m endslate gui
```

To build a standalone `Endslate.exe` that needs no Python at all:

```powershell
.\scripts\build.ps1
```

Settings, the metadata cache, the run journals and a crash log live in
`%LOCALAPPDATA%\Endslate\`, never inside the media library. When the window is opened
from the Desktop icon there is no console to print to, so any error is written to
`%LOCALAPPDATA%\Endslate\endslate.log` and shown in a dialog.

## First run

1. **Settings**: paste your TMDB API key (the v3 key from your TMDB account settings) and
   press Test. Without a key Endslate still works, but anything with no year in its
   filename lands in Needs you instead of resolving itself
2. **Library**: drop the folder that holds `Movies` and `TV Shows` onto the page, or
   browse to it. Pick a preset. Press Scan library
3. **Review**: six tiles across the top are both the counts and the filter. Planned is
   what will happen, Needs you is what needs a decision. Double-click any row to search
   TMDB, with posters, or type the title in by hand
4. **Apply**: the numbers, the safety contract, then the run
5. **History**: every run, with an Undo button

Stop Jellyfin before applying. Moving files while its library scan is running can leave
its database pointing at paths that no longer exist. Endslate checks whether anything is
listening on the Jellyfin port and warns you, but the check is a courtesy, not a guarantee.

## Getting around

| Key | Does |
| --- | --- |
| `Ctrl` `1` to `5` | Jump to Library, Review, Apply, History, Settings |
| `Ctrl` `R` or `F5` | Scan the library again |
| `Ctrl` `F` | Jump to the search field |
| `Space` | Include or exclude the selected rows |
| `Enter` | Resolve the selected title |
| `Ctrl` `A` | Tick everything the filter is showing |

Right-click any row to open its folder in Explorer, copy either path, or exclude it.

## Duplicates

When two files resolve to the same name, neither moves and both wait on the Duplicates
tab. Pick one and press **Keep this one**, or press **Keep the largest of each** to settle
every group at once. The copies you do not keep go to `_Quarantine` alongside the junk, so
nothing is deleted and the run is still reversible.

Two different cuts of the same film are not duplicates: Endslate tells them apart by
edition, part, resolution or source and names them `Housefull 5 (2025) - A.mkv` and
`- B.mkv`. It reads those markers back on the next scan, so a second run leaves them alone.
The theme follows Windows by default and can be pinned to dark or light in Settings.

## Presets

| Preset | Movie | Episode |
| --- | --- | --- |
| Jellyfin | `Movies\Title (Year)\Title (Year).mkv` | `Shows\Title (Year)\Season 01\Title (Year) S01E01 Name.mkv` |
| Plex | same | `Shows\Title (Year)\Season 01\Title (Year) - s01e01 - Name.mkv` |
| Flat | `Movies\Title (Year).mkv` | same as Jellyfin |
| Kodi | same as Jellyfin | `Shows\Title (Year)\Season 01\Title (Year) S01E01.mkv` |

Settings has an Advanced section where each preset is four editable templates with a live
preview. Tokens: `{title}` `{year}` `{year_paren}` `{season:02}` `{episode:02}`
`{episode_title}` `{episode_title_suffix}` `{episode_title_dash}` `{edition}`
`{edition_suffix}` `{part}` `{part_suffix}` `{resolution}` `{source}` `{tmdb_id}`
`{imdb_id}` `{lang}` `{ext}`. Save your edits under a new name and it joins the list.

## Subtitles

External subtitles are renamed to match their video with an ISO 639-1 suffix, which is
what Jellyfin expects: `Fight Club (1999).en.srt`. `forced` and `sdh` markers are kept,
since they decide which track auto-plays. With English-only on, other languages and
redundant duplicate tracks go to `_Quarantine`.

Pairing handles four layouts: same folder same stem, same folder different stem, a `Subs`
subfolder, and a sidecar season folder such as `Dark - season 1.en\`.

## Windows paths

Every filesystem call goes through `fsops.py`, which adds the `\\?\` extended-length
prefix on Windows. Without it a source path over 259 characters fails to move and the
file is silently left behind. A rename that changes only letter case goes via a
temporary name, since a case-insensitive filesystem treats it as a no-op otherwise.

After a run, every move is verified: if a file is not at its target and nothing raised,
it is reported as a problem rather than passing quietly. Problems are listed in the Apply
log and written to `<run id>-problems.txt` beside the journal.

## Junk

Swept to `M:\Media\_Quarantine\<run timestamp>\` with the original relative path kept
underneath. `_Quarantine` is excluded from every scan.

macOS `._` resource forks and `.DS_Store`, `Thumbs.db` and `desktop.ini`, release-site
adverts (`www.YTS.MX.jpg`, `YIFYStatus.com.txt` and friends), web assets, folders holding
no media at all, and video files under 150 MB with `sample` in the name.

`poster.jpg`, `folder.jpg`, `fanart.jpg`, `banner.jpg` and `logo.png` are artwork, not
junk, and are kept and renamed alongside their video.

## Command line

The GUI is the main interface. The CLI is there for checking things quickly.

```powershell
python -m endslate plan  "M:\Media"                 # print the whole plan
python -m endslate plan  "M:\Media" --bucket needs_you
python -m endslate plan  "M:\Media" --offline --preset Plex
python -m endslate apply "M:\Media" --yes
python -m endslate runs
python -m endslate undo                             # most recent run
python -m endslate undo 2026-09-18_190930
```

## How it fits together

```
scanner  ->  parser  ->  matcher  ->  planner  ->  review  ->  executor  ->  journal
  read      guess       confirm       targets      approve      move        undo
```

Only `executor` writes. Everything above it is pure, which is why the plan can be built
against the real library without risk.

| Module | Job |
| --- | --- |
| `scanner.py` | Walk the tree, classify every file |
| `parser.py` | Messy name to a guess: title, year, season, episode, language, edition |
| `matcher.py` | Confirm the guess against TMDB, score it, offer candidates |
| `planner.py` | Render the preset into target paths, find collisions and duplicates |
| `presets.py` | The four presets and the template renderer |
| `subtitles.py` | Pair subtitles to videos, detect language, name the result |
| `junk.py` | Decide what is debris. Conservative by design |
| `executor.py` | Preflight, move, sweep, undo. The only writer |
| `journal.py` | Append-only JSONL record of every operation |
| `sanitize.py` | Make any title legal on Windows without mangling it |
| `fsops.py` | Filesystem calls that cope with long paths and case-only renames |
| `ui/theme.py` | The design system: colour, type and spacing tokens, and the stylesheet |
| `ui/icons.py` | A stroke icon set drawn as SVG and tinted to the theme |
| `ui/widgets.py` | Cards, tiles, pills, toggles, banners, empty states, toasts |
| `ui/delegate.py` | How one proposed change is drawn in the review list |
| `ui/pages/` | One module per screen |

## Tests

```powershell
python -m pip install pytest
python -m pytest
```

`tests/fixtures/names.py` is the parser's specification: real filenames with the parse each
must produce. Add a row whenever a name surprises you. `tests/test_regressions.py` holds one
test per bug found by running against the real library. The executor is tested against a
generated tree that reproduces every folder shape found in a real library, and the
apply-then-undo round trip asserts the tree comes back byte-identical.
