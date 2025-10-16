"""Logging utility functions and helpers.

This module provides high-level logging utilities for common patterns in the
Erenshor pipeline. These functions wrap Loguru's logger with convenience APIs
for command execution, error handling, progress tracking, and operation timing.

Key utilities:
- Command logging: Track CLI command execution lifecycle
- Error logging: Log exceptions with rich context
- Progress tracking: Show completion progress for long operations
- Operation timing: Context manager for automatic timing
- Function decoration: Automatic entry/exit logging

All utilities use Loguru under the hood and integrate cleanly with the
logging setup from setup.py.
"""

import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any, TypeVar

from loguru import logger

# Type variable for function decorators
F = TypeVar("F", bound=Callable[..., Any])


def log_command_start(command: str, **context: Any) -> None:
    """Log the start of a CLI command execution.

    Logs at INFO level with the command name and any additional context
    data provided as keyword arguments. Useful for tracking command
    invocations in the pipeline.

    Args:
        command: Name of the command being executed (e.g., "export", "deploy").
        **context: Additional context data to include in the log message
            (e.g., variant="main", dry_run=True).

    Example:
        >>> log_command_start("export", variant="main", force=True)
        # Logs: "Command started: export | variant=main force=True"

        >>> log_command_start("sheets.deploy")
        # Logs: "Command started: sheets.deploy"
    """
    if context:
        context_str = " ".join(f"{k}={v}" for k, v in context.items())
        logger.info(f"Command started: {command} | {context_str}")
    else:
        logger.info(f"Command started: {command}")


def log_command_end(
    command: str,
    duration: float,
    success: bool = True,
    **context: Any,
) -> None:
    """Log the completion of a CLI command.

    Logs at INFO level for successful commands or ERROR level for failed
    commands. Includes execution duration and optional context data.

    Args:
        command: Name of the command that completed.
        duration: Execution time in seconds (e.g., from time.time()).
        success: Whether the command succeeded. Defaults to True.
        **context: Additional context data to include in the log message.

    Example:
        >>> start = time.time()
        >>> # ... do work ...
        >>> log_command_end("export", time.time() - start)
        # Logs: "Command completed: export (2.34s)"

        >>> log_command_end("deploy", 5.67, success=False, error="Network timeout")
        # Logs: "Command failed: deploy (5.67s) | error=Network timeout"
    """
    duration_str = f"{duration:.2f}s"

    if context:
        context_str = " ".join(f"{k}={v}" for k, v in context.items())
        msg = f"{command} ({duration_str}) | {context_str}"
    else:
        msg = f"{command} ({duration_str})"

    if success:
        logger.info(f"Command completed: {msg}")
    else:
        logger.error(f"Command failed: {msg}")


def log_error(
    error: Exception,
    context: dict[str, Any] | None = None,
    *,
    show_traceback: bool = True,
) -> None:
    """Log an error with full context and traceback.

    Logs at ERROR level with the exception type, message, and optional
    traceback. Includes any additional context data provided.

    Args:
        error: The exception to log.
        context: Optional dictionary of context data to include.
        show_traceback: Whether to include the full traceback. Defaults to True.

    Example:
        >>> try:
        ...     result = divide(10, 0)
        ... except ZeroDivisionError as e:
        ...     log_error(e, {"numerator": 10, "denominator": 0})
        # Logs: "Error: ZeroDivisionError: division by zero | numerator=10 denominator=0"
        # (plus traceback)

        >>> log_error(RuntimeError("Database locked"), show_traceback=False)
        # Logs: "Error: RuntimeError: Database locked" (no traceback)
    """
    error_type = type(error).__name__
    error_msg = str(error)

    # Build context string
    context_parts = []
    if context:
        context_parts.append(" | ")
        context_parts.append(" ".join(f"{k}={v}" for k, v in context.items()))

    context_str = "".join(context_parts)

    # Log error with optional traceback
    if show_traceback:
        # Loguru will automatically include the traceback when we pass exception=True
        logger.opt(exception=True).error(f"Error: {error_type}: {error_msg}{context_str}")
    else:
        logger.error(f"Error: {error_type}: {error_msg}{context_str}")


def log_progress(
    message: str,
    current: int,
    total: int,
    *,
    level: str = "INFO",
    show_percentage: bool = True,
) -> None:
    """Log progress information for long-running operations.

    Logs progress with current/total counts and optional percentage.
    Useful for tracking progress through large datasets or batch operations.

    Args:
        message: Description of what is in progress.
        current: Current progress count (0-indexed or 1-indexed).
        total: Total number of items to process.
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO.
        show_percentage: Whether to include percentage. Defaults to True.

    Example:
        >>> for i, item in enumerate(items, start=1):
        ...     log_progress("Processing items", i, len(items))
        ...     process(item)
        # Logs: "Processing items: 1/100 (1%)"
        # Logs: "Processing items: 2/100 (2%)"
        # ...

        >>> log_progress("Fetching pages", 5, 20, level="DEBUG")
        # Logs: "Fetching pages: 5/20 (25%)"
    """
    # Calculate percentage
    if total > 0:
        percentage = (current / total) * 100
    else:
        percentage = 0.0

    # Build progress string
    if show_percentage:
        progress_str = f"{current}/{total} ({percentage:.0f}%)"
    else:
        progress_str = f"{current}/{total}"

    # Log at specified level
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(f"{message}: {progress_str}")


