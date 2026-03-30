from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.template_library.web_dev.html_tests import *
from autograder.template_library.web_dev.css_tests import *
from autograder.template_library.web_dev.js_tests import *
from autograder.template_library.web_dev.structure_tests import *

class WebDevTemplate(Template):
    """
    A template for web development assignments, containing a collection of
    all available test functions related to HTML, CSS, and JS.
    """
    @property
    def template_name(self):
        return "Html Css Js Template"
    @property
    def template_description(self):
        return "Um template abrangente para trabalhos de desenvolvimento web, incluindo testes para HTML, CSS e JavaScript."

    @property
    def requires_sandbox(self) -> bool:
        return False

    def __init__(self, clean=False):
        self.tests = {
            "has_class": HasClass(),
            "check_bootstrap_linked": CheckBootstrapLinked(),
            "check_internal_links": CheckInternalLinks(),
            "has_tag": HasTag(),
            "has_forbidden_tag": HasForbiddenTag(),
            "has_attribute": HasAttribute(),
            "check_no_unclosed_tags": CheckNoUnclosedTags(),
            "check_no_inline_styles": CheckNoInlineStyles(),
            "uses_semantic_tags": UsesSemanticTags(),
            "check_css_linked": CheckCssLinked(),
            "css_uses_property": CssUsesProperty(),
            "count_over_usage": CountOverUsage(),
            "js_uses_feature": JsUsesFeature(),
            "uses_forbidden_method": UsesForbiddenMethod(),
            "count_global_vars": CountGlobalVars(),
            "check_headings_sequential": CheckHeadingsSequential(),
            "check_all_images_have_alt": CheckAllImagesHaveAlt(),
            "check_html_direct_children": CheckHtmlDirectChildren(),
            "check_tag_not_inside": CheckTagNotInside(),
            "check_internal_links_to_article": CheckInternalLinksToArticle(),
            "has_style": HasStyle(),
            "check_head_details": CheckHeadDetails(),
            "check_attribute_and_value": CheckAttributeAndValue(),
            "check_dir_exists": CheckDirExists(),
            "check_project_structure": CheckProjectStructure(),
            "check_id_selector_over_usage": CheckIdSelectorOverUsage(),
            "uses_relative_units": UsesRelativeUnits(),
            "check_media_queries": CheckMediaQueries(),
            "check_flexbox_usage": CheckFlexboxUsage(),
            "check_bootstrap_usage": CheckBootstrapUsage(),
            "link_points_to_page_with_query_param": LinkPointsToPageWithQueryParam(),
            "js_uses_query_string_parsing": JsUsesQueryStringParsing(),
            "js_has_json_array_with_id": JsHasJsonArrayWithId(),
            "js_uses_dom_manipulation": JsUsesDomManipulation(),
            "has_no_js_framework": HasNoJsFramework(),
            "count_unused_css_classes": CountUnusedCssClasses()
        }

    def get_test(self, name: str) -> TestFunction:
        """
        Retrieves a specific test function instance from the template.
        """
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function
