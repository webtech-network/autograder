"""Each selected web document is parsed once per grading and shared read-only (PRF-04).

The tests count real ``BeautifulSoup`` constructions while grading through the
public pipeline, so they observe what every evaluator actually does.
"""
import gc
import threading
import tracemalloc
from concurrent.futures import ThreadPoolExecutor

import bs4
import pytest

from autograder import Submission, SubmissionFile, build_pipeline
from autograder.models.language import Language
from autograder.template_library.web_dev.documents import parsed_html
from tests.builtin_evaluator_cases import DEFINITION, SUBMISSIONS, WEBDEV_TESTS, leaves

# Every web_dev evaluator that reads HTML structure, CSS included.
HTML_READERS = {"has_class", "check_bootstrap_linked", "check_internal_links", "has_tag", "has_forbidden_tag",
                "has_attribute", "check_no_inline_styles", "uses_semantic_tags", "check_css_linked",
                "check_headings_sequential", "check_all_images_have_alt", "check_html_direct_children",
                "check_tag_not_inside", "check_internal_links_to_article", "check_head_details",
                "check_attribute_and_value", "check_bootstrap_usage", "link_points_to_page_with_query_param",
                "count_unused_css_classes"}


def _definition(tests):
    return {"schema_version": "1.0", "templates": ["webdev"], "languages": ["node"],
            "criteria": {"base": {"weight": 100, "tests": tests}}}


def _grade(definition, files):
    submission = Submission("student", "student", "assignment",
                            {name: SubmissionFile(name, content) for name, content in files.items()},
                            language=Language.NODE)
    outcome = build_pipeline(definition=definition).run(submission).outcome.model_dump(mode="json")
    assert outcome["status"] == "completed", outcome["error"]
    return outcome


@pytest.fixture
def parses(monkeypatch):
    """Record every BeautifulSoup tree built, with its serialization at construction."""
    built = []
    original = bs4.BeautifulSoup.__init__

    def counting_init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        built.append((args[0] if args else kwargs.get("markup", ""), self, self.decode()))

    monkeypatch.setattr(bs4.BeautifulSoup, "__init__", counting_init)
    return built


def test_rubric_covers_every_html_reading_evaluator():
    assert HTML_READERS <= {test["type"] for test in WEBDEV_TESTS}


@pytest.mark.parametrize("variant", sorted(SUBMISSIONS))
def test_each_document_is_parsed_once_per_grading(parses, variant):
    files = SUBMISSIONS[variant]
    rubric = WEBDEV_TESTS + [
        {"id": f"tag-{index}", "type": "has_tag", "name": "Has tag", "parameters": {"tag": "p", "required_count": index}}
        for index in range(30)]

    _grade(_definition(rubric), files)
    assert [markup for markup, _, _ in parses] == [files["index.html"]]

    # A second grading of identical bytes is a new grading: it parses again,
    # because nothing is cached across submissions.
    _grade(_definition(rubric), files)
    assert [markup for markup, _, _ in parses] == [files["index.html"]] * 2


@pytest.mark.parametrize("variant", sorted(SUBMISSIONS))
def test_no_criterion_mutates_the_shared_tree(parses, variant):
    _grade(DEFINITION, SUBMISSIONS[variant])
    assert parses
    for _, soup, serialized in parses:
        assert soup.decode() == serialized


@pytest.mark.parametrize("variant", sorted(SUBMISSIONS))
def test_criteria_cannot_observe_each_other(variant):
    """Each criterion graded alone on a private parse equals its shared-parse result, in either order."""
    files = SUBMISSIONS[variant]
    shared = leaves(_grade(_definition(WEBDEV_TESTS), files)["tree"])
    assert leaves(_grade(_definition(WEBDEV_TESTS[::-1]), files)["tree"]) == shared
    for test in WEBDEV_TESTS:
        alone = leaves(_grade(_definition([test]), files)["tree"])
        assert alone == {test["id"]: shared[test["id"]]}


def _page(sections: int) -> dict[str, str]:
    body = "".join(f'<section id="s{index}" class="card"><h2>{index}</h2></section>' for index in range(sections))
    return {"index.html": f"<html><head><title>{sections}</title></head><body><main>{body}</main></body></html>"}


def test_parallel_gradings_of_different_documents_never_cross_contaminate():
    workers, rounds = 8, 25
    definition = _definition([
        {"id": "sections", "type": "has_tag", "name": "Sections", "parameters": {"tag": "section", "required_count": 100}},
        {"id": "cards", "type": "has_class", "name": "Cards", "parameters": {"class_names": ["card"], "required_count": 100}},
        {"id": "title", "type": "check_head_details", "name": "Title", "parameters": {"detail_tag": "title"}},
    ])
    expected = {sections: leaves(_grade(definition, _page(sections))["tree"]) for sections in range(1, workers + 1)}
    assert len({repr(result) for result in expected.values()}) == workers
    start = threading.Barrier(workers)

    def grade_repeatedly(sections):
        start.wait()
        return [leaves(_grade(definition, _page(sections))["tree"]) for _ in range(rounds)]

    with ThreadPoolExecutor(workers) as pool:
        observed = dict(zip(expected, pool.map(grade_repeatedly, expected)))
    for sections, results in observed.items():
        assert results == [expected[sections]] * rounds


def test_memory_stays_flat_across_a_thousand_distinct_gradings():
    pipeline = build_pipeline(definition=_definition([
        {"id": f"tag-{index}", "type": "has_tag", "name": "Has tag", "parameters": {"tag": "section", "required_count": 3}}
        for index in range(5)]))

    def grade(index):
        page = _page(20)["index.html"].replace("<title>20", f"<title>{index}")
        submission = Submission(str(index), index, "assignment", {"index.html": SubmissionFile("index.html", page)},
                                language=Language.NODE)
        assert pipeline.run(submission).outcome.status == "completed"

    tracemalloc.start()
    try:
        for index in range(100):
            grade(index)
        gc.collect()
        warmed, _ = tracemalloc.get_traced_memory()
        for index in range(100, 1000):
            grade(index)
        gc.collect()
        final, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    # Nothing survives a grading: no parsed tree is left alive anywhere.
    assert not [obj for obj in gc.get_objects() if isinstance(obj, bs4.BeautifulSoup)]
    # One tree of this page is ~46 KB, so retaining the 900 later ones would add
    # ~40 MB. The margin absorbs one-off interpreter table resizes (~2 MB).
    assert final - warmed < 8_000_000


def test_a_reused_file_object_with_new_content_is_parsed_again():
    file = SubmissionFile("index.html", "<p>first</p>")
    first = parsed_html(file)
    assert parsed_html(file) is first
    file.content = "<div>second</div>"
    assert parsed_html(file).find("div") is not None and parsed_html(file).find("p") is None
