"""Build a source archive that Gmail will actually accept.

Gmail rejects a documented list of file extensions, and it inspects inside
archives -- including inside Python wheels, which are themselves zip files. This
script produces an archive containing none of them, and reports exactly what it
had to leave out.

Two categories of problem:

* **Our own files.** The .bat and .ps1 wrappers, and the browser script app.js.
  The wrappers are redundant now that make.py exists, so they are simply left
  out. app.js is renamed to app.js.txt and restored by `make.py setup`.

* **Bundled wheels.** These cannot be salvaged. PyInstaller ships bootloader
  .exe files and setuptools ships CLI stubs; renaming files inside a wheel would
  corrupt it. The vendor/wheels folder is therefore excluded, which means the
  receiving machine needs PyPI access -- or the wheels transferred some other
  way.

Run:  python build/make_email_zip.py [output.zip]
"""
from __future__ import annotations

import fnmatch
import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Extensions Gmail refuses, including inside archives.
#: From https://support.google.com/mail/answer/6590
BLOCKED = {
    ".ade", ".adp", ".apk", ".appx", ".appxbundle", ".bat", ".cab", ".chm",
    ".cmd", ".com", ".cpl", ".diagcab", ".diagcfg", ".diagpkg", ".dll", ".dmg",
    ".ex", ".ex_", ".exe", ".hta", ".img", ".ins", ".iso", ".isp", ".jar",
    ".jnlp", ".js", ".jse", ".lib", ".lnk", ".mde", ".mjs", ".msc", ".msi",
    ".msix", ".msixbundle", ".msp", ".mst", ".nsh", ".pif", ".ps1", ".scr",
    ".sct", ".shb", ".sys", ".vb", ".vbe", ".vbs", ".vhd", ".vxd", ".wsc",
    ".wsf", ".wsh", ".xll",
}

#: Never shipped: local environments, build output, caches, version control.
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "dist", "work",
             "ins_files", ".idea"}

#: Left out because Gmail rejects them and make.py replaces them.
SKIP_GLOBS = ["*.pyc", "*.pyo", "*.zip", "*.bat", "*.ps1"]

#: Excluded wholesale: wheels contain .exe files that cannot be renamed away.
SKIP_TREES = ["vendor/wheels"]

#: Shipped under a different name and restored by make.py.
RENAMES = {"src/batchbuilder/static/app.js": "src/batchbuilder/static/app.js.txt"}

TOP = "batch-builder"


def should_skip(rel: Path) -> bool:
    posix = rel.as_posix()
    if any(part in SKIP_DIRS for part in rel.parts):
        return True
    if any(posix.startswith(tree) for tree in SKIP_TREES):
        return True
    return any(fnmatch.fnmatch(rel.name, pattern) for pattern in SKIP_GLOBS)


def blocked_inside(data: bytes) -> list[str]:
    """Look inside a nested archive for blocked members."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as inner:
            return [n for n in inner.namelist()
                    if Path(n).suffix.lower() in BLOCKED]
    except zipfile.BadZipFile:
        return []


def build(output: Path) -> int:
    included: list[tuple[Path, str]] = []
    excluded: list[tuple[str, str]] = []

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        posix = rel.as_posix()

        if should_skip(rel):
            # Only report exclusions that are interesting. Build output and
            # caches were never going to ship and would drown the useful lines.
            is_artifact = posix.startswith(("build/dist", "build/work"))
            in_wheels = any(posix.startswith(t) for t in SKIP_TREES)
            if in_wheels:
                excluded.append((posix, "wheels contain .exe bootloaders"))
            elif rel.suffix.lower() in BLOCKED and not is_artifact:
                excluded.append((posix, "blocked type, replaced by make.py"))
            continue

        arcname = RENAMES.get(posix, posix)
        included.append((path, f"{TOP}/{arcname}"))

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for source, arcname in included:
            z.write(source, arcname=arcname)

    # ---- verify what we produced, rather than trusting the filters above ----
    problems: list[str] = []
    with zipfile.ZipFile(output) as z:
        for name in z.namelist():
            if Path(name).suffix.lower() in BLOCKED:
                problems.append(name)
            if name.endswith((".whl", ".jar", ".zip")):
                for nested in blocked_inside(z.read(name)):
                    problems.append(f"{name} -> {nested}")

    size = output.stat().st_size
    print(f"Wrote {output}")
    print(f"  {len(included)} files, {size / 1024 / 1024:.1f} MB")

    if excluded:
        print(f"\n  Left out ({len(excluded)}):")
        seen: set[str] = set()
        for name, reason in excluded:
            key = reason if "wheels" in reason else name
            if key in seen:
                continue
            seen.add(key)
            if "wheels" in reason:
                count = sum(1 for _, r in excluded if r == reason)
                print(f"    vendor/wheels/  ({count} files) - {reason}")
            else:
                print(f"    {name} - {reason}")

    if RENAMES:
        print("\n  Renamed for delivery (make.py setup restores these):")
        for original, shipped in RENAMES.items():
            print(f"    {original}  ->  {Path(shipped).name}")

    print()
    if problems:
        print(f"  FAILED: {len(problems)} blocked file(s) still present:")
        for p in problems[:10]:
            print(f"    {p}")
        return 1

    print("  VERIFIED: no Gmail-blocked file types, including inside archives.")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path.home() / "Downloads" / "batch-builder-source-emailsafe.zip")
    sys.exit(build(target))
