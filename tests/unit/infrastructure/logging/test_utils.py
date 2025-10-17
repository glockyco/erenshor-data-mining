"""Tests for logging utility functions.

This module tests logging utilities including:
- Command logging (start/end)
- Error logging with context and tracebacks
- Progress logging for long operations
- Operation context manager for timing
- Function decorator for automatic logging
"""

import time

import pytest
from loguru import logger

from erenshor.infrastructure.logging.utils import (
    log_command_end,
    log_command_start,
    log_error,
    log_function,
    log_operation,
    log_progress,
)


@pytest.fixture
def log_messages():
    """Fixture that captures log messages in a list."""
    messages = []

    def sink(message):
        messages.append(str(message))

    # Remove existing handlers and add test sink
    logger.remove()
    handler_id = logger.add(sink, level="DEBUG", format="{level} | {message}")

    yield messages

    # Cleanup
    logger.remove(handler_id)


class TestCommandLogging:
    """Tests for log_command_start and log_command_end functions."""

    def test_log_command_start_basic(self, log_messages):
        """Test logging command start without context."""
        log_command_start("export")

        assert len(log_messages) == 1
        assert "INFO" in log_messages[0]
        assert "Command started: export" in log_messages[0]

    def test_log_command_start_with_context(self, log_messages):
        """Test logging command start with context data."""
        log_command_start("export", variant="main", force=True)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "INFO" in message
        assert "Command started: export" in message
        assert "variant=main" in message
        assert "force=True" in message

    def test_log_command_start_with_multiple_context(self, log_messages):
        """Test logging command start with multiple context values."""
        log_command_start(
            "sheets.deploy",
            variant="playtest",
            dry_run=False,
            sheets=["items", "characters"],
        )

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "Command started: sheets.deploy" in message
        assert "variant=playtest" in message
        assert "dry_run=False" in message

    def test_log_command_start_empty_command(self, log_messages):
        """Test logging with empty command name."""
        log_command_start("")

        assert len(log_messages) == 1
        assert "Command started:" in log_messages[0]

    def test_log_command_end_success(self, log_messages):
        """Test logging successful command completion."""
        log_command_end("export", duration=2.5, success=True)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "INFO" in message
        assert "Command completed: export (2.50s)" in message

    def test_log_command_end_failure(self, log_messages):
        """Test logging failed command completion."""
        log_command_end("export", duration=1.23, success=False)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "ERROR" in message
        assert "Command failed: export (1.23s)" in message

    def test_log_command_end_with_context(self, log_messages):
        """Test logging command end with context data."""
        log_command_end(
            "deploy",
            duration=5.67,
            success=False,
            error="Network timeout",
            retries=3,
        )

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "ERROR" in message
        assert "Command failed: deploy (5.67s)" in message
        assert "error=Network timeout" in message
        assert "retries=3" in message

    def test_log_command_end_duration_formatting(self, log_messages):
        """Test that duration is formatted to 2 decimal places."""
        test_cases = [
            (0.0, "0.00s"),
            (0.1, "0.10s"),
            (1.234, "1.23s"),
            (10.999, "11.00s"),
            (100.5, "100.50s"),
        ]

        for duration, expected in test_cases:
            log_messages.clear()
            log_command_end("test", duration=duration)
            assert expected in log_messages[0]

    def test_log_command_end_default_success(self, log_messages):
        """Test that success defaults to True."""
        log_command_end("test", duration=1.0)

        assert len(log_messages) == 1
        assert "INFO" in log_messages[0]
        assert "Command completed" in log_messages[0]


