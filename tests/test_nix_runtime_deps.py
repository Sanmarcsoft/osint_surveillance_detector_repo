"""The Nix image must ship every module ghostmode imports (osint #85).

`flake.nix` builds the production OCI image from an explicit list of Python
packages. That list drifted to four entries while the app grew to import eight
third-party modules, so `ghostmode serve` raised ImportError on `fastmcp`
before logging was configured. The container exited 1 with no CloudWatch
output, the failure was written off as "the Nix image crashes on startup", and
production ran a hand-built ECR image for three months instead.

Nothing catches that at build time: `nix build` succeeds, because a missing
runtime import is not a build error. This test is the gate.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FLAKE = REPO / "flake.nix"
SRC = REPO / "ghostmode"

# Python module name -> nixpkgs python3Packages attribute name, for the cases
# where they differ. Anything not listed is assumed to match.
MODULE_TO_NIX = {
    "dotenv": "python-dotenv",
    "jwt": "pyjwt",
    "prometheus_client": "prometheus-client",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "psycopg2": "psycopg2",
}

# Modules that ship with the interpreter or are pulled in by the app package
# itself, so they need no entry in the Nix closure.
NOT_PACKAGED = {"ghostmode"}


def _nix_python_packages() -> set[str]:
    """Extract the withPackages list from flake.nix."""
    text = FLAKE.read_text()
    match = re.search(
        r"ghostmodePython\s*=\s*\S+\.python3\.withPackages\s*\(\s*ps:\s*with ps;\s*\[(.*?)\]\s*\)",
        text,
        re.DOTALL,
    )
    assert match, "could not find the ghostmodePython withPackages list in flake.nix"
    body = re.sub(r"#[^\n]*", "", match.group(1))
    return {tok for tok in body.split() if tok}


def _imported_third_party_modules() -> set[str]:
    """Every top-level third-party module imported anywhere under ghostmode/.

    Walks the AST rather than grepping, so imports nested inside functions
    count too. Those are the dangerous ones: a missing lazy import fails at
    first query instead of at boot.
    """
    found: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    found.add(node.module.split(".")[0])
    return {
        mod
        for mod in found
        if mod not in sys.stdlib_module_names
        and mod not in NOT_PACKAGED
        and not mod.startswith("_")
    }


def test_nix_closure_covers_every_import():
    declared = _nix_python_packages()
    missing = {
        mod: MODULE_TO_NIX.get(mod, mod)
        for mod in sorted(_imported_third_party_modules())
        if MODULE_TO_NIX.get(mod, mod) not in declared
    }
    assert not missing, (
        "flake.nix ghostmodePython is missing packages for imported modules "
        f"{missing}. The image will build fine and then exit 1 at runtime. "
        "Add the nixpkgs attribute to the withPackages list."
    )


def test_fastmcp_is_present():
    """Regression pin for the exact package whose absence caused osint #85."""
    assert "fastmcp" in _nix_python_packages(), (
        "fastmcp dropped out of the Nix closure. `ghostmode serve` imports it at "
        "module scope, so the container exits 1 before writing a single log line."
    )


def test_python_input_is_pinned_to_a_revision():
    """A moving branch would make the production image non-deterministic."""
    text = FLAKE.read_text()
    match = re.search(r'nixpkgs-python\.url\s*=\s*"github:NixOS/nixpkgs/([^"]+)"', text)
    assert match, "nixpkgs-python input missing from flake.nix"
    ref = match.group(1)
    assert re.fullmatch(r"[0-9a-f]{40}", ref), (
        f"nixpkgs-python must be pinned to a 40-char commit SHA, got {ref!r}. "
        "Branch refs make the image non-reproducible."
    )
