"""Apollo (SQL Server) access.

Read-only. Every query is parameterised: the MBN arrives from a text box and the
original pasted it straight into the SQL string.

The application talks to the ``ApolloClient`` protocol, so the golden regression
test can substitute recorded results without a database.
"""
from __future__ import annotations

import threading
import time
from typing import Protocol, Sequence

from .models import PbiSample, QcRecord

#: Preferred first, oldest last. The original pinned "SQL Server Native Client
#: 10.0", which is long out of support and absent from current Windows images;
#: if it disappears from a workstation the app should keep working.
DRIVER_PREFERENCES = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 13.1 for SQL Server",
    "ODBC Driver 13 for SQL Server",
    "ODBC Driver 11 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server Native Client 10.0",
    "SQL Server",
)

VALIDATE_MBN_SQL = "select top 1 1 from pb where mbatch = ? and bact = 1"

PBI_SQL = (
    "select pspecno, pcont, mbatch from pbi "
    "join pb on pb.batch = pbi.batch and pb.befdt = pbi.befdt "
    "where mbatch = ? and bact = 1 and qcid = '' and pspecno <> ''"
)

QC_SQL = (
    "select kqcruni.qcid, kqcruni.qcspecno from pb "
    "join kqcrun on pb.pbbqcrun = kqcrun.qcrun "
    "join kqcruni on kqcrun.qcrun = kqcruni.qcrun "
    "and kqcrun.qcrefdt = kqcruni.qcrefdt "
    "where bact = 1 and mbatch = ? and pb.wl = kqcruni.wl"
)


class ApolloError(Exception):
    """Apollo could not be reached or a query failed."""


class ApolloClient(Protocol):
    def mbn_exists(self, mbn: str) -> bool: ...
    def pbi_samples(self, mbn: str) -> list[PbiSample]: ...
    def qc_records(self, mbn: str) -> list[QcRecord]: ...


def available_driver(preferred: str | None = None) -> str:
    """Pick an installed ODBC driver, preferring the configured one."""
    try:
        import pyodbc
    except ImportError as exc:
        raise ApolloError(
            "pyodbc is not installed, so Apollo cannot be reached."
        ) from exc

    installed = set(pyodbc.drivers())
    if preferred and preferred in installed:
        return preferred
    for name in DRIVER_PREFERENCES:
        if name in installed:
            return name
    raise ApolloError(
        "No SQL Server ODBC driver is installed on this machine. Install the "
        "Microsoft ODBC Driver for SQL Server. Drivers found: "
        + (", ".join(sorted(installed)) or "none")
    )


class SqlServerApolloClient:
    """Live read-only connection to Apollo.

    The connection is opened lazily on first use, not at import. The original
    connected at module scope, so an unreachable server meant the application
    would not start at all and the analyst saw nothing.
    """

    def __init__(self, server: str, database: str, uid: str, pwd: str,
                 driver: str | None = None, timeout: int = 10):
        self._server = server
        self._database = database
        self._uid = uid
        self._pwd = pwd
        self._driver = driver
        self._timeout = timeout
        self._cnxn = None

    @property
    def description(self) -> str:
        return f"{self._database} on {self._server}"

    def connect(self):
        if self._cnxn is not None:
            return self._cnxn
        try:
            import pyodbc
        except ImportError as exc:
            # available_driver() converts this too, but connect() must not let a
            # raw ImportError escape: callers only guard against ApolloError, so
            # anything else takes the whole application down.
            raise ApolloError(
                "pyodbc is not installed, so Apollo cannot be reached. The "
                "application still runs; plate files can be loaded and checked."
            ) from exc

        driver = available_driver(self._driver)
        parts = [
            f"Driver={{{driver}}}",
            f"Server={self._server}",
            f"Database={self._database}",
            f"UID={self._uid}",
            f"PWD={self._pwd}",
        ]
        if driver.startswith("ODBC Driver"):
            # Older drivers reject this attribute outright rather than ignoring
            # it, which turns a working connection into a confusing failure.
            parts.append("TrustServerCertificate=yes")
        try:
            self._cnxn = pyodbc.connect(
                ";".join(parts) + ";",
                timeout=self._timeout,
                readonly=True,
            )
        except Exception as exc:
            raise ApolloError(
                f"Could not connect to Apollo ({self.description}) using "
                f"{driver}. Check that this machine is on the lab network. ({exc})"
            ) from exc
        return self._cnxn

    def check(self) -> None:
        """Open the connection now so startup can report a clear failure."""
        self.connect()

    def _rows(self, sql: str, *params) -> list[tuple]:
        cursor = self.connect().cursor()
        try:
            cursor.execute(sql, *params)
            return [tuple(r) for r in cursor.fetchall()]
        except Exception as exc:
            raise ApolloError(f"Apollo query failed: {exc}") from exc
        finally:
            cursor.close()

    def mbn_exists(self, mbn: str) -> bool:
        return bool(self._rows(VALIDATE_MBN_SQL, mbn))

    def pbi_samples(self, mbn: str) -> list[PbiSample]:
        return [PbiSample(str(a).strip(), str(b).strip(), str(c).strip())
                for a, b, c in self._rows(PBI_SQL, mbn)]

    def qc_records(self, mbn: str) -> list[QcRecord]:
        return [QcRecord(str(a).strip(), str(b).strip())
                for a, b in self._rows(QC_SQL, mbn)]

    def close(self) -> None:
        if self._cnxn is not None:
            try:
                self._cnxn.close()
            finally:
                self._cnxn = None


