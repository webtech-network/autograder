"""Test suite for configuration models to ensure they align with criteria_schema.json"""

import json
import pytest
from pathlib import Path

from autograder.models.config.criteria import CriteriaConfig
from autograder.models.config.category import CategoryConfig
from autograder.models.config.subject import SubjectConfig
from autograder.models.config.test import TestConfig, ParameterConfig


@pytest.fixture
def criteria_schema_path():
    """Path to the criteria_schema.json file"""
    return Path(__file__).parent.parent.parent / "critera_schema.json"


@pytest.fixture
def criteria_schema_dict(criteria_schema_path):
    """Load criteria schema as dictionary"""
    with open(criteria_schema_path, "r") as f:
        return json.load(f)


@pytest.fixture
def criteria_config(criteria_schema_dict):
    """Parse criteria schema into CriteriaConfig object"""
    return CriteriaConfig.from_dict(criteria_schema_dict)


class TestParameterConfig:
    """Test ParameterConfig model"""

    def test_parameter_config_creation(self):
        """Test creating a ParameterConfig"""
        param = ParameterConfig(name="tag", value="body")
        assert param.name == "tag"
        assert param.value == "body"

    def test_parameter_config_with_int_value(self):
        """Test ParameterConfig with integer value"""
        param = ParameterConfig(name="required_count", value=1)
        assert param.name == "required_count"
        assert param.value == 1
        assert isinstance(param.value, int)

    def test_parameter_config_forbid_extra(self):
        """Test that extra fields are forbidden"""
        with pytest.raises(ValueError):
            ParameterConfig(name="tag", value="body", extra_field="not allowed")


class TestTestConfig:
    """Test TestConfig model"""

    def test_test_config_with_file_and_name(self):
        """Test creating a TestConfig with file and name"""
        test = TestConfig(
            file="index.html",
            name="has_tag",
            parameters=[
                ParameterConfig(name="tag", value="body"),
                ParameterConfig(name="required_count", value=1),
            ],
        )
        assert test.file == "index.html"
        assert test.name == "has_tag"
        assert test.parameters is not None
        assert len(test.parameters) == 2

    def test_test_config_without_parameters(self):
        """Test TestConfig without parameters"""
        test = TestConfig(file="index.html", name="check_css_linked")
        assert test.file == "index.html"
        assert test.name == "check_css_linked"
        assert test.parameters is None

    def test_get_args_list(self):
        """Test converting parameters to args list"""
        test = TestConfig(
            file="index.html",
            name="has_tag",
            parameters=[
                ParameterConfig(name="tag", value="body"),
                ParameterConfig(name="required_count", value=1),
            ],
        )
        args = test.get_args_list()
        assert args == ["body", 1]

    def test_get_kwargs_dict(self):
        """Test converting parameters to kwargs dict"""
        test = TestConfig(
            file="index.html",
            name="has_tag",
            parameters=[
                ParameterConfig(name="tag", value="body"),
                ParameterConfig(name="required_count", value=1),
            ],
        )
        kwargs = test.get_kwargs_dict()
        assert kwargs == {"tag": "body", "required_count": 1}

    def test_get_args_list_empty(self):
        """Test get_args_list with no parameters"""
        test = TestConfig(file="index.html", name="check_css_linked")
        args = test.get_args_list()
        assert args == []

    def test_get_kwargs_dict_empty(self):
        """Test get_kwargs_dict with no parameters"""
        test = TestConfig(file="index.html", name="check_css_linked")
        kwargs = test.get_kwargs_dict()
        assert kwargs == {}


