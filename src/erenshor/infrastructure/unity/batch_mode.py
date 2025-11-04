"""Unity Editor batch mode wrapper for executing C# export scripts.

This module provides a Python wrapper around Unity Editor's batch mode functionality,
enabling programmatic execution of custom C# scripts for data export operations.

Features:
- Execute Unity Editor in headless batch mode
- Run static C# methods via -executeMethod
- Pass custom command-line arguments to Unity scripts
- Parse and categorize Unity log output
- Comprehensive error handling for:
  - Unity not found
  - Compilation errors
  - Method execution failures
  - Runtime errors
- Proper logging using loguru

The UnityBatchMode class wraps Unity CLI and provides type-safe, testable
interfaces for running export scripts. It's designed to work with the
ExportBatch.cs entry point and other Unity Editor scripts.
"""

import re
import subprocess
from pathlib import Path
from typing import Literal

from loguru import logger

from erenshor.infrastructure.time import Clock, RealClock


class UnityBatchModeError(Exception):
    """Base exception for Unity batch mode errors.

    This is the parent exception for all Unity-specific errors.
    Catch this to handle all Unity batch mode failures.
    """

    pass


class UnityNotFoundError(UnityBatchModeError):
    """Raised when Unity executable is not found.

    This typically means Unity is not installed at the expected path
    or the configured path is incorrect.
    """

    pass


class UnityCompilationError(UnityBatchModeError):
    """Raised when Unity script compilation fails.

    This occurs when:
    - C# syntax errors in Editor scripts
    - Missing assembly references
    - Invalid Unity API usage
    - Type resolution failures
    """

    pass


class UnityExecutionError(UnityBatchModeError):
    """Raised when Unity method execution fails to start.

    This can occur due to:
    - Method not found
    - Method is not static
    - Method has invalid signature
    - Class not found
    """

    pass


class UnityRuntimeError(UnityBatchModeError):
    """Raised when Unity script execution fails at runtime.

    This occurs when:
    - Exceptions thrown in C# code
    - Database errors
    - File I/O errors
    - Asset loading failures
    """

    pass


LogLevel = Literal["quiet", "normal", "verbose"]