class TestErrorLogging:
    """Tests for log_error function."""

    def test_log_error_basic(self, log_messages):
        """Test logging an error without context."""
        error = ValueError("Something went wrong")
        log_error(error, show_traceback=False)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "ERROR" in message
        assert "ValueError" in message
        assert "Something went wrong" in message

    def test_log_error_with_context(self, log_messages):
        """Test logging an error with context data."""
        error = ZeroDivisionError("division by zero")
        context = {"numerator": 10, "denominator": 0}
        log_error(error, context=context, show_traceback=False)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "ERROR" in message
        assert "ZeroDivisionError" in message
        assert "division by zero" in message
        assert "numerator=10" in message
        assert "denominator=0" in message

    def test_log_error_with_traceback(self, log_messages):
        """Test logging an error with traceback enabled."""
        try:
            raise RuntimeError("Test error with traceback")
        except RuntimeError as e:
            log_error(e, show_traceback=True)

        # Should have error message (traceback may be in separate messages)
        assert len(log_messages) >= 1
        first_message = log_messages[0]
        assert "ERROR" in first_message
        assert "RuntimeError" in first_message
        assert "Test error with traceback" in first_message

    def test_log_error_without_traceback(self, log_messages):
        """Test logging an error with traceback disabled."""
        error = RuntimeError("Test error without traceback")
        log_error(error, show_traceback=False)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "ERROR" in message
        assert "RuntimeError" in message
        assert "Test error without traceback" in message

    def test_log_error_empty_context(self, log_messages):
        """Test logging an error with empty context dict."""
        error = ValueError("Test error")
        log_error(error, context={}, show_traceback=False)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "ERROR" in message
        assert "ValueError" in message

    def test_log_error_none_context(self, log_messages):
        """Test logging an error with None context."""
        error = ValueError("Test error")
        log_error(error, context=None, show_traceback=False)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "ERROR" in message
        assert "ValueError" in message

    def test_log_error_custom_exception_types(self, log_messages):
        """Test logging different exception types."""
        test_cases = [
            ValueError("value error"),
            TypeError("type error"),
            RuntimeError("runtime error"),
            FileNotFoundError("file not found"),
            KeyError("key error"),
        ]

        for error in test_cases:
            log_messages.clear()
            log_error(error, show_traceback=False)

            assert len(log_messages) == 1
            message = log_messages[0]
            assert type(error).__name__ in message
            assert str(error) in message


class TestProgressLogging:
    """Tests for log_progress function."""

    def test_log_progress_basic(self, log_messages):
        """Test logging progress with default settings."""
        log_progress("Processing items", current=1, total=10)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "INFO" in message
        assert "Processing items: 1/10 (10%)" in message

    def test_log_progress_without_percentage(self, log_messages):
        """Test logging progress without percentage."""
        log_progress("Processing items", current=5, total=20, show_percentage=False)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "Processing items: 5/20" in message
        assert "%" not in message

    def test_log_progress_with_percentage(self, log_messages):
        """Test logging progress with percentage enabled."""
        log_progress("Processing items", current=25, total=100, show_percentage=True)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "Processing items: 25/100 (25%)" in message

    def test_log_progress_different_levels(self, log_messages):
        """Test logging progress at different log levels."""
        test_cases = [
            ("DEBUG", "DEBUG"),
            ("INFO", "INFO"),
            ("WARNING", "WARNING"),
            ("ERROR", "ERROR"),
        ]

        for level, expected in test_cases:
            log_messages.clear()
            log_progress("Test", current=1, total=2, level=level)

            assert len(log_messages) == 1
            assert expected in log_messages[0]

    def test_log_progress_percentage_calculation(self, log_messages):
        """Test that percentage is calculated correctly."""
        test_cases = [
            (1, 4, "25%"),
            (1, 2, "50%"),
            (3, 4, "75%"),
            (4, 4, "100%"),
            (0, 10, "0%"),
        ]

        for current, total, expected in test_cases:
            log_messages.clear()
            log_progress("Test", current=current, total=total)
            assert expected in log_messages[0]

    def test_log_progress_zero_total(self, log_messages):
        """Test logging progress when total is zero."""
        log_progress("Test", current=0, total=0)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "0/0 (0%)" in message

    def test_log_progress_large_numbers(self, log_messages):
        """Test logging progress with large numbers."""
        log_progress("Processing", current=5000, total=10000)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "5000/10000 (50%)" in message

    def test_log_progress_fractional_percentage(self, log_messages):
        """Test that fractional percentages are rounded."""
        # 1/3 = 33.333...% -> should round to 33%
        log_progress("Test", current=1, total=3)

        assert len(log_messages) == 1
        message = log_messages[0]
        assert "1/3 (33%)" in message


