"""Command line entry point. The GUI is the main interface, this is for checking."""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

from endslate import presets as presets_mod
from endslate import report
from endslate.models import Bucket
from endslate.planner import Options, build_plan
from endslate.scanner import scan as scan_library


def _scan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("root")
    parser.add_argument("--preset", default="Jellyfin")
    parser.add_argument("--offline", action="store_true", help="skip the metadata lookup")
    parser.add_argument("--all-subtitles", action="store_true", help="keep non-English subtitles")
    parser.add_argument("--keep-folder-names", action="store_true", help="do not rename the top-level folders")
    parser.add_argument("--folder-per-movie", dest="folder_per_movie", action="store_true", default=None)
    parser.add_argument("--no-folder-per-movie", dest="folder_per_movie", action="store_false")


def _build(args, quiet: bool = False):
    root = Path(args.root).expanduser()
    if not root.is_dir():
        raise SystemExit(f"not a folder: {root}")
    scanned = scan_library(root)
    preset = presets_mod.builtin(args.preset)
    options = Options(
        english_only_subtitles=not args.all_subtitles,
        rename_top_level_folders=not args.keep_folder_names,
        folder_per_movie=None if args.folder_per_movie is None else args.folder_per_movie,
    )
    matcher = None
    if not args.offline:
        from endslate.config import load_config
        from endslate.matcher import TmdbMatcher
        from endslate.matching import Resolver
        from endslate.tvdb import TvdbMatcher

        config = load_config()
        tmdb = tvdb = None
        if config.tmdb_api_key:
            tmdb = TmdbMatcher(config.tmdb_api_key, language=config.metadata_language,
                               fuzzy_threshold=config.fuzzy_threshold)
        elif not quiet:
            print("no TMDB key configured, films and shows run offline", file=sys.stderr)
        if config.tvdb_api_key:
            tvdb = TvdbMatcher(config.tvdb_api_key, language=config.metadata_language,
                               fuzzy_threshold=config.fuzzy_threshold, pin=config.tvdb_pin)
        elif not quiet:
            print("no TheTVDB key configured, anime numbered from episode one waits for you",
                  file=sys.stderr)
        if tmdb is not None or tvdb is not None:
            # The same answers the window would give, remembered decisions included.
            matcher = Resolver(tmdb, tvdb=tvdb)
    return build_plan(scanned, preset, options, matcher=matcher)


def _plan(args) -> int:
    plan = _build(args)
    buckets = [Bucket(args.bucket)] if args.bucket else None
    print(report.render(plan, limit=args.limit, buckets=buckets))
    return 0


def _apply(args) -> int:
    from endslate import jellyfin
    from endslate.config import load_config
    from endslate.executor import execute, preflight

    config = load_config()
    if config.check_jellyfin:
        running, how = jellyfin.is_running(config.jellyfin_url)
        if running and not args.force:
            print(f"Jellyfin looks like it is running ({how}).", file=sys.stderr)
            print("Stop the server first, or pass --force.", file=sys.stderr)
            return 3

    plan = _build(args)
    problems = preflight(plan)
    if problems:
        print("Preflight failed, nothing was moved:", file=sys.stderr)
        for problem in problems[:40]:
            print(f"  {problem.path}: {problem.message}", file=sys.stderr)
        return 4

    counts = plan.counts()
    print(report.summary(plan))
    if not args.yes:
        answer = input(f"Apply {len(plan.selected_operations())} operations? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("nothing done")
            return 0

    run_id = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    result = execute(plan, run_id)
    print(result.summary())
    if result.journal_path:
        print(f"journal: {result.journal_path}")
    if result.failures:
        print(f"\n{len(result.failures)} files did not move:", file=sys.stderr)
        for failure in result.failures:
            print(f"  ! {failure.path}: {failure.message}", file=sys.stderr)
        if result.report_path:
            print(f"written to {result.report_path}", file=sys.stderr)
    return 0 if result.ok else 5


def _runs(args) -> int:
    from endslate.journal import list_runs

    runs = list_runs()
    if not runs:
        print("no runs recorded yet")
        return 0
    for info in runs:
        print(f"{info.run_id}  {info.label}  {info.root}")
    return 0


def _undo(args) -> int:
    from endslate.executor import undo as undo_run
    from endslate.journal import list_runs, mark_reverted

    runs = list_runs()
    if not runs:
        print("no runs to undo", file=sys.stderr)
        return 2
    if args.run_id:
        chosen = next((r for r in runs if r.run_id == args.run_id), None)
        if chosen is None:
            print(f"no run called {args.run_id}", file=sys.stderr)
            return 2
    else:
        # The newest run that is still standing. Picking the newest outright
        # replayed an already reverted run, which reported every file missing.
        chosen = next((r for r in runs if not r.reverted), None)
        if chosen is None:
            print("every recorded run has already been undone", file=sys.stderr)
            return 2
    if chosen.reverted:
        print(f"{chosen.run_id} has already been undone", file=sys.stderr)
        return 2
    result = undo_run(chosen.path)
    mark_reverted(chosen.path)
    print(f"restored {result.moved} files, removed {result.folders_removed} folders")
    for failure in result.failures:
        print(f"  ! {failure.path}: {failure.message}", file=sys.stderr)
    return 0 if result.ok else 5


def _alert(title: str, message: str) -> None:
    """Say something visible even when there is no console to print to."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
        return
    except Exception:
        pass
    print(f"{title}: {message}", file=sys.stderr)


def _gui(args) -> int:
    try:
        from endslate.ui.app import run_app
    except ImportError as exc:
        _alert(
            "Endslate cannot open",
            "The window toolkit is missing or broken.\n\n"
            f"{exc}\n\n"
            "Run \"Setup Endslate.cmd\" in the Endslate folder to reinstall it.",
        )
        return 1
    return run_app()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="endslate", description="Rename and reorganize a media library")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="scan a library and print what would change")
    _scan_args(p)
    p.add_argument("--limit", type=int, default=0, help="rows per section, 0 for all")
    p.add_argument("--bucket", choices=[b.value for b in Bucket])
    p.set_defaults(func=_plan)

    a = sub.add_parser("apply", help="scan, then actually move the files")
    _scan_args(a)
    a.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    a.add_argument("--force", action="store_true", help="apply even if Jellyfin looks like it is running")
    a.set_defaults(func=_apply)

    r = sub.add_parser("runs", help="list past runs")
    r.set_defaults(func=_runs)

    u = sub.add_parser("undo", help="reverse a run")
    u.add_argument("run_id", nargs="?")
    u.set_defaults(func=_undo)

    g = sub.add_parser("gui", help="open the window")
    g.set_defaults(func=_gui)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