class TestSubjectConfig:
    """Test SubjectConfig model"""

    def test_subject_config_with_tests(self):
        """Test SubjectConfig with tests only"""
        subject = SubjectConfig(
            subject_name="structure",
            weight=40,
            tests=[
                TestConfig(
                    file="index.html",
                    name="has_tag",
                    parameters=[ParameterConfig(name="tag", value="body")],
                )
            ],
        )
        assert subject.subject_name == "structure"
        assert subject.weight == 40
        assert subject.tests is not None
        assert len(subject.tests) == 1
        assert subject.subjects is None

    def test_subject_config_with_nested_subjects(self):
        """Test SubjectConfig with nested subjects"""
        subject = SubjectConfig(
            subject_name="html",
            weight=60,
            subjects=[
                SubjectConfig(
                    subject_name="structure",
                    weight=40,
                    tests=[TestConfig(file="index.html", name="has_tag")],
                )
            ],
        )
        assert subject.subject_name == "html"
        assert subject.weight == 60
        assert subject.subjects is not None
        assert len(subject.subjects) == 1
        assert subject.subjects[0].subject_name == "structure"

    def test_subject_config_validation_requires_tests_or_subjects(self):
        """Test that SubjectConfig requires at least tests or subjects"""
        with pytest.raises(
            ValueError, match="must have at least 'tests' or 'subjects'"
        ):
            SubjectConfig(subject_name="invalid", weight=50)

    def test_subject_config_with_both_tests_and_subjects_requires_subjects_weight(self):
        """Test that having both tests and subjects requires subjects_weight"""
        with pytest.raises(ValueError, match="needs 'subjects_weight' defined"):
            SubjectConfig(
                subject_name="mixed",
                weight=50,
                tests=[TestConfig(file="index.html", name="has_tag")],
                subjects=[
                    SubjectConfig(
                        subject_name="nested",
                        weight=30,
                        tests=[TestConfig(file="index.html", name="has_tag")],
                    )
                ],
            )

    def test_subject_config_with_both_tests_and_subjects_with_weight(self):
        """Test that having both tests and subjects works with subjects_weight"""
        subject = SubjectConfig(
            subject_name="mixed",
            weight=50,
            tests=[TestConfig(file="index.html", name="has_tag")],
            subjects=[
                SubjectConfig(
                    subject_name="nested",
                    weight=30,
                    tests=[TestConfig(file="index.html", name="has_tag")],
                )
            ],
            subjects_weight=60,
        )
        assert subject.subject_name == "mixed"
        assert subject.subjects_weight == 60


class TestCategoryConfig:
    """Test CategoryConfig model"""

    def test_category_config_with_subjects(self):
        """Test CategoryConfig with subjects"""
        category = CategoryConfig(
            weight=100,
            subjects=[
                SubjectConfig(
                    subject_name="html",
                    weight=60,
                    tests=[TestConfig(file="index.html", name="has_tag")],
                )
            ],
        )
        assert category.weight == 100
        assert category.subjects is not None
        assert len(category.subjects) == 1
        assert category.subjects[0].subject_name == "html"

    def test_category_config_validation_requires_tests_or_subjects(self):
        """Test that CategoryConfig requires at least tests or subjects"""
        with pytest.raises(
            ValueError, match="must have at least 'tests' or 'subjects'"
        ):
            CategoryConfig(weight=100)

    def test_category_config_with_both_tests_and_subjects_requires_subjects_weight(
        self,
    ):
        """Test that having both tests and subjects requires subjects_weight"""
        with pytest.raises(ValueError, match="needs 'subjects_weight' defined"):
            CategoryConfig(
                weight=100,
                tests=[TestConfig(file="index.html", name="has_tag")],
                subjects=[
                    SubjectConfig(
                        subject_name="nested",
                        weight=30,
                        tests=[TestConfig(file="index.html", name="has_tag")],
                    )
                ],
            )


class TestCriteriaConfig:
    """Test CriteriaConfig model"""

    def test_criteria_config_basic(self):
        """Test basic CriteriaConfig creation"""
        criteria = CriteriaConfig(
            test_library="web_dev",
            base=CategoryConfig(
                weight=100,
                subjects=[
                    SubjectConfig(
                        subject_name="html",
                        weight=60,
                        tests=[TestConfig(file="index.html", name="has_tag")],
                    )
                ],
            ),
        )
        assert criteria.test_library == "web_dev"
        assert criteria.base.weight == 100
        assert criteria.bonus is None
        assert criteria.penalty is None

    def test_criteria_config_with_all_categories(self):
        """Test CriteriaConfig with base, bonus, and penalty"""
        criteria = CriteriaConfig(
            test_library="web_dev",
            base=CategoryConfig(
                weight=100,
                subjects=[
                    SubjectConfig(
                        subject_name="html",
                        weight=60,
                        tests=[TestConfig(file="index.html", name="has_tag")],
                    )
                ],
            ),
            bonus=CategoryConfig(
                weight=40,
                subjects=[
                    SubjectConfig(
                        subject_name="accessibility",
                        weight=20,
                        tests=[
                            TestConfig(
                                file="index.html", name="check_all_images_have_alt"
                            )
                        ],
                    )
                ],
            ),
            penalty=CategoryConfig(
                weight=50,
                subjects=[
                    SubjectConfig(
                        subject_name="html",
                        weight=50,
                        tests=[
                            TestConfig(file="index.html", name="check_bootstrap_usage")
                        ],
                    )
                ],
            ),
        )
        assert criteria.test_library == "web_dev"
        assert criteria.base.weight == 100
        assert criteria.bonus is not None
        assert criteria.bonus.weight == 40
        assert criteria.penalty is not None
        assert criteria.penalty.weight == 50


