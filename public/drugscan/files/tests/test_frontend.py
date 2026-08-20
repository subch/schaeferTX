"""Static checks on the front end.

These exist because a whole class of UI bug is invisible to the tests that read
DOM state: `element.hidden` reports True even while author CSS forces the
element on screen. The busy spinner shipped permanently visible for exactly that
reason -- `.busy { display: flex }` outranked the user-agent rule for [hidden].
"""
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "src" / "batchbuilder" / "static"
TEMPLATES = Path(__file__).resolve().parent.parent / "src" / "batchbuilder" / "templates"

def _read_asset(name: str) -> str:
    """Read a static asset, tolerating the email-safe stash name.

    Gmail blocks .js attachments, so the source archive ships app.js as
    app.js.txt and `make.py setup` restores it. Tests should pass either way,
    including before setup has run.
    """
    direct = STATIC / name
    if direct.exists():
        return direct.read_text(encoding="utf-8")
    stashed = STATIC / (name + ".txt")
    if stashed.exists():
        return stashed.read_text(encoding="utf-8")
    raise FileNotFoundError(f"{name} not found in {STATIC}")


CSS = _read_asset("app.css")
JS = _read_asset("app.js")
HTML = (TEMPLATES / "index.html").read_text(encoding="utf-8")


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


class TestHiddenAttribute:
    def test_stylesheet_forces_hidden_to_win(self):
        """Without this rule every `hidden` toggle in app.js is inert."""
        css = strip_comments(CSS)
        match = re.search(r"\[hidden\]\s*\{([^}]*)\}", css)
        assert match, "app.css must reset [hidden]"
        body = match.group(1).replace(" ", "").lower()
        assert "display:none!important" in body, (
            "the [hidden] reset must be !important, or author display rules "
            "such as .busy{display:flex} will still beat it"
        )

    def test_elements_toggled_in_js_exist_in_the_template(self):
        toggled = set(re.findall(r'\$\("([a-z-]+)"\)\.hidden', JS))
        toggled |= set(re.findall(
            r'document\.getElementById\("([a-z-]+)"\)\.hidden', JS))
        assert toggled, "expected the script to toggle some elements"
        for element_id in toggled:
            assert f'id="{element_id}"' in HTML, (
                f'app.js toggles #{element_id} but the template has no such id')

    @pytest.mark.parametrize("element_id", [
        "busy", "detected", "legend", "counts", "mockup-field",
        "condition-field", "result-actions",
    ])
    def test_elements_that_start_hidden_say_so(self, element_id):
        """Each of these must carry the attribute; the CSS reset makes it bite."""
        pattern = rf'id="{element_id}"[^>]*>'
        match = re.search(pattern, HTML)
        assert match, f"#{element_id} not found in the template"
        tag_start = HTML.rfind("<", 0, match.start())
        tag = HTML[tag_start:match.end()]
        assert " hidden" in tag, f"#{element_id} should start hidden: {tag}"


class TestNoExternalResources:
    """The application must work with no network access of any kind."""

    @pytest.mark.parametrize("source,name", [(HTML, "index.html"),
                                             (CSS, "app.css"),
                                             (JS, "app.js")])
    def test_no_remote_urls(self, source, name):
        for bad in ("http://", "https://", "//cdn", "fonts.googleapis",
                    "unpkg.com", "jsdelivr"):
            assert bad not in source, f"{name} references {bad}"

    def test_assets_are_version_stamped(self):
        assert "app.css') }}?v=" in HTML
        assert "app.js') }}?v=" in HTML


class TestRequestHandling:
    def test_every_fetch_goes_through_the_deadline_helper(self):
        """A bare fetch has no timeout, so a stall leaves the overlay spinning."""
        bare = re.findall(r"(?<!\.)\bfetch\(", JS)
        # exactly one: the definition inside request() itself
        assert len(bare) == 1, (
            f"expected all calls to go through request(); found {len(bare)} "
            f"bare fetch( occurrences")

    def test_busy_overlay_is_always_cleared_on_failure(self):
        # every busy(true, ...) path must have a matching catch that clears it
        assert JS.count("busy(true") <= JS.count("busy(false")


class TestPackaging:
    """Guards for failures that only appear in a frozen build."""

    ROOT = Path(__file__).resolve().parent.parent
    SPEC = (ROOT / "build" / "batchbuilder.spec").read_text(encoding="utf-8")
    # make.py is the authoritative build path. build.ps1 is a convenience that
    # is deliberately absent from the emailed archive, so treat it as optional.
    MAKE = (ROOT / "make.py").read_text(encoding="utf-8")
    _PS1 = ROOT / "build" / "build.ps1"
    BUILD_PS1 = _PS1.read_text(encoding="utf-8") if _PS1.exists() else None

    def test_entry_point_is_not_the_package_main(self):
        """PyInstaller runs its entry script as a top-level module, so pointing
        it at __main__.py fails on that file's relative imports before any of
        our error handling exists."""
        assert "entry.py" in self.SPEC
        assert '"__main__.py"' not in self.SPEC

    def test_entry_script_exists_and_imports_the_package(self):
        entry = (Path(__file__).resolve().parent.parent / "build" / "entry.py")
        assert entry.exists()
        text = entry.read_text(encoding="utf-8")
        assert "from batchbuilder.__main__ import run" in text
        assert "sys.exit(main())" in text

    def test_templates_and_static_are_bundled(self):
        assert "batchbuilder/templates" in self.SPEC
        assert "batchbuilder/static" in self.SPEC

    def test_build_task_smoke_tests_the_executable(self):
        """A build that compiles but cannot start must fail the build."""
        assert "--version" in self.MAKE
        assert "does not start" in self.MAKE

    def test_build_task_runs_tests_first(self):
        assert "Not packaging" in self.MAKE

    @pytest.mark.skipif(not (Path(__file__).resolve().parent.parent
                             / "build" / "build.ps1").exists(),
                        reason="build.ps1 is not shipped in the source archive")
    def test_powershell_build_script_agrees_when_present(self):
        assert "--version" in self.BUILD_PS1
        assert "does not start" in self.BUILD_PS1

    def test_make_py_has_no_blocked_extension_dependencies(self):
        """The project must not require file types that cannot be transferred."""
        required = [p for p in ("setup.bat", "run.bat", "build.bat")
                    if p in self.MAKE]
        assert not required, (
            f"make.py should not depend on blocked file types: {required}")