@contextmanager
def log_operation(
    operation: str,
    *,
    level: str = "INFO",
    log_args: bool = False,
    **context: Any,
) -> Any:
    """Context manager for timing and logging operations.

    Automatically logs operation start, end, duration, and handles exceptions.
    Useful for wrapping operations that should be timed and logged.

    Args:
        operation: Name of the operation being performed.
        level: Log level for start/end messages. Defaults to INFO.
        log_args: Whether to log the context as args. Defaults to False.
        **context: Additional context data to include in log messages.

    Yields:
        dict: A context dictionary that can be updated during the operation.

    Raises:
        Exception: Any exception raised within the context is re-raised after logging.

    Example:
        >>> with log_operation("database query", query="SELECT * FROM items"):
        ...     results = db.execute(query)
        # Logs: "Starting: database query | query=SELECT * FROM items"
        # Logs: "Completed: database query (0.15s)"

        >>> with log_operation("file processing") as ctx:
        ...     data = process_file("data.csv")
        ...     ctx["rows"] = len(data)
        # Logs: "Starting: file processing"
        # Logs: "Completed: file processing (2.34s) | rows=1234"

        >>> with log_operation("risky operation"):
        ...     raise ValueError("Something went wrong")
        # Logs: "Starting: risky operation"
        # Logs: "Failed: risky operation (0.01s)"
        # Logs full error traceback and re-raises exception
    """
    log_method = getattr(logger, level.lower(), logger.info)

    # Log start
    if context and log_args:
        context_str = " | " + " ".join(f"{k}={v}" for k, v in context.items())
        log_method(f"Starting: {operation}{context_str}")
    else:
        log_method(f"Starting: {operation}")

    # Create mutable context dict for updates during operation
    runtime_context: dict[str, Any] = {}

    start_time = time.time()
    try:
        yield runtime_context
        duration = time.time() - start_time

        # Log success with any runtime context
        if runtime_context:
            context_str = " | " + " ".join(f"{k}={v}" for k, v in runtime_context.items())
            log_method(f"Completed: {operation} ({duration:.2f}s){context_str}")
        else:
            log_method(f"Completed: {operation} ({duration:.2f}s)")

    except Exception as e:
        duration = time.time() - start_time

        # Log failure
        logger.error(f"Failed: {operation} ({duration:.2f}s)")
        log_error(e, context=context or None)
        raise


def log_function(
    *,
    level: str = "DEBUG",
    log_args: bool = False,
    log_result: bool = False,
) -> Callable[[F], F]:
    """Decorator to log function entry, exit, and timing.

    Wraps a function to automatically log when it's called and when it returns.
    Optionally logs arguments and return values. Useful for debugging and
    tracking function execution flow.

    Args:
        level: Log level for entry/exit messages. Defaults to DEBUG.
        log_args: Whether to log function arguments. Defaults to False.
        log_result: Whether to log return value. Defaults to False.

    Returns:
        Decorator function that wraps the target function.

    Example:
        >>> @log_function()
        ... def process_data(data: list[int]) -> int:
        ...     return sum(data)
        >>> process_data([1, 2, 3])
        # Logs: "Entering: process_data"
        # Logs: "Exiting: process_data (0.00s)"
        # Returns: 6

        >>> @log_function(level="INFO", log_args=True, log_result=True)
        ... def calculate(x: int, y: int) -> int:
        ...     return x + y
        >>> calculate(10, 20)
        # Logs: "Entering: calculate | args=(10, 20)"
        # Logs: "Exiting: calculate (0.00s) | result=30"
        # Returns: 30
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            log_method = getattr(logger, level.lower(), logger.debug)
            func_name = func.__name__

            # Log entry
            if log_args:
                args_str = ", ".join(repr(arg) for arg in args)
                kwargs_str = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
                all_args = ", ".join(filter(None, [args_str, kwargs_str]))
                log_method(f"Entering: {func_name} | args=({all_args})")
            else:
                log_method(f"Entering: {func_name}")

            # Execute function
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Log exit
                if log_result:
                    log_method(f"Exiting: {func_name} ({duration:.2f}s) | result={result!r}")
                else:
                    log_method(f"Exiting: {func_name} ({duration:.2f}s)")

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Exception in: {func_name} ({duration:.2f}s)")
                log_error(e)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator
