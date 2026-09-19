"""Filesystem calls that survive Windows.

Two things bite on Windows and nowhere else. Paths over 259 characters fail
unless they carry the \\\\?\\ extended-length prefix, and a rename that changes
only letter case is a no-op to a case-insensitive filesystem unless it goes via
a temporary name. Every filesystem call in the executor and the scanner goes
through here so both are handled once.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterator

WINDOWS = os.name == "nt"
PATH_LIMIT = 259
TEMP_SUFFIX = ".endslate-case-tmp"


def raw(path) -> str:
    """The form Windows accepts for long paths. A no-op everywhere else."""
    text = str(path)
    if not WINDOWS or text.startswith("\\\\?\\"):
        return text
    absolute = os.path.abspath(text)
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


def unraw(text: str) -> str:
    if text.startswith("\\\\?\\UNC\\"):
        return "\\\\" + text[8:]
    if text.startswith("\\\\?\\"):
        return text[4:]
    return text


def exists(path) -> bool:
    return os.path.exists(raw(path))


def is_dir(path) -> bool:
    return os.path.isdir(raw(path))


def size(path) -> int:
    return os.path.getsize(raw(path))


def listdir(path) -> list[str]:
    return os.listdir(raw(path))


def is_empty_dir(path) -> bool:
    try:
        return not os.listdir(raw(path))
    except OSError:
        return False


def mkdir(path) -> None:
    os.mkdir(raw(path))


def makedirs(path) -> None:
    os.makedirs(raw(path), exist_ok=True)


def rmdir(path) -> None:
    os.rmdir(raw(path))


def same_file(a, b) -> bool:
    try:
        return os.path.samefile(raw(a), raw(b))
    except OSError:
        return False


def is_case_only_rename(src, dst) -> bool:
    return str(src) != str(dst) and str(src).lower() == str(dst).lower()


def move(src, dst) -> None:
    """Move, going via a temporary name when only the letter case changes."""
    if is_case_only_rename(src, dst) and exists(dst):
        temporary = str(src) + TEMP_SUFFIX
        os.rename(raw(src), raw(temporary))
        try:
            os.rename(raw(temporary), raw(dst))
        except OSError:
            os.rename(raw(temporary), raw(src))
            raise
        return
    shutil.move(raw(src), raw(dst))


def actual_name(path) -> str:
    """The name as the filesystem spells it, which may differ in case."""
    parent = Path(path).parent
    wanted = Path(path).name
    try:
        for entry in os.listdir(raw(parent)):
            if entry.lower() == wanted.lower():
                return entry
    except OSError:
        pass
    return wanted


def walk(root) -> Iterator[tuple[Path, list[str], list[str]]]:
    """os.walk that copes with long paths and hands back ordinary Paths."""
    errors: list[str] = []
    for dirpath, dirnames, filenames in os.walk(raw(root), onerror=errors.append):
        yield Path(unraw(dirpath)), dirnames, filenames


def walk_with_errors(root, on_error) -> Iterator[tuple[Path, list[str], list[str]]]:
    for dirpath, dirnames, filenames in os.walk(raw(root), onerror=lambda e: on_error(str(e))):
        yield Path(unraw(dirpath)), dirnames, filenames


def too_long(path) -> bool:
    return WINDOWS and len(str(path)) > PATH_LIMIT
