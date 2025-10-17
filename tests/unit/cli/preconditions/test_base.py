"""Tests for precondition base types."""

from erenshor.cli.preconditions.base import PreconditionResult


def test_precondition_result_creation():
    """Test creating a PreconditionResult."""
    result = PreconditionResult(
        passed=True,
        check_name="test_check",
        message="Test passed",
        detail="Additional details",
    )

    assert result.passed is True
    assert result.check_name == "test_check"
    assert result.message == "Test passed"
    assert result.detail == "Additional details"


def test_precondition_result_success_str():
    """Test string representation of successful check."""
    result = PreconditionResult(
        passed=True,
        check_name="test_check",
        message="All good",
    )

    assert str(result) == "✓ All good"


def test_precondition_result_failure_str():
    """Test string representation of failed check."""
    result = PreconditionResult(
        passed=False,
        check_name="test_check",
        message="Something wrong",
    )

    assert str(result) == "✗ Something wrong"


def test_precondition_result_with_detail():
    """Test string representation with detail."""
    result = PreconditionResult(
        passed=False,
        check_name="test_check",
        message="Check failed",
        detail="Error: file not found",
    )

    output = str(result)
    assert "✗ Check failed" in output
    assert "Error: file not found" in output


def test_precondition_result_with_multiline_detail():
    """Test string representation with multiline detail."""
    result = PreconditionResult(
        passed=False,
        check_name="test_check",
        message="Check failed",
        detail="Line 1\nLine 2\nLine 3",
    )

    output = str(result)
    assert "✗ Check failed" in output
    assert "Line 1" in output
    assert "Line 2" in output
    assert "Line 3" in output


def test_precondition_result_default_detail():
    """Test that detail defaults to empty string."""
    result = PreconditionResult(
        passed=True,
        check_name="test_check",
        message="Test",
    )

    assert result.detail == ""
    assert str(result) == "✓ Test"
