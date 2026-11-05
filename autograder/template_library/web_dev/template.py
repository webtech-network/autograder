from autograder.models.abstract.template import Template
from autograder.template_library.web_dev.html_tests import (
    HasClass, CheckBootstrapLinked, CheckInternalLinks, HasTag, HasForbiddenTag,
    HasAttribute, CheckNoUnclosedTags, CheckNoInlineStyles, UsesSemanticTags,
    CheckCssLinked, CheckHeadDetails, CheckAttributeAndValue, CheckInternalLinksToArticle,
    CheckTagNotInside, CheckHeadingsSequential, CheckAllImagesHaveAlt,
    CheckHtmlDirectChildren, LinkPointsToPageWithQueryParam, CheckBootstrapUsage
)
from autograder.template_library.web_dev.css_tests import (
    CssUsesProperty, CountOverUsage, HasStyle, CheckIdSelectorOverUsage,
    UsesRelativeUnits, CheckMediaQueries, CheckFlexboxUsage, CountUnusedCssClasses
)
from autograder.template_library.web_dev.js_tests import (
    JsUsesFeature, UsesForbiddenMethod, CountGlobalVars, JsUsesQueryStringParsing,
    JsHasJsonArrayWithId, JsUsesDomManipulation, HasNoJsFramework
)
from autograder.template_library.web_dev.structure_tests import (
    CheckDirExists, CheckProjectStructure
)


class WebDevTemplate(Template):
    """HTML, CSS and JavaScript checks for web development assignments."""

    def __init__(self):
        super().__init__(
            "Html Css Js Template",
            "Um template abrangente para trabalhos de desenvolvimento web, incluindo testes para HTML, CSS e JavaScript.",
            [
                HasClass(), CheckBootstrapLinked(), CheckInternalLinks(), HasTag(), HasForbiddenTag(),
                HasAttribute(), CheckNoUnclosedTags(), CheckNoInlineStyles(), UsesSemanticTags(),
                CheckCssLinked(), CssUsesProperty(), CountOverUsage(), JsUsesFeature(), UsesForbiddenMethod(),
                CountGlobalVars(), CheckHeadingsSequential(), CheckAllImagesHaveAlt(),
                CheckHtmlDirectChildren(), CheckTagNotInside(), CheckInternalLinksToArticle(), HasStyle(),
                CheckHeadDetails(), CheckAttributeAndValue(), CheckDirExists(), CheckProjectStructure(),
                CheckIdSelectorOverUsage(), UsesRelativeUnits(), CheckMediaQueries(), CheckFlexboxUsage(),
                CheckBootstrapUsage(), LinkPointsToPageWithQueryParam(), JsUsesQueryStringParsing(),
                JsHasJsonArrayWithId(), JsUsesDomManipulation(), HasNoJsFramework(), CountUnusedCssClasses(),
            ],
        )
