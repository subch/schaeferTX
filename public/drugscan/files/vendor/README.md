# Vendored wheels

Every Python package this project needs, pre-downloaded, so `setup.ps1` can
install with **no internet access**:

```
pip install --no-index --find-links vendor\wheels -r requirements-dev.txt
```

That is what `setup.ps1` does automatically when this folder is present. If it
is missing, setup falls back to downloading from PyPI, which will fail on a
machine behind a proxy with no package access.

## Refreshing them

On a machine that *does* have internet access, from the project root:

```bash
pip download -r requirements-dev.txt -d vendor\wheels
```

## Platform and Python versions

Windows, 64-bit Intel/AMD, CPython **3.10 through 3.13**. A few packages ship
version-specific binaries (markupsafe, pyodbc, tomli), so each of those is
present once per Python version - that is why some names repeat.

They will not work on a different OS or on ARM. If the target machine is
unusual, delete this folder and let setup fall back to PyPI, or re-download on a
matching machine.

To cover a newer Python, from a machine with internet access:

```bash
pip download -r requirements-dev.txt -d vendor\wheels --only-binary=:all: --python-version 314 --platform win_amd64
```
