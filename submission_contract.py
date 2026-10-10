"""Shared acceptance policy for the HTTP and Actions hosts, outside grading core."""

import json
import posixpath
import re
import unicodedata

MAX_FILES = 100
MAX_PATH_BYTES = 255
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_FILE_BYTES = 5 * 1024 * 1024
MAX_METADATA_BYTES = 16 * 1024
MAX_TOTAL_METADATA_BYTES = 64 * 1024
MAX_REQUEST_BYTES = 32 * 1024 * 1024


def validate_filename(value: str) -> str:
    """Reject aliases instead of silently renaming caller-owned paths."""
    if (
        not value
        or posixpath.normpath(value) != value
        or value in (".", "..")
        or value.startswith(("/", "../"))
        or "\\" in value
        or re.match(r"^[A-Za-z]:", value)
        or any(unicodedata.category(char) in ("Cc", "Cs") for char in value)
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError("filename must be a canonical relative POSIX path in Unicode NFC")
    if len(value.encode("utf-8")) > MAX_PATH_BYTES:
        raise ValueError("filename exceeds 255 UTF-8 bytes")
    return value


def validate_content(value: str) -> str:
    """Accept source text exactly; binary and invalid Unicode are unsupported."""
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise ValueError("file content must be valid UTF-8 text") from exc
    if "\x00" in value:
        raise ValueError("binary file content containing NUL is unsupported")
    if size > MAX_FILE_BYTES:
        raise ValueError("file content exceeds 1 MiB")
    return value


def metadata_bytes(value: dict | None) -> int:
    """Measure finite JSON, with one fixed serialization for all host limits."""
    if value is None:
        return 0
    try:
        return len(json.dumps(value, ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("metadata must contain finite UTF-8 JSON values") from exc


def validate_metadata(value: dict | None) -> dict | None:
    """Bound each opaque metadata object before persistence or evaluation."""
    if metadata_bytes(value) > MAX_METADATA_BYTES:
        raise ValueError("metadata exceeds 16 KiB")
    return value


def validate_filenames(names: list[str]) -> None:
    """Reject duplicate files and file/directory collisions before staging."""
    known = set(names)
    if len(known) != len(names):
        raise ValueError("submission filenames must be unique")
    for name in names:
        parts = name.split("/")
        if any("/".join(parts[:index]) in known for index in range(1, len(parts))):
            raise ValueError("submission filenames contain a file/directory collision")
