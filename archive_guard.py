"""Validation of uploaded task archives before anything reads or extracts them.

Uploaded ZIPs are untrusted. Nothing in them is executed, imported or unpacked
into the project directory. This module decides whether an archive is safe to
inspect at all, and returns its members with normalised names so every later
reader works from the same vetted list.

Limits were set against the real benchmark rather than guessed. Measured over
all 70 merged terminal-bench task packages (2026-09-10):

    largest total uncompressed   124.1 MiB   atrx-vep-crispr
    largest single file           94.7 MiB   live-database-cutover
    most entries                   403
    worst compression ratio      310:1       uefi-bootkit, a 0.5 MiB firmware
                                             variable store that is mostly zeros

That last figure is why compression ratio is only judged above a size floor: a
flat ratio cap would have rejected a merged benchmark task. Tiny files routinely
compress far better than 100:1 and are harmless at that size; a decompression
bomb is only dangerous because of how large it becomes.

Each limit keeps at least 2x headroom over the largest real task. Raise a
constant here, with a note, if a legitimate task is ever rejected.
"""

from __future__ import annotations

import io
import re
import stat
import time
import zipfile
from dataclasses import dataclass

MiB = 1024 * 1024

# Compressed request body accepted by the review endpoint. The largest real
# task is ~124 MiB of already-compressed archives, so it barely shrinks.
MAX_UPLOAD_BYTES = 256 * MiB
# 12x the most entries in any real task (403).
MAX_ARCHIVE_ENTRIES = 5_000
# 4x the largest real task (124.1 MiB).
MAX_TOTAL_UNCOMPRESSED = 512 * MiB
# 2.7x the largest real file (94.7 MiB).
MAX_ENTRY_UNCOMPRESSED = 256 * MiB
# Ratio is only judged for entries at least this large. The worst real ratio
# (310:1) sits on a 0.5 MiB file, far below this floor.
RATIO_ENTRY_FLOOR = 16 * MiB
# Per-entry cap above the floor. Real large files are ~1:1 (already
# compressed); deflated text rarely exceeds 20:1. A bomb is typically >1000:1.
MAX_ENTRY_RATIO = 100
# Whole-archive check, catching a bomb split into many files that each stay
# under the entry floor.
RATIO_TOTAL_FLOOR = 64 * MiB
MAX_TOTAL_RATIO = 50
# Wall-clock budget for validating and inventorying one archive.
MAX_INSPECT_SECONDS = 30.0

SUPPORTED_METHODS = {
    zipfile.ZIP_STORED: "stored",
    zipfile.ZIP_DEFLATED: "deflate",
    zipfile.ZIP_BZIP2: "bzip2",
    zipfile.ZIP_LZMA: "lzma",
}

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_DRIVE = re.compile(r"^[A-Za-z]:")


class ArchiveRejected(ValueError):
    """The archive is unsafe or unreadable. The message is shown to the user."""


@dataclass(frozen=True)
class Member:
    info: zipfile.ZipInfo
    name: str  # normalised, forward-slash, no leading slash, no dot segments


def _ratio(info: zipfile.ZipInfo) -> float:
    # A zero compressed size with content is itself anomalous; max() keeps the
    # division defined and still yields a large ratio for it.
    return info.file_size / max(info.compress_size, 1)


def normalise_name(raw: str) -> str:
    """Return a safe relative path, or raise ArchiveRejected."""
    if _CONTROL.search(raw):
        raise ArchiveRejected(f"Archive entry name contains control characters: {raw!r}")
    name = raw.replace("\\", "/")
    if name.startswith("/"):
        raise ArchiveRejected(f"Archive entry uses an absolute path: {raw!r}")
    if _DRIVE.match(name):
        raise ArchiveRejected(f"Archive entry uses a drive-letter path: {raw!r}")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise ArchiveRejected(f"Archive entry escapes the archive root: {raw!r}")
    if not parts:
        raise ArchiveRejected(f"Archive entry has an empty name: {raw!r}")
    return "/".join(parts)


