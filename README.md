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

## Install

Needs Python 3.10 or newer.

```powershell
git clone <this repo> ; cd Endslate
python -m pip install -r requirements.txt
python -m endslate gui
```

To build a standalone `Endslate.exe`:

```powershell
.\scripts\build.ps1
```

Settings, the metadata cache and the run journals live in `%LOCALAPPDATA%\Endslate\`,
never inside the media library.

## First run

1. **Settings**: paste your TMDB API key (the v3 key from your TMDB account settings) and
   press Test. Without a key the tool still works, but anything with no year in its
   filename lands in Needs you instead of resolving itself
2. **Library**: point it at the folder that holds `Movies` and `TV Shows`, pick a preset,
   press Scan
3. **Review**: six tabs. Planned is what will happen, Needs you is what needs a decision.
   Double-click any Needs you row to search TMDB or type the title in by hand
4. **Apply**: confirms the counts, then moves the files
5. **History**: every run, with an Undo button

Stop Jellyfin before applying. Moving files while its library scan is running can leave
its database pointing at paths that no longer exist. Endslate checks whether anything is
listening on the Jellyfin port and warns you, but the check is a courtesy, not a guarantee.

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
| `ui/` | PySide6 window. Thin, all logic lives below it |

## Tests

```powershell
python -m pip install pytest
python -m pytest
```

`tests/fixtures/names.py` is the parser's specification: real filenames with the parse each
must produce. Add a row whenever a name surprises you. The executor is tested against a
generated tree that reproduces every folder shape found in a real library, and the
apply-then-undo round trip asserts the tree comes back byte-identical.