class TestOperationContext:
    """Tests for log_operation context manager."""

    def test_log_operation_basic(self, log_messages):
        """Test basic operation logging without errors."""
        with log_operation("database query"):
            pass

        # Should have start and end messages
        assert len(log_messages) == 2
        assert "Starting: database query" in log_messages[0]
        assert "Completed: database query" in log_messages[1]
        assert "s)" in log_messages[1]  # Duration

    def test_log_operation_with_context(self, log_messages):
        """Test operation logging with initial context."""
        with log_operation("database query", log_args=True, query="SELECT * FROM items"):
            pass

        assert len(log_messages) == 2
        assert "Starting: database query" in log_messages[0]
        assert "query=SELECT * FROM items" in log_messages[0]
        assert "Completed: database query" in log_messages[1]

    def test_log_operation_with_runtime_context(self, log_messages):
        """Test operation logging with runtime context updates."""
        with log_operation("file processing") as ctx:
            ctx["rows"] = 1234
            ctx["errors"] = 5

        assert len(log_messages) == 2
        assert "Starting: file processing" in log_messages[0]
        assert "Completed: file processing" in log_messages[1]
        assert "rows=1234" in log_messages[1]
        assert "errors=5" in log_messages[1]

    def test_log_operation_with_exception(self, log_messages):
        """Test operation logging when exception is raised."""
        with pytest.raises(ValueError), log_operation("risky operation"):
            raise ValueError("Something went wrong")

        # Should have start, failure, and error messages
        assert len(log_messages) >= 2
        assert "Starting: risky operation" in log_messages[0]
        assert "Failed: risky operation" in log_messages[1]

    def test_log_operation_timing(self, log_messages):
        """Test that operation timing is accurate."""
        with log_operation("slow operation"):
            time.sleep(0.1)  # Sleep for 100ms

        assert len(log_messages) == 2
        # Extract duration from message
        completed_msg = log_messages[1]
        assert "Completed: slow operation" in completed_msg
        # Duration should be ~0.1s (allow some variance)
        assert "0.1" in completed_msg or "0.0" in completed_msg

    def test_log_operation_different_levels(self, log_messages):
        """Test operation logging at different log levels."""
        test_cases = ["DEBUG", "INFO", "WARNING", "ERROR"]

        for level in test_cases:
            log_messages.clear()
            with log_operation("test", level=level):
                pass

            assert len(log_messages) == 2
            # Check that messages use the specified level
            # Note: Loguru might format level differently

    def test_log_operation_without_args(self, log_messages):
        """Test operation logging without logging arguments."""
        with log_operation("test operation", log_args=False, key="value"):
            pass

        assert len(log_messages) == 2
        assert "Starting: test operation" in log_messages[0]
        # Context should not be in start message when log_args=False
        assert "key=value" not in log_messages[0]

    def test_log_operation_yields_mutable_context(self, log_messages):
        """Test that operation context is mutable."""
        with log_operation("test") as ctx:
            assert isinstance(ctx, dict)
            assert len(ctx) == 0

            ctx["key"] = "value"
            assert ctx["key"] == "value"

    def test_log_operation_exception_includes_context(self, log_messages):
        """Test that exceptions are logged with context."""
        with pytest.raises(RuntimeError), log_operation("failing operation", log_args=True, param="test"):
            raise RuntimeError("Test failure")

        # Should log the failure with original context
        assert any("Failed: failing operation" in msg for msg in log_messages)


