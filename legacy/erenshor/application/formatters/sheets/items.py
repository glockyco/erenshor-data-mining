"""Formatter for Google Sheets export.

This module provides formatters that execute SQL queries from the queries directory
and format the results as spreadsheet rows ready for Google Sheets API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

__all__ = [
    "SheetsFormatter",
]


class SheetsFormatter:
    """Format database query results as spreadsheet rows.

    This formatter executes SQL queries from individual .sql files in the queries directory
    and converts the results into a format suitable for Google Sheets API:
    - First row: Column headers
    - Subsequent rows: Data rows

    The formatter handles data type conversion:
    - Booleans → "TRUE"/"FALSE" strings
    - None → empty string
    - Numbers → preserved as-is
    - Strings → preserved as-is
    """

    def __init__(self, engine: Engine, queries_dir: Path):
        """Initialize formatter.

        Args:
            engine: SQLAlchemy database engine
            queries_dir: Path to directory containing .sql query files
        """
        self.engine = engine
        self.queries_dir = queries_dir

    def get_sheet_names(self) -> List[str]:
        """Get list of all available sheet names.

        Returns:
            List of sheet names from .sql files in queries directory
        """
        if not self.queries_dir.exists():
            return []

        # Get all .sql files and return their names without extension
        sql_files = sorted(self.queries_dir.glob("*.sql"))
        return [f.stem for f in sql_files]

    def format_sheet(self, sheet_name: str) -> List[List[Any]]:
        """Execute query and format results as spreadsheet rows.

        Args:
            sheet_name: Name of the sheet (e.g., 'items', 'characters')

        Returns:
            List of rows, where first row is headers and subsequent rows are data

        Raises:
            ValueError: If sheet_name.sql not found in queries directory
        """
        sql_file = self.queries_dir / f"{sheet_name}.sql"

        if not sql_file.exists():
            available = ", ".join(self.get_sheet_names())
            raise ValueError(
                f"Query file '{sheet_name}.sql' not found in {self.queries_dir}. "
                f"Available sheets: {available}"
            )

        # Read query from file
        query_sql = sql_file.read_text(encoding="utf-8").strip()

        if not query_sql:
            raise ValueError(f"Query file '{sheet_name}.sql' is empty")

        return self._execute_and_format(query_sql)

    def format_all_sheets(self) -> Dict[str, List[List[Any]]]:
        """Execute all queries and format results.

        Returns:
            Dictionary mapping sheet names to formatted rows
        """
        results = {}
        for sheet_name in self.get_sheet_names():
            results[sheet_name] = self.format_sheet(sheet_name)
        return results

    def _execute_and_format(self, query: str) -> List[List[Any]]:
        """Execute SQL query and format results as rows.

        Args:
            query: SQL query to execute

        Returns:
            List of rows with headers as first row
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(query))

            # Get column names from result
            headers = list(result.keys())

            # Fetch all data rows
            data_rows = []
            for row in result:
                formatted_row = [self._format_value(val) for val in row]
                data_rows.append(formatted_row)

        # Combine headers and data
        return [headers] + data_rows

    def _format_value(self, value: Any) -> Any:
        """Format a single cell value for Google Sheets.

        Args:
            value: Raw value from database

        Returns:
            Formatted value suitable for Google Sheets
        """
        if value is None:
            return ""
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return value
        # Everything else as string
        return str(value)

    def get_row_count(self, sheet_name: str) -> int:
        """Get the number of data rows (excluding header) for a sheet.

        Args:
            sheet_name: Name of the sheet

        Returns:
            Number of data rows
        """
        rows = self.format_sheet(sheet_name)
        return len(rows) - 1  # Subtract header row
