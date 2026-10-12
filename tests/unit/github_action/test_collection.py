"""Checkout collection follows the shared source-input limits without rewriting text."""
from unittest.mock import patch

import pytest

from github_action import main
from submission_contract import MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_FILE_BYTES


def test_collection_preserves_utf8_and_line_endings(tmp_path):
    data = "# café\r\nprint('✓')\r\n".encode("utf-8")
    (tmp_path / "main.py").write_bytes(data)
    assert main.collect_files(tmp_path)["main.py"].content.encode("utf-8") == data


@pytest.mark.parametrize("data", [b"\xff", b"abc\x00def"])
def test_collection_rejects_unsupported_text(tmp_path, data):
    (tmp_path / "main.py").write_bytes(data)
    with pytest.raises(ValueError):
        main.collect_files(tmp_path)


def test_collection_rejects_empty_submission(tmp_path):
    with pytest.raises(ValueError, match="no submission files"):
        main.collect_files(tmp_path)


def test_collection_file_count_boundary(tmp_path):
    for index in range(MAX_FILES):
        (tmp_path / f"file-{index:03}.py").touch()
    assert len(main.collect_files(tmp_path)) == MAX_FILES
    (tmp_path / "extra.py").touch()
    with pytest.raises(ValueError, match="at most"):
        main.collect_files(tmp_path)


def test_collection_file_size_boundary_counts_utf8_bytes(tmp_path):
    source = tmp_path / "main.py"
    source.write_bytes(b"a" * MAX_FILE_BYTES)
    assert len(main.collect_files(tmp_path)["main.py"].content) == MAX_FILE_BYTES
    source.write_bytes(b"a" * (MAX_FILE_BYTES - 1) + "é".encode())
    with pytest.raises(ValueError, match="exceeds"):
        main.collect_files(tmp_path)


def test_collection_total_size_boundary(tmp_path):
    for index in range(MAX_TOTAL_FILE_BYTES // MAX_FILE_BYTES):
        (tmp_path / f"file-{index}.py").write_bytes(b"a" * MAX_FILE_BYTES)
    remainder = MAX_TOTAL_FILE_BYTES % MAX_FILE_BYTES
    (tmp_path / "last.py").write_bytes(b"a" * remainder)
    main.collect_files(tmp_path)
    (tmp_path / "last.py").write_bytes(b"a" * (remainder + 1))
    with pytest.raises(ValueError, match="total file bytes"):
        main.collect_files(tmp_path)


@pytest.mark.parametrize("kind", ["file", "directory", "root"])
def test_collection_rejects_symlinks(tmp_path, kind):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("secret")
    if kind == "file":
        (source / "alias.py").symlink_to(outside / "secret.py")
    elif kind == "directory":
        (source / "alias").symlink_to(outside, target_is_directory=True)
    else:
        source = tmp_path / "alias"
        source.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        main.collect_files(source)


def test_collection_fails_on_unreadable_directory(tmp_path):
    def unreadable_walk(root, *, onerror):
        onerror(PermissionError("not readable"))
        return iter(())

    with patch.object(main.os, "walk", side_effect=unreadable_walk):
        with pytest.raises(ValueError, match="unreadable directory"):
            main.collect_files(tmp_path)


def test_collection_fails_on_unreadable_file(tmp_path):
    (tmp_path / "main.py").touch()
    with patch.object(main.Path, "open", side_effect=PermissionError("not readable")):
        with pytest.raises(ValueError, match="not readable UTF-8"):
            main.collect_files(tmp_path)


def test_collection_bounds_read_before_allocating_large_content(tmp_path):
    source = tmp_path / "large.py"
    with source.open("wb") as handle:
        handle.truncate(100 * MAX_FILE_BYTES)
    with patch.object(main.Path, "open", wraps=source.open) as opened:
        with pytest.raises(ValueError, match="exceeds"):
            main.collect_files(tmp_path)
    assert opened.call_args.args == ("rb",)
