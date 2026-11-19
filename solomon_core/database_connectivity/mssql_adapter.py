# ------------------------------------------------------------------
# FILE: mssql_adapter.py
# DIRECTORY: solomon_core/database_connectivity/
# ------------------------------------------------------------------
# Microsoft SQL Server adapter for the generic external-database contract.
# ------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from config import settings

from .contracts import (
    ApprovedReadQuery,
    DatabaseAdapterError,
    DatabaseHealth,
    ReadFilter,
    ReadOrder,
)


_IDENTIFIER_PART_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALLOWED_FILTER_OPERATORS = {"eq", "contains", "in", "not_in", "is_null", "is_not_null"}
_ALLOWED_ORDER_DIRECTIONS = {"asc", "desc"}


@dataclass(frozen=True)
class MssqlAdapterConfig:
    driver: str
    server: str
    database: str
    username: str
    password: str
    encrypt: bool = True
    trust_server_certificate: bool = True
    connect_timeout_seconds: int = 3
    query_timeout_seconds: int = 8
    max_rows: int = 100

    @classmethod
    def from_settings(cls) -> "MssqlAdapterConfig":
        return cls(
            driver=str(settings.EXTERNAL_DATABASE_MSSQL_DRIVER or "").strip(),
            server=str(settings.EXTERNAL_DATABASE_MSSQL_SERVER or "").strip(),
            database=str(settings.EXTERNAL_DATABASE_MSSQL_DATABASE or "").strip(),
            username=str(settings.EXTERNAL_DATABASE_MSSQL_USERNAME or "").strip(),
            password=str(settings.EXTERNAL_DATABASE_MSSQL_PASSWORD or ""),
            encrypt=bool(settings.EXTERNAL_DATABASE_MSSQL_ENCRYPT),
            trust_server_certificate=bool(
                settings.EXTERNAL_DATABASE_MSSQL_TRUST_SERVER_CERTIFICATE
            ),
            connect_timeout_seconds=int(
                settings.EXTERNAL_DATABASE_CONNECT_TIMEOUT_SECONDS
            ),
            query_timeout_seconds=int(
                settings.EXTERNAL_DATABASE_QUERY_TIMEOUT_SECONDS
            ),
            max_rows=int(settings.EXTERNAL_DATABASE_MAX_ROWS),
        )


