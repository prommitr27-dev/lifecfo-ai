"""Write docs/competition/THIRD_PARTY_LICENSES.md from the lockfiles.

Python packages come from uv.lock, with each license read from the installed
package metadata (run `uv sync` first). Mobile packages come from
mobile/package-lock.json, which records each package's license.

Run: uv run python scripts/generate_third_party_licenses.py
"""

from __future__ import annotations

import importlib.metadata as metadata
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "competition" / "THIRD_PARTY_LICENSES.md"
PROJECT = "lifecfo-ai"

# Packages uv.lock lists only for another platform (Windows), so they are not
# installed in a Linux environment. Licenses taken from their PyPI pages.
NOT_INSTALLED_HERE = {
    "colorama": "BSD-3-Clause",
    "tzdata": "Apache-2.0",
}

# Free-text license fields and trove classifiers mapped to SPDX identifiers.
TEXT_TO_SPDX = {
    "mit": "MIT",
    "mit license": "MIT",
    "bsd license": "BSD-3-Clause",
    "bsd 3-clause license": "BSD-3-Clause",
    "3-clause bsd license": "BSD-3-Clause",
    "apache-2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "mpl-2.0": "MPL-2.0",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "bsd-3-clause": "BSD-3-Clause",
}

# Licenses that let an MIT project use and redistribute the package as is.
PERMISSIVE = {
    "MIT",
    "MIT-CMU",
    "ISC",
    "0BSD",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "Zlib",
    "Unlicense",
    "CC0-1.0",
    "BlueOak-1.0.0",
    "Python-2.0",
    "PSF-2.0",
}

