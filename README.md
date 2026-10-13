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

Downloads\[SubsPlease] Sousou no Frieren - 12 (1080p) [A1B2C3D4].mkv
   ->  Anime\Frieren - Beyond Journey's End (2023) [tvdbid-424536]\Season 01\Frieren - Beyond Journey's End (2023) S01E12 A Real Hero.mkv
```

For mixed incoming media, create `Downloads` alongside `Movies` and `Shows`. Each
approved run scans that folder, uses season and episode markers to separate shows from
movies, confirms titles with TMDB, and moves recognized files to their normal
destinations. Files that cannot be classified stay in `Downloads`, and the folder
itself is preserved for the next run.

## Anime

An `Anime` folder beside `Movies` and `Shows` is a third library. Anime is matched against
TheTVDB rather than TMDB, because fansub releases count episodes from the start of the
show (`[Erai-raws] One Piece - 1085`) and TheTVDB is the source that knows which season
episode 1085 falls in. Its folder carries the show's TheTVDB id, `[tvdbid-81797]`, which
Jellyfin reads directly, so it never mistakes an anime for its live-action remake.

- In `Anime`, everything with an episode number is anime. A film there goes to `Movies`
- In `Downloads`, a release named `[Group] Title - 12` is anime and goes to `Anime`
- In `Shows`, a file counted from episode one is placed with TheTVDB but stays in `Shows`
- The romaji, English and Japanese names all count: `Shingeki no Kyojin` matches
  `Attack on Titan`. When two shows still share a name, the one whose original language is
  Japanese, Chinese or Korean is preferred, since a fansub release is anime
- Anything still ambiguous waits in Needs you. Mob Psycho 100 is both a 2016 anime and a
  2018 live-action drama, both Japanese, so Endslate asks
- An episode TheTVDB does not list yet, or a `Season 2` folder holding `- 05` that could be
  either the fifth of season two or the fifth overall, waits rather than guessing
- Without a TheTVDB key, anime named `S01E05` still resolves through TMDB; anything counted
  from episode one waits in Needs you with a note saying why

## What it will never do

- Overwrite an existing file. A collision stops that operation, it does not resolve itself
- Delete anything. Removal means a move into `_Quarantine`, except folders left empty
- Move an item it is not confident about. Those wait for you in the Needs you tab
- Remove or quarantine unrecognized files in `Downloads`
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
   filename lands in Needs you instead of resolving itself. For anime, paste a TheTVDB v4
   key as well (thetvdb.com, Dashboard, API Keys); a user-supported key also needs your
   subscriber PIN
2. **Library**: drop the folder that holds `Movies` and `TV Shows` onto the page, or
   browse to it. You may also place mixed movies and episodes in a `Downloads` folder
   alongside them; each run classifies recognized files and moves them to the configured
   destination. Unrecognized download contents stay in `Downloads`. Pick a preset.
   Press Scan library
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
| `Ctrl` `1` to `6` | Jump to Library, Review, Apply, Health, History, Settings |
| `Ctrl` `R` or `F5` | Scan the library again |
| `Ctrl` `F` | Jump to the search field |
| `Space` | Include or exclude the selected rows |
| `Enter` | Resolve the selected title |
| `Ctrl` `A` | Tick everything the filter is showing |

Right-click any row to open its folder in Explorer, copy either path, or exclude it.

The theme follows Windows by default and can be pinned to dark or light in Settings. Both
are soft UI on cool clay: every surface is moulded from one grey and told apart by light,
cards raised, inputs pressed in, and whatever you have selected stays pressed in. Violet
is the one primary action and the focus ring. Otherwise colour only marks a file's state:
teal will move, amber needs you, rose collides, blue goes to quarantine. The interface is
set in DM Sans and Plus Jakarta Sans, bundled in `assets\fonts` under the SIL Open Font
License.

## It remembers what you tell it

Every title you resolve by hand is written to `%LOCALAPPDATA%\Endslate\decisions.json`, twice: against the
file you made it on, and against the title you made it for. The second one is what
matters. It survives the file being renamed and it generalises, so
`INDIANA JONES RAIDERS LOST ARK` stays solved no matter what the file is called
afterwards, and a decision about a show covers every episode of it.

Needs you should therefore shrink to zero over a few sessions and stay there. Settings
shows how many titles are remembered and has a button to forget them all.

## Does Jellyfin agree?

Renaming is the means. Whether Jellyfin recognises everything is the result, and only
Jellyfin can answer that. Put a Jellyfin API key in Settings (Dashboard, API Keys) and
Endslate can:

- tell Jellyfin to rescan when a run finishes, automatically or on the button
- ask which movies and shows it still has no provider id for, and list them
- list every entry it still holds at a path that no longer exists on disk

The first list is the honest score for a run. If something renamed cleanly and Jellyfin
still cannot place it, the name is not the problem. The second list means Jellyfin has not
caught up with the rename at all, which is the next section. It is only checked when
Endslate can see the same paths Jellyfin does, so a server on another machine skips it.

### Jellyfin still shows the old names

The symptom: after a run and any number of rescans, Jellyfin still lists films under their
old folder names, playing one fails with `Error opening input: No such file or directory`,
and the renamed copies never appear. Deleting and re-adding the library does not help.

The cause, as seen in Jellyfin 10.11.6: when a scan finds that a file has gone, Jellyfin
deletes the old entry and parks its watch history on a placeholder item, so it can be
reattached if the film comes back. If the placeholder already holds history under the same
key, from an earlier delete of the same film, the database refuses:

```
UNIQUE constraint failed: UserData.ItemId, UserData.UserId, UserData.CustomDataKey
```

The delete fails, the rest of that folder's scan is abandoned with it, the stale entry
stays and the new one is never added. A film renamed in more than one run, or a watched
duplicate removed later, is exactly how a key gets reused. Search for the message in
`C:\ProgramData\Jellyfin\Server\log\log_<date>.log` to confirm it.

Endslate does not touch Jellyfin's database. What helps:

1. Check Jellyfin's release notes for a newer build that fixes it, and update
2. Otherwise stop Jellyfin, copy `C:\ProgramData\Jellyfin\Server\data\jellyfin.db`
   somewhere safe, and clear the parked history so the deletes can go through. This loses
   the watch history of items no longer in the library, and nothing else:
   ```sql
   DELETE FROM UserData WHERE ItemId = '00000000-0000-0000-0000-000000000001';
   ```
   Start Jellyfin and scan the library
3. Next time, stop Jellyfin or turn off real-time monitoring for the library while
   applying, so it sees one finished rename rather than every step of it

## Health

A correctly named library can still be missing the middle of a season. The Health screen
looks for what renaming cannot fix:

| Check | What it finds |
| --- | --- |
| Missing episodes | Gaps between the first and last episode of any season |
| Redundant archives | A large `.zip` or `.rar` sitting beside its own extracted contents |
| Duplicate copies | The same film twice, ranked by resolution then size, with the waste totalled |
| Broken files | Zero-byte videos, and anything too small to be a film or an episode |
| Orphan subtitles | Subtitle files that match no video |
| Empty folders | Left behind by something other than Endslate |

Nothing on this screen is renamed, quarantined or deleted. Each finding gives you the
path and a button to open its folder. **Check playability** runs `ffprobe` over whatever
looked broken, so you learn which files will actually not play.

## Duplicates

When two files resolve to the same name, neither moves and both wait on the Duplicates
tab. Pick one and press **Keep this one**, or press **Keep the largest of each** to settle
every group at once. The copies you do not keep go to `_Quarantine` alongside the junk, so
nothing is deleted and the run is still reversible.

Two different cuts of the same film are not duplicates: Endslate tells them apart by
edition, part, resolution or source and names them `Housefull 5 (2025) - A.mkv` and
`- B.mkv`. It reads those markers back on the next scan, so a second run leaves them alone.

## Presets

| Preset | Movie | Episode |
| --- | --- | --- |
| Jellyfin | `Movies\Title (Year)\Title (Year).mkv` | `Shows\Title (Year)\Season 01\Title (Year) S01E01 Name.mkv` |
| Plex | same | `Shows\Title (Year)\Season 01\Title (Year) - s01e01 - Name.mkv` |
| Flat | `Movies\Title (Year).mkv` | same as Jellyfin |
| Kodi | same as Jellyfin | `Shows\Title (Year)\Season 01\Title (Year) S01E01.mkv` |

Anime uses the same season folder and episode name under `Anime\`, with the show's id in
its folder: `Title (Year) [tvdbid-N]` for Jellyfin and Flat, `Title (Year) {tvdb-N}` for
Plex, and no id for Kodi. A file holding two episodes is named `S01E01-E02`.

Settings has an Advanced section where each preset's templates are editable with a live
preview. Tokens: `{title}` `{year}` `{year_paren}` `{season:02}` `{episode:02}`
`{episode_range}` `{episode_range_lower}` `{absolute}` `{episode_title}`
`{episode_title_suffix}` `{episode_title_dash}` `{edition}` `{edition_suffix}` `{part}`
`{part_suffix}` `{resolution}` `{source}` `{tmdb_id}` `{imdb_id}` `{tvdb_id}` `{tvdb_tag}`
`{tvdb_plex}` `{lang}` `{ext}`. Save your edits under a new name and it joins the list.
Presets saved before anime support pick up the default anime templates.

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

Swept to `<library root>\_Quarantine\<run timestamp>\` with the original relative path
kept underneath. `_Quarantine` is excluded from every scan.

macOS `._` resource forks and `.DS_Store`, `Thumbs.db` and `desktop.ini`, release-site
adverts (`www.YTS.MX.jpg`, `YIFYStatus.com.txt` and friends), web assets, folders holding
no media at all, and video files under 150 MB with `sample` in the name.

`poster.jpg`, `folder.jpg`, `fanart.jpg`, `banner.jpg` and `logo.png` are artwork, not
junk, and are kept and renamed alongside their video.

Large archives in `Downloads` are kept when no extracted video is present. When an
archive has extracted video files beside it, the videos are organized normally and the
archive is moved to that run's `_Quarantine` folder.

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
| `scanner.py` | Walk the tree, classify every file, find `Movies`, `Shows`, `Anime` and `Downloads` |
| `parser.py` | Messy name to a guess: title, year, season, episode or absolute number, release group |
| `matcher.py` | Confirm the guess against TMDB, score it, offer candidates |
| `tvdb.py` | The same for anime against TheTVDB, and absolute numbers to seasons |
| `matching.py` | Which provider answers for which item, with your remembered decisions on top |
| `planner.py` | Render the preset into target paths, find collisions and duplicates |
| `presets.py` | The four presets and the template renderer |
| `subtitles.py` | Pair subtitles to videos, detect language, name the result |
| `junk.py` | Decide what is debris. Conservative by design |
| `executor.py` | Preflight, move, sweep, undo. The only writer |
| `journal.py` | Append-only JSONL record of every operation |
| `sanitize.py` | Make any title legal on Windows without mangling it |
| `fsops.py` | Filesystem calls that cope with long paths and case-only renames |
| `cache.py` | SQLite cache of TMDB answers, so a rescan costs nothing |
| `langs.py` | Language names and codes to ISO 639-1 |
| `report.py` | The problems file written beside a run's journal |
| `jellyfin.py` | Ask Jellyfin to rescan, what it identified, and what it lost track of |
| `cli.py` | The command line |
| `ui/theme.py` | The design system: colour, type, depth and spacing tokens, and the stylesheet |
| `ui/neu.py` | The soft UI shadows: blurred sprites, nine-sliced, painted beneath each control |
| `ui/icons.py` | A stroke icon set drawn as SVG and tinted to the theme |
| `ui/widgets.py` | Cards, tiles, pills, toggles, banners, empty states, toasts |
| `ui/delegate.py` | How one proposed change is drawn in the review list |
| `ui/pages/` | One module per screen |
| `decisions.py` | What you resolved by hand, kept between runs |
| `health.py` | The checks a renamer cannot make |

## Tests

```powershell
python -m pip install pytest
python -m pytest
```

`tests/fixtures/names.py` is the parser's specification: real filenames with the parse each
must produce. Add a row whenever a name surprises you. `tests/test_regressions.py` holds one
test per bug found by running against the real library.

Matching is the part with the most riding on it, and until you record real answers it is
only tested against a stub written from assumptions, which is exactly how two films called
The Witch got through. Once, on a machine that can reach TMDB:

```powershell
python scripts/record_tmdb.py
```

That saves real search results and season listings to `tests/fixtures/tmdb/responses.json`
and `tests/test_tmdb_live_fixtures.py` replays them offline from then on.
`scripts/record_tvdb.py` does the same for TheTVDB into `tests/fixtures/tvdb/`, replayed by
`tests/test_tvdb.py`. Only response
bodies are stored, never the key, and the recorder refuses to write if it finds the key in
the payload anyway. Those tests skip themselves until the file exists.

The executor is tested against a generated tree that reproduces every folder shape found in a real library, and the
apply-then-undo round trip asserts the tree comes back byte-identical.