class MssqlExternalDatabaseAdapter:
    """Bounded, parameterized, read-only SQL Server adapter."""

    engine = "mssql"

    def __init__(
        self,
        *,
        source_id: str,
        config: MssqlAdapterConfig | None = None,
    ) -> None:
        self.source_id = str(source_id or "").strip()
        self.config = config or MssqlAdapterConfig.from_settings()

    def _connection_string(self) -> str:
        encrypt = "yes" if self.config.encrypt else "no"
        trust = "yes" if self.config.trust_server_certificate else "no"
        return (
            f"DRIVER={{{self.config.driver}}};"
            f"SERVER={self.config.server};"
            f"DATABASE={self.config.database};"
            f"UID={self.config.username};"
            f"PWD={self.config.password};"
            f"Encrypt={encrypt};"
            f"TrustServerCertificate={trust};"
        )

    @staticmethod
    def _exception_text(exc: BaseException) -> str:
        parts = [str(exc)]
        for item in getattr(exc, "args", ()) or ():
            parts.append(str(item))
        return " | ".join(parts).upper()

    @classmethod
    def _classify_exception(
        cls,
        exc: BaseException,
        *,
        during_connect: bool,
    ) -> DatabaseAdapterError:
        text = cls._exception_text(exc)

        if "HYT00" in text or "HYT01" in text or "TIMEOUT" in text or "TIMED OUT" in text:
            return DatabaseAdapterError(
                "EXTERNAL_DATABASE_TIMEOUT",
                "The external database operation timed out.",
            )

        if "28000" in text or "18456" in text or "LOGIN FAILED" in text:
            return DatabaseAdapterError(
                "EXTERNAL_DATABASE_AUTHENTICATION_FAILED",
                "The external database rejected the configured connector identity.",
            )

        if "229" in text or "PERMISSION" in text or "DENIED" in text:
            return DatabaseAdapterError(
                "EXTERNAL_DATABASE_ACCESS_DENIED",
                "The configured connector identity is not authorized for this database operation.",
            )

        if during_connect:
            return DatabaseAdapterError(
                "EXTERNAL_DATABASE_UNAVAILABLE",
                "The configured external database is unavailable.",
            )

        return DatabaseAdapterError(
            "EXTERNAL_DATABASE_QUERY_FAILED",
            "The approved external database read failed.",
        )

    def _connect(self):
        required = (
            self.config.driver,
            self.config.server,
            self.config.database,
            self.config.username,
            self.config.password,
        )
        if not self.source_id or not all(str(value or "").strip() for value in required):
            raise DatabaseAdapterError(
                "EXTERNAL_DATABASE_CONFIG_INVALID",
                "External SQL Server configuration is incomplete.",
            )

        if self.config.connect_timeout_seconds <= 0 or self.config.query_timeout_seconds <= 0:
            raise DatabaseAdapterError(
                "EXTERNAL_DATABASE_CONFIG_INVALID",
                "External SQL Server timeout configuration is invalid.",
            )

        try:
            import pyodbc
        except Exception as exc:  # pragma: no cover - live environment guard
            raise DatabaseAdapterError(
                "EXTERNAL_DATABASE_DRIVER_UNAVAILABLE",
                "The configured SQL Server Python driver is unavailable.",
            ) from exc

        try:
            connection = pyodbc.connect(
                self._connection_string(),
                timeout=int(self.config.connect_timeout_seconds),
                autocommit=False,
            )
            connection.timeout = int(self.config.query_timeout_seconds)
            return connection
        except Exception as exc:
            raise self._classify_exception(exc, during_connect=True) from exc

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, (bytes, bytearray, memoryview)):
            return {
                "binary_omitted": True,
                "size_bytes": len(bytes(value)),
            }
        if isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @staticmethod
    def _quote_identifier(identifier: str, *, allow_qualified: bool = False) -> str:
        clean = str(identifier or "").strip()
        parts = clean.split(".") if allow_qualified else [clean]
        if not clean or any(not _IDENTIFIER_PART_RE.fullmatch(part) for part in parts):
            raise DatabaseAdapterError(
                "EXTERNAL_DATABASE_READ_PLAN_INVALID",
                f"Invalid database identifier in approved read plan: {clean or '<empty>'}",
            )
        return ".".join(f"[{part}]" for part in parts)

    @classmethod
    def _compile_filter(cls, item: ReadFilter) -> Tuple[str, List[Any]]:
        column = cls._quote_identifier(item.column)
        operator = str(item.operator or "").strip().lower()
        if operator not in _ALLOWED_FILTER_OPERATORS:
            raise DatabaseAdapterError(
                "EXTERNAL_DATABASE_READ_PLAN_INVALID",
                f"Unsupported approved-read filter operator: {operator or '<empty>'}",
            )

        if operator == "eq":
            return f"{column} = ?", [item.value]

        if operator == "contains":
            return f"{column} LIKE ?", [f"%{str(item.value or '')}%"]

        if operator in {"in", "not_in"}:
            values = tuple(item.value or ()) if isinstance(item.value, (list, tuple, set)) else ()
            if not values:
                raise DatabaseAdapterError(
                    "EXTERNAL_DATABASE_READ_PLAN_INVALID",
                    f"Approved-read {operator} filter requires at least one value.",
                )
            placeholders = ", ".join("?" for _ in values)
            keyword = "IN" if operator == "in" else "NOT IN"
            return f"{column} {keyword} ({placeholders})", list(values)

        if operator == "is_null":
            return f"{column} IS NULL", []

        if operator == "is_not_null":
            return f"{column} IS NOT NULL", []

        raise DatabaseAdapterError(
            "EXTERNAL_DATABASE_READ_PLAN_INVALID",
            "Unsupported approved-read filter operator.",
        )

    @classmethod
    def _compile_read(
        cls,
        query: ApprovedReadQuery,
        *,
        global_max_rows: int,
    ) -> Tuple[str, Tuple[Any, ...], int]:
        if not isinstance(query, ApprovedReadQuery):
            raise DatabaseAdapterError(
                "EXTERNAL_DATABASE_READ_PLAN_INVALID",
                "External database reads require an approved read plan.",
            )

        relation = cls._quote_identifier(query.relation, allow_qualified=True)
        columns = tuple(str(value or "").strip() for value in (query.columns or ()))
        if not columns:
            raise DatabaseAdapterError(
                "EXTERNAL_DATABASE_READ_PLAN_INVALID",
                "Approved read plan must select explicit columns.",
            )
        rendered_columns = ", ".join(cls._quote_identifier(column) for column in columns)

        requested_rows = int(query.max_rows or 0)
        hard_cap = int(global_max_rows or 0)
        if requested_rows <= 0 or hard_cap <= 0:
            raise DatabaseAdapterError(
                "EXTERNAL_DATABASE_READ_PLAN_INVALID",
                "Approved read plan row limits must be greater than zero.",
            )
        row_limit = min(requested_rows, hard_cap)

        required_sql: List[str] = []
        match_any_sql: List[str] = []
        parameters: List[Any] = []

        for item in query.required_filters or ():
            sql, values = cls._compile_filter(item)
            required_sql.append(sql)
            parameters.extend(values)

        match_any_parameters: List[Any] = []
        for item in query.match_any_filters or ():
            sql, values = cls._compile_filter(item)
            match_any_sql.append(sql)
            match_any_parameters.extend(values)

        where_parts: List[str] = []
        if match_any_sql:
            where_parts.append("(" + " OR ".join(match_any_sql) + ")")
            parameters = match_any_parameters + parameters
        if required_sql:
            where_parts.extend(required_sql)

        sql = f"SELECT TOP ({row_limit}) {rendered_columns} FROM {relation}"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)

        if query.order_by:
            order_terms = []
            for item in query.order_by:
                if not isinstance(item, ReadOrder):
                    raise DatabaseAdapterError(
                        "EXTERNAL_DATABASE_READ_PLAN_INVALID",
                        "Approved read ordering must use ReadOrder entries.",
                    )
                direction = str(item.direction or "asc").strip().lower()
                if direction not in _ALLOWED_ORDER_DIRECTIONS:
                    raise DatabaseAdapterError(
                        "EXTERNAL_DATABASE_READ_PLAN_INVALID",
                        f"Unsupported approved-read order direction: {direction}",
                    )
                order_terms.append(
                    f"{cls._quote_identifier(item.column)} {direction.upper()}"
                )
            sql += " ORDER BY " + ", ".join(order_terms)

        return sql, tuple(parameters), row_limit

    def health(self) -> DatabaseHealth:
        try:
            connection = self._connect()
            try:
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)) AS server_name, "
                    "DB_NAME() AS database_name"
                )
                row = cursor.fetchone()
                return DatabaseHealth(
                    ok=True,
                    engine=self.engine,
                    source_id=self.source_id,
                    database=str(row.database_name if row else self.config.database),
                    server=str(row.server_name if row else self.config.server),
                    status="ready",
                )
            finally:
                connection.rollback()
                connection.close()
        except DatabaseAdapterError as exc:
            return DatabaseHealth(
                ok=False,
                engine=self.engine,
                source_id=self.source_id,
                database=self.config.database,
                server=self.config.server,
                status="unavailable",
                detail=exc.code,
            )

    def execute_read(self, query: ApprovedReadQuery) -> List[Dict[str, Any]]:
        statement, parameters, row_limit = self._compile_read(
            query,
            global_max_rows=int(self.config.max_rows),
        )
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(statement, parameters)
            columns = [str(item[0]) for item in (cursor.description or [])]
            rows: List[Dict[str, Any]] = []
            for raw_row in cursor.fetchmany(row_limit):
                rows.append(
                    {
                        columns[index]: self._normalize_value(value)
                        for index, value in enumerate(raw_row)
                    }
                )
            return rows
        except DatabaseAdapterError:
            raise
        except Exception as exc:
            raise self._classify_exception(exc, during_connect=False) from exc
        finally:
            try:
                connection.rollback()
            finally:
                connection.close()