# Compatible with MIT, with a condition worth stating.
NOTES = {
    "MPL-2.0": (
        "File-level copyleft. Using the package unmodified is fine; changes to "
        "its own files would have to be shared under MPL-2.0. We do not modify it."
    ),
    "CC-BY-4.0": (
        "Data license (browser support tables). Requires attribution, which this "
        "list provides. Used only at build time."
    ),
}


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def python_license(dist: metadata.Distribution) -> str:
    md = dist.metadata
    expression = md.get("License-Expression")
    if expression:
        return expression.strip()
    text = (md.get("License") or "").strip()
    if text and "\n" not in text and len(text) < 60:
        mapped = TEXT_TO_SPDX.get(text.lower())
        if mapped:
            return mapped
    classifiers = [
        c.split("::")[-1].strip()
        for c in md.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    mapped = [TEXT_TO_SPDX.get(c.lower(), c) for c in classifiers]
    if mapped:
        return " OR ".join(dict.fromkeys(mapped))
    return text.splitlines()[0] if text else "UNKNOWN"


def python_packages() -> tuple[list[dict], set[str]]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = {normalise(p["name"]): p for p in lock["package"]}
    root = packages[PROJECT]

    def closure(names: list[str]) -> set[str]:
        seen: set[str] = set()
        stack = list(names)
        while stack:
            name = normalise(stack.pop())
            if name in seen or name == PROJECT:
                continue
            seen.add(name)
            stack.extend(d["name"] for d in packages[name].get("dependencies", []))
        return seen

    runtime = closure([d["name"] for d in root.get("dependencies", [])])
    dev_direct = [d["name"] for group in root.get("dev-dependencies", {}).values() for d in group]
    dev_only = closure(dev_direct) - runtime

    installed = {normalise(d.metadata["Name"]): d for d in metadata.distributions()}
    rows = []
    for name in sorted(runtime | dev_only):
        if name in installed:
            license_ = python_license(installed[name])
        elif name in NOT_INSTALLED_HERE:
            license_ = NOT_INSTALLED_HERE[name]
        else:
            license_ = "UNKNOWN (run uv sync)"
        rows.append(
            {
                "name": packages[name]["name"],
                "version": packages[name]["version"],
                "license": license_,
                "scope": "runtime" if name in runtime else "dev",
            }
        )
    return rows, dev_only


def npm_packages() -> list[dict]:
    lock = json.loads((ROOT / "mobile" / "package-lock.json").read_text(encoding="utf-8"))
    rows = {}
    for path, info in lock["packages"].items():
        if not path:
            continue
        name = info.get("name") or path.split("node_modules/")[-1]
        key = (name, info.get("version", ""))
        dev = bool(info.get("dev") or info.get("devOptional"))
        rows[key] = {
            "name": name,
            "version": info.get("version", ""),
            "license": info.get("license") or "UNKNOWN",
            "scope": "dev" if dev else "app or build",
        }
    return sorted(rows.values(), key=lambda r: (r["name"].lower(), r["version"]))


def terms(expression: str) -> tuple[list[str], str]:
    """Split an SPDX expression into its identifiers and its operator."""
    cleaned = expression.strip("() ")
    if " OR " in cleaned:
        return [t.strip("() ") for t in cleaned.split(" OR ")], "OR"
    return [t.strip("() ") for t in cleaned.split(" AND ")], "AND"


def verdict(expression: str) -> str:
    ids, op = terms(expression)
    ok = [i in PERMISSIVE or i in NOTES for i in ids]
    if (op == "OR" and any(ok)) or (op == "AND" and all(ok)):
        if op == "OR" and not all(ok):
            chosen = next(i for i in ids if i in PERMISSIVE)
            return f"OK (we use it under {chosen})"
        noted = [i for i in ids if i in NOTES]
        return f"OK, see note on {noted[0]}" if noted else "OK"
    return "REVIEW"


def table(rows: list[dict]) -> list[str]:
    lines = ["| Package | Version | License | Scope | MIT compatible |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['name']} | {r['version']} | {r['license']} | {r['scope']} "
            f"| {verdict(r['license'])} |"
        )
    return lines


def summary(rows: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["license"]] = counts.get(r["license"], 0) + 1
    lines = ["| License | Packages |", "|---|---|"]
    for license_, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {license_} | {n} |")
    return lines


def main() -> None:
    py_rows, _ = python_packages()
    npm_rows = npm_packages()
    flagged = [r for r in py_rows + npm_rows if verdict(r["license"]) == "REVIEW"]
    used_notes = sorted(
        {i for r in py_rows + npm_rows for i in terms(r["license"])[0] if i in NOTES}
    )

    out = [
        "# Third-party licenses",
        "",
        "LifeCFO AI is released under the [MIT License](../../LICENSE). This list",
        "covers every third-party package pinned in the lockfiles: `uv.lock` for the",
        "Python engines, web app, and API, and `mobile/package-lock.json` for the",
        "Expo mobile app. It is generated; do not edit it by hand. Regenerate with:",
        "",
        "```bash",
        "uv sync",
        "uv run python scripts/generate_third_party_licenses.py",
        "```",
        "",
        "## Result",
        "",
        f"- Python: {len(py_rows)} packages "
        f"({sum(r['scope'] == 'runtime' for r in py_rows)} runtime, "
        f"{sum(r['scope'] == 'dev' for r in py_rows)} development only).",
        f"- Mobile (npm): {len(npm_rows)} packages "
        f"({sum(r['scope'] == 'app or build' for r in npm_rows)} app or build tooling, "
        f"{sum(r['scope'] == 'dev' for r in npm_rows)} development only).",
    ]
    if flagged:
        out.append(f"- **{len(flagged)} package(s) need review** (marked REVIEW below).")
    else:
        out.append(
            "- **No license conflicts with MIT.** No package is GPL, LGPL, or AGPL "
            "only; where a package offers a choice (for example `BSD-3-Clause OR "
            "GPL-2.0`), we use the permissive option."
        )
    out += ["", "## Notes on licenses with conditions", ""]
    for license_ in used_notes:
        out.append(f"- **{license_}**: {NOTES[license_]}")
    out += [
        "- **Python-2.0** and **PSF-2.0**: permissive Python Software Foundation "
        "licenses; keep the copyright notice.",
        "- All other licenses listed (MIT, ISC, BSD, Apache-2.0, 0BSD, Zlib, "
        "Unlicense, CC0-1.0, BlueOak-1.0.0, MIT-CMU) are permissive. Apache-2.0 "
        "packages ask that their NOTICE file is kept when redistributed.",
        "",
        "Platform-specific packages (for example the `lightningcss-*` binaries) are",
        "listed for every platform in the lockfile; only the one for the build",
        "machine is installed.",
        "",
        "## Python packages (uv.lock)",
        "",
        *summary(py_rows),
        "",
        *table(py_rows),
        "",
        "## Mobile packages (mobile/package-lock.json)",
        "",
        *summary(npm_rows),
        "",
        *table(npm_rows),
        "",
    ]
    OUTPUT.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}: {len(py_rows)} Python, {len(npm_rows)} npm")
    if flagged:
        print("Needs review:", ", ".join(f"{r['name']} ({r['license']})" for r in flagged))


if __name__ == "__main__":
    main()