class UnityBatchMode:
    """Wrapper for Unity Editor batch mode execution.

    This class provides a Python interface to Unity Editor's batch mode,
    allowing execution of static C# methods in a headless Unity environment.
    It's specifically designed for running export scripts that generate
    game data from Unity assets.

    Attributes:
        unity_path: Path to Unity Editor executable.
        timeout: Maximum execution time in seconds.

    Example:
        >>> # Execute export batch script
        >>> unity = UnityBatchMode(
        ...     unity_path=Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"),
        ...     timeout=3600
        ... )
        >>> unity.execute_method(
        ...     project_path=Path("variants/main/unity"),
        ...     class_name="ExportBatch",
        ...     method_name="Run",
        ...     log_file=Path("logs/export.log"),
        ...     arguments={
        ...         "dbPath": "/path/to/output.sqlite",
        ...         "entities": "items,spells,characters",
        ...         "logLevel": "verbose"
        ...     }
        ... )

        >>> # Execute custom static method
        >>> unity.execute_method(
        ...     project_path=Path("variants/main/unity"),
        ...     class_name="MyExporter",
        ...     method_name="CustomExport",
        ...     log_file=Path("logs/custom.log")
        ... )
    """

    def __init__(
        self,
        unity_path: Path,
        timeout: int = 3600,
        clock: Clock | None = None,
    ) -> None:
        """Initialize Unity batch mode wrapper.

        Args:
            unity_path: Path to Unity Editor executable (must exist).
            timeout: Maximum execution time in seconds (default: 3600).
            clock: Clock implementation for time operations (default: RealClock()).

        Raises:
            UnityNotFoundError: If Unity executable is not found.
        """
        self.unity_path = unity_path
        self.timeout = timeout
        self.clock = clock if clock is not None else RealClock()

        # Verify Unity exists and is executable
        if not self.unity_path.exists():
            raise UnityNotFoundError(
                f"Unity executable not found at: {self.unity_path}\n"
                "Verify Unity is installed and path is correct in config.toml"
            )

        if not self.unity_path.is_file():
            raise UnityNotFoundError(f"Unity path is not a file: {self.unity_path}")

        logger.debug(f"Unity batch mode initialized: path={unity_path}, timeout={timeout}s")

    def execute_method(
        self,
        project_path: Path,
        class_name: str,
        method_name: str,
        log_file: Path | None = None,
        arguments: dict[str, str] | None = None,
    ) -> None:
        """Execute a static C# method in Unity batch mode.

        Runs Unity Editor in headless batch mode to execute a specific static
        method. The method must be accessible from Unity Editor (typically in
        an Editor assembly) and must be static with no parameters.

        Unity command-line arguments can be passed via the arguments dict.
        These will be available to C# code via Environment.GetCommandLineArgs().

        Args:
            project_path: Path to Unity project directory (must exist).
            class_name: C# class name containing the method.
            method_name: Static method name to execute.
            log_file: Optional path for Unity log output (default: creates temp file).
            arguments: Optional command-line arguments for the C# method.

        Raises:
            UnityNotFoundError: If project path doesn't exist.
            UnityCompilationError: If C# compilation fails.
            UnityExecutionError: If method execution fails to start.
            UnityRuntimeError: If method execution fails at runtime.

        Example:
            >>> unity = UnityBatchMode(unity_path=Path("/path/to/Unity"))
            >>> unity.execute_method(
            ...     project_path=Path("variants/main/unity"),
            ...     class_name="ExportBatch",
            ...     method_name="Run",
            ...     log_file=Path("logs/export.log"),
            ...     arguments={
            ...         "dbPath": "/path/to/output.sqlite",
            ...         "entities": "items,spells",
            ...         "logLevel": "verbose"
            ...     }
            ... )
        """
        logger.info(f"Executing Unity method: {class_name}.{method_name}")
        logger.debug(f"Project: {project_path}")
        logger.debug(f"Arguments: {arguments}")

        # Validate project path
        if not project_path.exists():
            raise UnityNotFoundError(f"Unity project not found: {project_path}")

        if not project_path.is_dir():
            raise UnityNotFoundError(f"Unity project path is not a directory: {project_path}")

        # Create log file if not provided
        if log_file is None:
            log_file = Path(f"unity_batch_{class_name}_{method_name}.log")

        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Build Unity command
        cmd = [
            str(self.unity_path),
            "-batchmode",
            "-quit",
            "-projectPath",
            str(project_path.absolute()),
            "-executeMethod",
            f"{class_name}.{method_name}",
            "-logFile",
            str(log_file.absolute()),
        ]

        # Add custom arguments
        if arguments:
            for key, value in arguments.items():
                cmd.extend([f"-{key}", value])

        logger.debug(f"Executing Unity: {' '.join(cmd)}")

        # Execute Unity in background and monitor progress
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            logger.info("Monitoring Unity export progress...")

            # Monitor progress by checking log file periodically
            start_time = self.clock.time()
            last_update = 0

            while True:
                # Check if process has finished
                returncode = process.poll()
                if returncode is not None:
                    logger.info("Unity export completed")
                    break

                # Show progress every 30 seconds
                elapsed = int(self.clock.time() - start_time)
                if elapsed - last_update >= 30:
                    logger.info(f"Still exporting... ({elapsed}s elapsed)")
                    last_update = elapsed

                # Check for timeout
                if elapsed > self.timeout:
                    process.kill()
                    logger.error(f"Unity execution timed out after {self.timeout}s")
                    raise UnityRuntimeError(
                        f"Unity execution timed out after {self.timeout} seconds.\n"
                        f"Check log file: {log_file}\n"
                        "Consider increasing timeout in config.toml"
                    )

                self.clock.sleep(5)  # Check every 5 seconds

            # Parse log file for errors
            self._check_execution_result(returncode, log_file)

            logger.info("Unity execution completed successfully")
            logger.debug(f"Log file: {log_file}")

        except FileNotFoundError as e:
            raise UnityNotFoundError(f"Unity executable not found: {self.unity_path}") from e

    def _check_execution_result(self, exit_code: int, log_file: Path) -> None:
        """Check Unity execution result for errors.

        Parses Unity log file to detect compilation errors, execution errors,
        and runtime errors. Raises appropriate exceptions with error details.

        Args:
            exit_code: Unity process exit code.
            log_file: Path to Unity log file.

        Raises:
            UnityCompilationError: If compilation failed.
            UnityExecutionError: If method execution failed to start.
            UnityRuntimeError: If runtime error occurred.
        """
        # Exit code 0 = success, 1 = error
        if exit_code == 0:
            logger.debug(f"Unity exited with success code: {exit_code}")
            return

        # Read log file for error details
        if not log_file.exists():
            logger.warning(f"Unity log file not found: {log_file}")
            raise UnityRuntimeError(
                f"Unity execution failed with exit code {exit_code}, but log file is missing.\n"
                f"Expected log: {log_file}"
            )

        log_content = log_file.read_text()

        # Check for compilation errors
        if self._has_compilation_error(log_content):
            error_details = self._extract_compilation_errors(log_content)
            logger.error(f"Unity compilation failed: {error_details}")
            raise UnityCompilationError(
                f"Unity script compilation failed.\n" f"Check log file: {log_file}\n" f"Errors:\n{error_details}"
            )

        # Check for method execution errors
        if self._has_execution_error(log_content):
            error_details = self._extract_execution_error(log_content)
            logger.error(f"Unity method execution failed: {error_details}")
            raise UnityExecutionError(
                f"Failed to execute Unity method.\n" f"Check log file: {log_file}\n" f"Error: {error_details}"
            )

        # Check for export errors first (most specific)
        if "[EXPORT_ERROR]" in log_content:
            error_details = self._extract_export_error(log_content)
            logger.error(f"Unity export error: {error_details}")
            raise UnityRuntimeError(
                f"Unity export script failed.\n" f"Check log file: {log_file}\n" f"Error:\n{error_details}"
            )

        # Check for licensing errors (before generic runtime errors)
        if self._has_licensing_error(log_content):
            logger.error("Unity licensing error detected")
            raise UnityRuntimeError(
                "Unity licensing validation failed.\n"
                "\n"
                "This typically happens when Unity's license needs to be refreshed.\n"
                "\n"
                "Solution:\n"
                "  • Start Unity Hub (this refreshes the license automatically)\n"
                "  • Then retry the export command\n"
                "\n"
                "If that doesn't work, check Unity Hub > Preferences > Licenses\n"
                "\n"
                f"Log file: {log_file}\n"
                "\n"
                "Note: Unity Personal (free) requires periodic license validation."
            )

        # Check for runtime errors (exceptions, generic errors)
        if self._has_runtime_error(log_content):
            error_details = self._extract_runtime_errors(log_content)
            logger.error(f"Unity runtime error: {error_details}")
            raise UnityRuntimeError(
                f"Unity script execution failed.\n" f"Check log file: {log_file}\n" f"Errors:\n{error_details}"
            )

        # Generic error if we can't determine cause
        logger.error(f"Unity failed with exit code {exit_code} (cause unknown)")
        raise UnityRuntimeError(
            f"Unity execution failed with exit code {exit_code}.\n" f"Check log file for details: {log_file}"
        )

    def _has_compilation_error(self, log_content: str) -> bool:
        """Check if log contains compilation errors.

        Args:
            log_content: Unity log file content.

        Returns:
            True if compilation errors detected, False otherwise.
        """
        compilation_markers = [
            "Compilation failed:",
            "error CS",  # C# compiler errors
            "Assembly has reference to non-existent assembly",
            "The type or namespace",
            "does not contain a definition for",
        ]
        return any(marker in log_content for marker in compilation_markers)

    def _has_execution_error(self, log_content: str) -> bool:
        """Check if log contains method execution errors.

        Args:
            log_content: Unity log file content.

        Returns:
            True if execution errors detected, False otherwise.
        """
        execution_markers = [
            "Executing method failed",
            "Method or operation is not found",
            "Could not execute the method",
        ]
        return any(marker in log_content for marker in execution_markers)

    def _has_licensing_error(self, log_content: str) -> bool:
        """Check if log contains Unity licensing errors that caused failure.

        Only returns True if licensing errors exist AND licensing didn't ultimately succeed.
        Transient licensing errors that resolve are ignored.

        Args:
            log_content: Unity log file content.

        Returns:
            True if licensing failed, False otherwise.
        """
        # Check for licensing error markers
        licensing_error_markers = [
            "[Licensing::Client] Error:",
            "[Licensing::Module] Error:",
            "No ULF license found",
            "Access token is unavailable",
            "LicensingClient has failed validation",
        ]
        has_licensing_errors = any(marker in log_content for marker in licensing_error_markers)

        # Check for licensing success markers
        licensing_success_markers = [
            "Successfully updated license",
            "Successfully resolved entitlement details",
            "Serial number assigned to:",
        ]
        has_licensing_success = any(marker in log_content for marker in licensing_success_markers)

        # Only report licensing error if we saw errors but NO success
        return has_licensing_errors and not has_licensing_success

    def _has_runtime_error(self, log_content: str) -> bool:
        """Check if log contains runtime errors.

        Args:
            log_content: Unity log file content.

        Returns:
            True if runtime errors detected, False otherwise.
        """
        runtime_markers = [
            "[EXPORT_ERROR]",  # Custom error marker from ExportBatch.cs
            "Exception:",
            "Error:",
            "NullReferenceException",
            "ArgumentException",
            "InvalidOperationException",
        ]
        return any(marker in log_content for marker in runtime_markers)

    def _extract_compilation_errors(self, log_content: str) -> str:
        """Extract compilation error details from log.

        Args:
            log_content: Unity log file content.

        Returns:
            Formatted compilation error details.
        """
        lines = log_content.splitlines()
        error_lines = []

        for line in lines:
            # Extract C# compiler errors (e.g., "error CS0246: The type...")
            if "error CS" in line:
                error_lines.append(line.strip())

        return "\n".join(error_lines) if error_lines else "Compilation failed (see log for details)"

    def _extract_execution_error(self, log_content: str) -> str:
        """Extract method execution error details from log.

        Args:
            log_content: Unity log file content.

        Returns:
            Formatted execution error details.
        """
        lines = log_content.splitlines()

        for line in lines:
            if "Executing method failed" in line or "Could not execute" in line:
                return line.strip()

        return "Method execution failed (see log for details)"

    def _extract_export_error(self, log_content: str) -> str:
        """Extract export error details from log.

        Args:
            log_content: Unity log file content.

        Returns:
            Formatted export error details.
        """
        lines = log_content.splitlines()

        for line in lines:
            if "[EXPORT_ERROR]" in line:
                # Extract just the error message after the marker
                return line.split("[EXPORT_ERROR]", 1)[1].strip()

        return "Export failed (see log for details)"

    def _extract_runtime_errors(self, log_content: str) -> str:
        """Extract runtime error details from log.

        Args:
            log_content: Unity log file content.

        Returns:
            Formatted runtime error details.
        """
        lines = log_content.splitlines()
        error_lines = []

        # Look for custom error markers
        for i, line in enumerate(lines):
            if "[EXPORT_ERROR]" in line:
                error_lines.append(line.strip())
                # Include next few lines for context
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip():
                        error_lines.append(lines[j].strip())

        # If no custom markers, look for exceptions
        if not error_lines:
            for i, line in enumerate(lines):
                if "Exception:" in line or "Error:" in line:
                    error_lines.append(line.strip())
                    # Include stack trace (next few lines)
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if lines[j].strip() and ("at " in lines[j] or "  in " in lines[j]):
                            error_lines.append(lines[j].strip())
                        elif not lines[j].strip():
                            break

        return "\n".join(error_lines) if error_lines else "Runtime error (see log for details)"

    def validate_project(self, project_path: Path) -> bool:
        """Validate that a Unity project has the required structure.

        Checks for essential Unity project directories and files.

        Args:
            project_path: Path to Unity project directory.

        Returns:
            True if project is valid, False otherwise.

        Example:
            >>> unity = UnityBatchMode(unity_path=Path("/path/to/Unity"))
            >>> if unity.validate_project(Path("variants/main/unity")):
            ...     print("Project is valid")
            ... else:
            ...     print("Project is invalid")
        """
        if not project_path.exists():
            logger.debug(f"Project path does not exist: {project_path}")
            return False

        # Check for essential Unity directories
        required_dirs = [
            project_path / "Assets",
            project_path / "ProjectSettings",
        ]

        for required_dir in required_dirs:
            if not required_dir.exists():
                logger.debug(f"Missing required directory: {required_dir}")
                return False

        logger.debug(f"Unity project validation passed: {project_path}")
        return True

    def get_version(self) -> str:
        """Get Unity Editor version.

        Extracts Unity version from the executable path. Unity versions
        follow the format: YYYY.X.YYfZ (e.g., 2021.3.45f2).

        Returns:
            Unity version string.

        Raises:
            UnityNotFoundError: If version cannot be detected from path.

        Example:
            >>> unity = UnityBatchMode(
            ...     unity_path=Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app")
            ... )
            >>> print(unity.get_version())
            2021.3.45f2
        """
        # Extract version from path (e.g., "2021.3.45f2")
        path_str = str(self.unity_path)
        version_pattern = r"(\d{4}\.\d+\.\d+[a-z]\d+)"
        match = re.search(version_pattern, path_str)

        if not match:
            raise UnityNotFoundError(
                f"Could not detect Unity version from path: {self.unity_path}\n"
                "Unity path must contain version number (e.g., 2021.3.45f2)\n"
                "Example valid path: /Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app"
            )

        version = match.group(1)
        logger.debug(f"Unity version detected: {version}")
        return version

    def is_installed(self) -> bool:
        """Check if Unity is properly installed and accessible.

        Returns:
            True if Unity executable exists and is accessible, False otherwise.

        Example:
            >>> unity = UnityBatchMode(unity_path=Path("/path/to/Unity"))
            >>> if unity.is_installed():
            ...     print("Unity is installed")
            ... else:
            ...     print("Unity not found")
        """
        is_installed = self.unity_path.exists() and self.unity_path.is_file()
        logger.debug(f"Unity installation check: {is_installed} (path={self.unity_path})")
        return is_installed
