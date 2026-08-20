"""Startup behaviour.

The application is launched by double-click and must never leave the analyst
with a browser tab spinning at a port nothing is listening on. That means two
rules: startup does not wait on the database, and startup does not die quietly.
"""
import socket
import threading
import time

import pytest

from batchbuilder.__main__ import find_port, wait_until_accepting
from batchbuilder.apollo import ApolloError, HealthProbe


class TestPortSelection:
    def test_picks_a_free_port(self):
        assert find_port(0) > 0

    def test_honours_a_requested_port(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            wanted = probe.getsockname()[1]
        assert find_port(wanted) == wanted

    def test_falls_back_when_the_requested_port_is_taken(self):
        held = socket.socket()
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        taken = held.getsockname()[1]
        try:
            chosen = find_port(taken)
            assert chosen != taken
            assert chosen > 0
        finally:
            held.close()


class TestWaitUntilAccepting:
    def test_returns_false_when_nothing_listens(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            dead = probe.getsockname()[1]
        started = time.monotonic()
        assert wait_until_accepting(dead, 0.5) is False
        assert time.monotonic() - started < 3.0

    def test_returns_true_once_something_listens(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        try:
            assert wait_until_accepting(port, 2.0) is True
        finally:
            server.close()

    def test_waits_for_a_late_starter(self):
        """The browser is opened from this, so it has to tolerate a slow start."""
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        holder = {}

        def start_later():
            time.sleep(0.4)
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            s.listen(1)
            holder["s"] = s

        t = threading.Thread(target=start_later)
        t.start()
        try:
            assert wait_until_accepting(port, 5.0) is True
        finally:
            t.join()
            if "s" in holder:
                holder["s"].close()


class TestHealthProbe:
    def test_never_blocks_the_caller(self):
        class Slow:
            description = "slow server"

            def check(self):
                time.sleep(2)

        probe = HealthProbe(Slow())
        started = time.monotonic()
        snap = probe.snapshot()
        assert time.monotonic() - started < 0.5
        assert snap["state"] == "checking"
        assert snap["ok"] is False

    def test_settles_to_ok(self):
        class Fine:
            description = "fine"

            def check(self):
                return None

        probe = HealthProbe(Fine())
        for _ in range(50):
            snap = probe.snapshot()
            if snap["state"] != "checking":
                break
            time.sleep(0.02)
        assert snap["state"] == "ok" and snap["ok"] is True

    def test_settles_to_error_with_the_reason(self):
        class Broken:
            description = "broken"

            def check(self):
                raise ApolloError("the network is down")

        probe = HealthProbe(Broken())
        for _ in range(50):
            snap = probe.snapshot()
            if snap["state"] != "checking":
                break
            time.sleep(0.02)
        assert snap["state"] == "error"
        assert "network is down" in snap["error"]

    def test_an_unexpected_exception_is_contained(self):
        """A driver can fail in ways that are not ApolloError; the probe must
        still report rather than propagate, or startup dies."""
        class Exploding:
            description = "exploding"

            def check(self):
                raise RuntimeError("boom")

        probe = HealthProbe(Exploding())
        for _ in range(50):
            snap = probe.snapshot()
            if snap["state"] != "checking":
                break
            time.sleep(0.02)
        assert snap["state"] == "error"
        assert "boom" in snap["error"]


class TestApolloClientErrors:
    def test_missing_pyodbc_raises_apollo_error_not_import_error(self, monkeypatch):
        """This is what took the whole application down: connect() let a bare
        ImportError escape, and callers only guard against ApolloError."""
        import builtins

        from batchbuilder.apollo import SqlServerApolloClient

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pyodbc":
                raise ImportError("no pyodbc here")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        client = SqlServerApolloClient("srv", "db", "u", "p")
        with pytest.raises(ApolloError, match="pyodbc"):
            client.check()