class TestSchemaIntegration:
    """Integration tests with the actual criteria_schema.json file"""

    def test_parse_full_schema(self, criteria_config):
        """Test that the full schema parses successfully"""
        assert isinstance(criteria_config, CriteriaConfig)
        assert criteria_config.test_library == "web_dev"

    def test_base_category_parsed(self, criteria_config):
        """Test that base category is parsed correctly"""
        assert criteria_config.base is not None
        assert criteria_config.base.weight == 100
        assert len(criteria_config.base.subjects) == 2

    def test_html_subject_structure(self, criteria_config):
        """Test HTML subject structure"""
        html_subject = criteria_config.base.subjects[0]
        assert html_subject.subject_name == "html"
        assert html_subject.weight == 60
        assert len(html_subject.subjects) == 2  # structure and link

    def test_html_structure_subject(self, criteria_config):
        """Test HTML structure subject"""
        html_subject = criteria_config.base.subjects[0]
        structure_subject = html_subject.subjects[0]
        assert structure_subject.subject_name == "structure"
        assert structure_subject.weight == 40
        assert len(structure_subject.tests) == 12

    def test_html_link_subject(self, criteria_config):
        """Test HTML link subject"""
        html_subject = criteria_config.base.subjects[0]
        link_subject = html_subject.subjects[1]
        assert link_subject.subject_name == "link"
        assert link_subject.weight == 20
        assert len(link_subject.tests) == 2

    def test_css_subject_structure(self, criteria_config):
        """Test CSS subject structure"""
        css_subject = criteria_config.base.subjects[1]
        assert css_subject.subject_name == "css"
        assert css_subject.weight == 40
        assert len(css_subject.subjects) == 2  # responsivity and style

    def test_css_responsivity_subject(self, criteria_config):
        """Test CSS responsivity subject"""
        css_subject = criteria_config.base.subjects[1]
        responsivity_subject = css_subject.subjects[0]
        assert responsivity_subject.subject_name == "responsivity"
        assert responsivity_subject.weight == 50
        assert len(responsivity_subject.tests) == 3

    def test_css_style_subject(self, criteria_config):
        """Test CSS style subject"""
        css_subject = criteria_config.base.subjects[1]
        style_subject = css_subject.subjects[1]
        assert style_subject.subject_name == "style"
        assert style_subject.weight == 50
        assert len(style_subject.tests) == 7

    def test_bonus_category_parsed(self, criteria_config):
        """Test that bonus category is parsed correctly"""
        assert criteria_config.bonus is not None
        assert criteria_config.bonus.weight == 40
        assert len(criteria_config.bonus.subjects) == 2

    def test_accessibility_bonus_subject(self, criteria_config):
        """Test accessibility bonus subject"""
        accessibility_subject = criteria_config.bonus.subjects[0]
        assert accessibility_subject.subject_name == "accessibility"
        assert accessibility_subject.weight == 20
        assert len(accessibility_subject.tests) == 1

    def test_head_detail_bonus_subject(self, criteria_config):
        """Test head_detail bonus subject"""
        head_detail_subject = criteria_config.bonus.subjects[1]
        assert head_detail_subject.subject_name == "head_detail"
        assert head_detail_subject.weight == 80
        assert len(head_detail_subject.tests) == 7

    def test_penalty_category_parsed(self, criteria_config):
        """Test that penalty category is parsed correctly"""
        assert criteria_config.penalty is not None
        assert criteria_config.penalty.weight == 50
        assert len(criteria_config.penalty.subjects) == 2

    def test_html_penalty_subject(self, criteria_config):
        """Test HTML penalty subject"""
        html_penalty_subject = criteria_config.penalty.subjects[0]
        assert html_penalty_subject.subject_name == "html"
        assert html_penalty_subject.weight == 50
        assert len(html_penalty_subject.tests) == 6

    def test_project_structure_penalty_subject(self, criteria_config):
        """Test project_structure penalty subject"""
        project_structure_subject = criteria_config.penalty.subjects[1]
        assert project_structure_subject.subject_name == "project_structure"
        assert project_structure_subject.weight == 50
        assert len(project_structure_subject.tests) == 3

    def test_test_config_structure(self, criteria_config):
        """Test that test configs are structured correctly"""
        # Get first test from structure subject
        html_subject = criteria_config.base.subjects[0]
        structure_subject = html_subject.subjects[0]
        first_test = structure_subject.tests[0]

        assert first_test.file == "index.html"
        assert first_test.name == "has_tag"
        assert len(first_test.parameters) == 2
        assert first_test.parameters[0].name == "tag"
        assert first_test.parameters[0].value == "body"
        assert first_test.parameters[1].name == "required_count"
        assert first_test.parameters[1].value == 1

    def test_test_without_parameters(self, criteria_config):
        """Test parsing of tests without parameters"""
        # Get check_css_linked test from link subject
        html_subject = criteria_config.base.subjects[0]
        link_subject = html_subject.subjects[1]
        check_css_test = link_subject.tests[0]

        assert check_css_test.file == "index.html"
        assert check_css_test.name == "check_css_linked"
        assert check_css_test.parameters is None or len(check_css_test.parameters) == 0

    def test_parameter_value_types(self, criteria_config):
        """Test that parameter values maintain correct types"""
        html_subject = criteria_config.base.subjects[0]
        structure_subject = html_subject.subjects[0]

        # Check string value
        tag_param = structure_subject.tests[0].parameters[0]
        assert isinstance(tag_param.value, str)

        # Check integer value
        count_param = structure_subject.tests[0].parameters[1]
        assert isinstance(count_param.value, int)

    def test_from_json_method(self, criteria_schema_path):
        """Test parsing from JSON string"""
        with open(criteria_schema_path, "r") as f:
            json_str = f.read()

        criteria = CriteriaConfig.from_json(json_str)
        assert isinstance(criteria, CriteriaConfig)
        assert criteria.test_library == "web_dev"

    def test_from_dict_method(self, criteria_schema_dict):
        """Test parsing from dictionary"""
        criteria = CriteriaConfig.from_dict(criteria_schema_dict)
        assert isinstance(criteria, CriteriaConfig)
        assert criteria.test_library == "web_dev"

    def test_round_trip_serialization(self, criteria_config):
        """Test that we can serialize and deserialize the config"""
        # Convert to dict
        config_dict = criteria_config.model_dump()

        # Parse back from dict
        reparsed = CriteriaConfig.from_dict(config_dict)

        # Verify they match
        assert reparsed.test_library == criteria_config.test_library
        assert reparsed.base.weight == criteria_config.base.weight
        assert reparsed.base.subjects is not None
        assert len(reparsed.base.subjects) == len(criteria_config.base.subjects)

    def test_weight_validation(self):
        """Test that weight validation works"""
        with pytest.raises(ValueError):
            SubjectConfig(
                subject_name="invalid",
                weight=150,  # Over 100
                tests=[TestConfig(file="test.html", name="test")],
            )

        with pytest.raises(ValueError):
            SubjectConfig(
                subject_name="invalid",
                weight=-10,  # Negative
                tests=[TestConfig(file="test.html", name="test")],
            )

    def test_extra_fields_forbidden(self):
        """Test that extra fields are forbidden at all levels"""
        # Test at criteria level
        with pytest.raises(ValueError):
            CriteriaConfig(
                test_library="web_dev",
                base=CategoryConfig(
                    weight=100,
                    subjects=[
                        SubjectConfig(
                            subject_name="html",
                            weight=60,
                            tests=[TestConfig(file="index.html", name="has_tag")],
                        )
                    ],
                ),
                extra_field="not allowed",
            )


class TestWeightCalculations:
    """Test weight-related calculations and validations"""

    def test_subject_weights_sum(self, criteria_config):
        """Verify that subject weights in base category sum correctly"""
        base_subjects = criteria_config.base.subjects
        total_weight = sum(subject.weight for subject in base_subjects)
        assert total_weight == 100  # html=60 + css=40

    def test_nested_subject_weights_sum(self, criteria_config):
        """Verify that nested subject weights sum correctly"""
        html_subject = criteria_config.base.subjects[0]
        nested_subjects = html_subject.subjects
        total_weight = sum(subject.weight for subject in nested_subjects)
        assert total_weight == 60  # structure=40 + link=20

        css_subject = criteria_config.base.subjects[1]
        nested_subjects = css_subject.subjects
        total_weight = sum(subject.weight for subject in nested_subjects)
        assert total_weight == 100  # responsivity=50 + style=50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