class RecordedApolloClient:
    """Replays recorded query results. Used by the regression tests."""

    def __init__(self, valid_mbns: Sequence[str],
                 pbi: Sequence[PbiSample],
                 qc: dict[str, Sequence[QcRecord]]):
        self._valid = set(valid_mbns)
        self._pbi = list(pbi)
        self._qc = {k: list(v) for k, v in qc.items()}

    description = "recorded fixture"

    def check(self) -> None:
        return None

    def mbn_exists(self, mbn: str) -> bool:
        return mbn in self._valid

    def pbi_samples(self, mbn: str) -> list[PbiSample]:
        return [s for s in self._pbi if s.mbatch == mbn]

    def qc_records(self, mbn: str) -> list[QcRecord]:
        return list(self._qc.get(mbn, []))


class HealthProbe:
    """Checks Apollo on a background thread and caches the answer.

    Connecting to an unreachable server can block for a long time -- far longer
    than any configured login timeout, since name resolution happens first. That
    must never happen on the request thread: a blocked probe would hold a
    worker, and a browser that retries would hold all of them.
    """

    #: How long a good result stays fresh before it is checked again.
    TTL_OK = 120.0
    #: Failures are retried sooner, so a reconnect is noticed quickly.
    TTL_BAD = 20.0

    def __init__(self, client):
        self._client = client
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._state = "checking"
        self._error: str | None = None
        self._checked_at = 0.0

    @property
    def description(self) -> str:
        return getattr(self._client, "description", "Apollo")

    def _run(self) -> None:
        state, error = "ok", None
        try:
            self._client.check()
        except ApolloError as exc:
            state, error = "error", str(exc)
        except Exception as exc:  # a driver can fail in unexpected ways
            state, error = "error", f"Unexpected error reaching Apollo: {exc}"
        with self._lock:
            self._state, self._error = state, error
            self._checked_at = time.monotonic()
            self._thread = None

    def _stale(self) -> bool:
        if self._checked_at == 0.0:
            return True
        ttl = self.TTL_OK if self._state == "ok" else self.TTL_BAD
        return (time.monotonic() - self._checked_at) > ttl

    def start(self, force: bool = False) -> None:
        """Kick off a probe if one is not already running."""
        with self._lock:
            if self._thread is not None:
                return
            if not force and not self._stale():
                return
            self._thread = threading.Thread(
                target=self._run, name="apollo-health", daemon=True)
            thread = self._thread
        thread.start()

    def snapshot(self) -> dict:
        """Current state, without ever blocking."""
        self.start()
        with self._lock:
            return {
                "state": self._state,
                "error": self._error,
                "apollo": self.description,
                "ok": self._state == "ok",
            }
