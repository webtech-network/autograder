"""Manual test script to verify language validation."""

from web.schemas.assignment import GradingConfigCreate, GradingConfigUpdate
from web.schemas.submission import SubmissionCreate, SubmissionFileData
from pydantic import ValidationError


def test_valid_languages():
    """Test that all valid languages work."""
    print("Testing valid languages...")
    valid_langs = ["python", "java", "node", "cpp", "PYTHON", "Java", "NODE", "Cpp"]

    for lang in valid_langs:
        try:
            config = GradingConfigCreate(
                external_assignment_id="test-001",
                template_name="input_output",
                criteria_config={"test_library": "input_output"},
                language=lang
            )
            print(f"  ✓ '{lang}' normalized to '{config.language}'")
        except ValidationError as e:
            print(f"  ✗ '{lang}' failed: {e}")


def test_invalid_languages():
    """Test that invalid languages are rejected."""
    print("\nTesting invalid languages (should fail)...")
    invalid_langs = ["javascript", "ruby", "go", "rust", "csharp", ""]

    for lang in invalid_langs:
        try:
            config = GradingConfigCreate(
                external_assignment_id="test-001",
                template_name="input_output",
                criteria_config={"test_library": "input_output"},
                language=lang
            )
            print(f"  ✗ '{lang}' was incorrectly accepted!")
        except ValidationError as e:
            error_msg = e.errors()[0]["msg"]
            print(f"  ✓ '{lang}' correctly rejected: {error_msg}")


def test_submission_language():
    """Test submission language validation."""
    print("\nTesting submission language validation...")

    # Test valid
    try:
        submission = SubmissionCreate(
            external_assignment_id="test-001",
            external_user_id="user-001",
            username="testuser",
            files=[SubmissionFileData(filename="test.py", content="print('hello')")],
            language="python"
        )
        print(f"  ✓ Valid submission language: {submission.language}")
    except ValidationError as e:
        print(f"  ✗ Valid submission failed: {e}")

    # Test invalid
    try:
        submission = SubmissionCreate(
            external_assignment_id="test-001",
            external_user_id="user-001",
            username="testuser",
            files=[SubmissionFileData(filename="test.js", content="console.log('hello')")],
            language="javascript"
        )
        print(f"  ✗ Invalid language 'javascript' was incorrectly accepted!")
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"]
        print(f"  ✓ Invalid language 'javascript' correctly rejected: {error_msg}")


def test_update_language():
    """Test update language validation."""
    print("\nTesting update language validation...")

    # Test valid
    try:
        update = GradingConfigUpdate(language="node")
        print(f"  ✓ Valid update language: {update.language}")
    except ValidationError as e:
        print(f"  ✗ Valid update failed: {e}")

    # Test invalid
    try:
        update = GradingConfigUpdate(language="javascript")
        print(f"  ✗ Invalid language 'javascript' was incorrectly accepted!")
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"]
        print(f"  ✓ Invalid language 'javascript' correctly rejected: {error_msg}")

    # Test None (should be allowed)
    try:
        update = GradingConfigUpdate(language=None)
        print(f"  ✓ None language accepted: {update.language}")
    except ValidationError as e:
        print(f"  ✗ None language failed: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Language Validation Test")
    print("=" * 60)

    test_valid_languages()
    test_invalid_languages()
    test_submission_language()
    test_update_language()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

