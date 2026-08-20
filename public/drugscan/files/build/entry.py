"""Packaging entry point.

PyInstaller executes its entry script as a top-level module with no package
context, so pointing it straight at ``batchbuilder/__main__.py`` fails on that
file's relative imports before any of our own error handling exists. Importing
the package properly and calling into it keeps the frozen build and the
``python -m batchbuilder`` path on identical code.
"""
import sys


def main() -> int:
    try:
        from batchbuilder.__main__ import run
    except Exception:
        # Import-time failures happen before run()'s safety net can help, and a
        # double-clicked build would otherwise close its window instantly.
        import traceback
        print("\n[Batch Builder] Failed to start: the application could not be "
              "loaded.\n", file=sys.stderr)
        traceback.print_exc()
        try:
            input("\nPress Enter to close this window...")
        except (EOFError, KeyboardInterrupt):
            pass
        return 1
    return run()


if __name__ == "__main__":
    sys.exit(main())
