"""One HTML parse per selected document per grading, shared read-only.

Every criterion of a grading receives the same ``SubmissionFile`` objects, so
the parsed tree is memoized on the file's identity and lives exactly as long as
that object: hosts build a ``Submission`` per grading, so nothing survives the
grading. There is deliberately no content-keyed or process-wide cache: identical
bytes from another submission are parsed again, and an unreferenced tree is
released as soon as its file is.

The tree is shared by every web_dev criterion over that file, so evaluators must
only read it (``find``, ``find_all``, ``select``, attribute access). Mutating
calls such as ``decompose``, ``extract``, ``replace_with`` or attribute
assignment would leak into later criteria; tests assert that grading leaves the
tree unchanged.
"""
import weakref

from bs4 import BeautifulSoup

from autograder.models.dataclass.submission import SubmissionFile

# id(file) -> (weak reference to file, content parsed, tree). An entry is removed
# when its file is finalized, before the id can be reused. Single dict reads,
# writes and pops are atomic; concurrent gradings use distinct file objects.
_parsed: dict[int, tuple[weakref.ref, str, BeautifulSoup]] = {}


def parsed_html(file: SubmissionFile) -> BeautifulSoup:
    """Return the shared, read-only parse of ``file`` for the current grading."""
    key, content = id(file), file.content
    entry = _parsed.get(key)
    if entry is not None and entry[0]() is file:
        # Identity, not equality: a host reusing a file object with new content
        # never reads a stale tree.
        if entry[1] is content:
            return entry[2]
    else:
        weakref.finalize(file, _parsed.pop, key, None).atexit = False
    soup = BeautifulSoup(content, "html.parser")
    _parsed[key] = (weakref.ref(file), content, soup)
    return soup