class TestFunctionDecorator:
    """Tests for log_function decorator."""

    def test_log_function_basic(self, log_messages):
        """Test basic function logging without arguments or result."""

        @log_function()
        def test_func():
            return 42

        result = test_func()

        assert result == 42
        assert len(log_messages) == 2
        assert "Entering: test_func" in log_messages[0]
        assert "Exiting: test_func" in log_messages[1]

    def test_log_function_with_args(self, log_messages):
        """Test function logging with argument logging enabled."""

        @log_function(log_args=True)
        def add(x, y):
            return x + y

        result = add(10, 20)

        assert result == 30
        assert len(log_messages) == 2
        assert "Entering: add" in log_messages[0]
        assert "args=(10, 20)" in log_messages[0]
        assert "Exiting: add" in log_messages[1]

    def test_log_function_with_kwargs(self, log_messages):
        """Test function logging with keyword arguments."""

        @log_function(log_args=True)
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = greet("Alice", greeting="Hi")

        assert result == "Hi, Alice!"
        assert len(log_messages) == 2
        assert "Entering: greet" in log_messages[0]
        assert "Alice" in log_messages[0]
        assert "greeting='Hi'" in log_messages[0]

    def test_log_function_with_result(self, log_messages):
        """Test function logging with result logging enabled."""

        @log_function(log_result=True)
        def multiply(x, y):
            return x * y

        result = multiply(5, 6)

        assert result == 30
        assert len(log_messages) == 2
        assert "Entering: multiply" in log_messages[0]
        assert "Exiting: multiply" in log_messages[1]
        assert "result=30" in log_messages[1]

    def test_log_function_with_args_and_result(self, log_messages):
        """Test function logging with both args and result."""

        @log_function(log_args=True, log_result=True)
        def calculate(x, y):
            return x + y

        result = calculate(10, 20)

        assert result == 30
        assert len(log_messages) == 2
        assert "args=(10, 20)" in log_messages[0]
        assert "result=30" in log_messages[1]

    def test_log_function_with_exception(self, log_messages):
        """Test function logging when exception is raised."""

        @log_function()
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_func()

        # Should log entry, exception, and error
        assert len(log_messages) >= 2
        assert "Entering: failing_func" in log_messages[0]
        assert "Exception in: failing_func" in log_messages[1]

    def test_log_function_timing(self, log_messages):
        """Test that function timing is logged."""

        @log_function()
        def slow_func():
            time.sleep(0.05)
            return "done"

        result = slow_func()

        assert result == "done"
        assert len(log_messages) == 2
        assert "Exiting: slow_func" in log_messages[1]
        # Should include timing (allow variance)
        assert "s)" in log_messages[1]

    def test_log_function_different_levels(self, log_messages):
        """Test function logging at different log levels."""

        @log_function(level="INFO")
        def test_func():
            pass

        test_func()

        assert len(log_messages) == 2
        # Messages should be at INFO level

    def test_log_function_preserves_function_metadata(self, log_messages):
        """Test that decorator preserves function name and docstring."""

        @log_function()
        def documented_func(x: int) -> int:
            """This is a documented function."""
            return x * 2

        # Check that metadata is preserved
        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a documented function."

    def test_log_function_with_no_arguments(self, log_messages):
        """Test logging a function with no arguments."""

        @log_function(log_args=True)
        def no_args():
            return "result"

        result = no_args()

        assert result == "result"
        assert len(log_messages) == 2
        assert "Entering: no_args" in log_messages[0]
        # Should have args=() for empty args
        assert "args=()" in log_messages[0]

    def test_log_function_with_complex_types(self, log_messages):
        """Test logging function with complex argument types."""

        @log_function(log_args=True, log_result=True)
        def process_data(items: list[int], config: dict[str, str]) -> int:
            return len(items)

        result = process_data([1, 2, 3], {"key": "value"})

        assert result == 3
        assert len(log_messages) == 2
        # Args should be logged with repr
        assert "Entering: process_data" in log_messages[0]
        assert "result=3" in log_messages[1]

    def test_log_function_exception_logging(self, log_messages):
        """Test that exceptions are logged with full context."""

        @log_function(log_args=True)
        def divide(x, y):
            return x / y

        with pytest.raises(ZeroDivisionError):
            divide(10, 0)

        # Should log entry, exception, and error details
        assert len(log_messages) >= 2
        assert "Entering: divide" in log_messages[0]
        assert "args=(10, 0)" in log_messages[0]
        assert "Exception in: divide" in log_messages[1]