def validate_archive(zip_bytes: bytes, *, deadline: float | None = None) -> list[Member]:
    """Vet an uploaded archive and return its file members. Raises ArchiveRejected."""
    if len(zip_bytes) > MAX_UPLOAD_BYTES:
        raise ArchiveRejected(
            f"Upload is {len(zip_bytes) / MiB:.1f} MiB; the limit is {MAX_UPLOAD_BYTES // MiB} MiB.")
    deadline = deadline if deadline is not None else time.monotonic() + MAX_INSPECT_SECONDS
    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, ValueError, NotImplementedError) as exc:
        raise ArchiveRejected(f"Not a readable ZIP archive: {exc}") from exc

    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise ArchiveRejected(
                f"Archive has {len(infos)} entries; the limit is {MAX_ARCHIVE_ENTRIES}.")

        members: list[Member] = []
        seen: dict[str, str] = {}
        seen_folded: dict[str, str] = {}
        total = compressed = 0
        for info in infos:
            if time.monotonic() > deadline:
                raise ArchiveRejected("Archive inspection exceeded its time budget.")
            # orig_filename is the raw name from the archive. zipfile truncates
            # .filename at the first NUL, which would hide a hostile name.
            name = normalise_name(getattr(info, 'orig_filename', info.filename))
            if info.flag_bits & 0x1:
                raise ArchiveRejected(f"Archive entry is encrypted: {name}")
            if info.compress_type not in SUPPORTED_METHODS:
                raise ArchiveRejected(
                    f"Archive entry uses unsupported compression method {info.compress_type}: {name}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ArchiveRejected(f"Archive entry is a symbolic link: {name}")
            if info.is_dir():
                continue
            if name in seen:
                raise ArchiveRejected(f"Archive contains the same path twice: {name}")
            folded = name.casefold()
            if folded in seen_folded:
                raise ArchiveRejected(
                    f"Archive paths differ only by case and would collide on extraction: "
                    f"{seen_folded[folded]} and {name}")
            seen[name] = name
            seen_folded[folded] = name

            if info.file_size > MAX_ENTRY_UNCOMPRESSED:
                raise ArchiveRejected(
                    f"{name} is {info.file_size / MiB:.1f} MiB uncompressed; "
                    f"the per-file limit is {MAX_ENTRY_UNCOMPRESSED // MiB} MiB.")
            if info.file_size >= RATIO_ENTRY_FLOOR and _ratio(info) > MAX_ENTRY_RATIO:
                raise ArchiveRejected(
                    f"{name} expands {_ratio(info):.0f}:1 to {info.file_size / MiB:.1f} MiB, "
                    f"which looks like a decompression bomb.")
            total += info.file_size
            compressed += info.compress_size
            if total > MAX_TOTAL_UNCOMPRESSED:
                raise ArchiveRejected(
                    f"Archive expands beyond {MAX_TOTAL_UNCOMPRESSED // MiB} MiB uncompressed.")
            members.append(Member(info=info, name=name))

        if total >= RATIO_TOTAL_FLOOR and total / max(compressed, 1) > MAX_TOTAL_RATIO:
            raise ArchiveRejected(
                f"Archive expands {total / max(compressed, 1):.0f}:1 overall to "
                f"{total / MiB:.1f} MiB, which looks like a decompression bomb.")
    return members


def read_member(archive: zipfile.ZipFile, member: Member, limit: int) -> bytes:
    """Read at most `limit` bytes of a vetted member, surfacing corruption clearly."""
    try:
        with archive.open(member.info) as handle:
            data = handle.read(limit + 1)
    except (zipfile.BadZipFile, EOFError, OSError, RuntimeError, NotImplementedError) as exc:
        raise ArchiveRejected(f"{member.name} could not be read: {exc}") from exc
    except Exception as exc:  # zlib.error and friends from a corrupt stream
        raise ArchiveRejected(f"{member.name} is corrupt: {exc}") from exc
    if len(data) > limit:
        raise ArchiveRejected(f"{member.name} exceeds its declared size.")
    return data
