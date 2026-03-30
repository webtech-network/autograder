import pytest
from autograder.template_library.web_dev.template import WebDevTemplate
from autograder.template_library.web_dev.css_tests import CountUnusedCssClasses

def test_web_dev_template_load():
    template = WebDevTemplate()
    assert template.template_name == "Html Css Js Template"
    # Verify we have exactly 36 tests as expected
    assert len(template.tests) == 36

def test_all_registered_tests_are_valid():
    template = WebDevTemplate()
    expected_keys = [
        # HTML
        "has_class", "check_bootstrap_linked", "check_internal_links", "has_tag",
        "has_forbidden_tag", "has_attribute", "check_no_unclosed_tags",
        "check_no_inline_styles", "uses_semantic_tags", "check_css_linked",
        "check_headings_sequential", "check_all_images_have_alt",
        "check_html_direct_children", "check_tag_not_inside",
        "check_internal_links_to_article", "has_style", "check_head_details",
        "check_attribute_and_value", "check_bootstrap_usage",
        # CSS
        "css_uses_property", "count_over_usage", "check_id_selector_over_usage",
        "uses_relative_units", "check_media_queries", "check_flexbox_usage",
        "count_unused_css_classes",
        # JS
        "js_uses_feature", "uses_forbidden_method", "count_global_vars",
        "link_points_to_page_with_query_param", "js_uses_query_string_parsing",
        "js_has_json_array_with_id", "js_uses_dom_manipulation", "has_no_js_framework",
        # Structure
        "check_dir_exists", "check_project_structure"
    ]
    
    for key in expected_keys:
        test_func = template.get_test(key)
        assert test_func is not None
        assert hasattr(test_func, 'execute')

def test_count_unused_css_classes_normalization():
    template = WebDevTemplate()
    # Check new key exists and old is gone
    assert "count_unused_css_classes" in template.tests
    assert "Count Unused Css Classes" not in template.tests
    
    test_func = template.get_test("count_unused_css_classes")
    assert isinstance(test_func, CountUnusedCssClasses)
    assert test_func.name == "count_unused_css_classes"

def test_submodule_imports():
    from autograder.template_library.web_dev.html_tests import HasClass
    from autograder.template_library.web_dev.css_tests import CssUsesProperty
    from autograder.template_library.web_dev.js_tests import JsUsesFeature
    from autograder.template_library.web_dev.structure_tests import CheckDirExists
    
    assert HasClass().name == "has_class"
    assert CssUsesProperty().name == "css_uses_property"
    assert JsUsesFeature().name == "js_uses_feature"
    assert CheckDirExists().name == "check_dir_exists"
