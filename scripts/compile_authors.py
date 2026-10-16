"""Compile the Open-H-RF author list into a LaTeX ``\\author`` block.

The roster lives in Google Sheets and changes as datasets are accepted.

The sheet is not link-viewable, so export the first tab as CSV over
``authors.csv`` in this folder and re-run. The website's author list
(``site/build.py``) reads the same file. If it ever is shared publicly, pass the
export URL to ``--csv`` instead and the roster is fetched live:

    python compile_authors.py --csv "https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<GID>"

Ordering comes from the ``Author number`` column. The first ``--core`` authors
form the core-team row and the last ``--senior`` form the senior-author row;
everyone in between is a contributor.

Superscript marks are independent of the rows: ``*`` and ``\u2020`` flag equal
first and senior authorship, and ``\u00a7`` flags the core team (the first
``--core-team-first`` and last ``--core-team-last`` authors). An author with
several marks gets them comma-separated in one superscript.
"""

import argparse
import csv
import io
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parent / "authors.csv"
DEFAULT_OUT = Path("assets/authors.tex")
DEFAULT_INSTITUTIONS_OUT = Path("assets/institutions.tex")

NUMBER_COLUMN = "Author number"
NAME_COLUMN = "Author"
ABBREVIATION_COLUMN = "Abbreviation"
AFFILIATION_COLUMN = "Affiliation"
AFFILIATION_ORDER_COLUMN = "Affiliation order"

# The rows and marks of the author list, as the paper has them; the website marks the same.
CORE = 6
SENIOR = 3
EQUAL_FIRST = 4
EQUAL_SENIOR = 3
CORE_TEAM_FIRST = 6
CORE_TEAM_LAST = 3

FIRST_AUTHOR_MARK = "*"
SENIOR_AUTHOR_MARK = r"\dag"
CORE_TEAM_MARK = r"\S"

THANKS = (
    "\\thanks{The steering committee of the Open-H-RF consortium consists of "
    "NVIDIA, Eindhoven University of Technology (TU/e) and Stanford University. "
    "\\authorcontributions}"
)

LATEX_ESCAPES = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}

# Leading initials of an abbreviated name: "T.S.W.", "H.-M.", "B. N.".
INITIALS = re.compile(r"^((?:[A-Z]\.[-\s]*)+)(.*)$")
MARKUP = re.compile(r"\\textsuperscript\{.*?\}")
MBOX = re.compile(r"^\\mbox\{(.*)\}$")


class AuthorListError(Exception):
    """The roster cannot be turned into an author block."""


def read_rows(source: str) -> list[dict[str, str]]:
    """Read the roster from a local CSV path or an http(s) URL."""
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source) as response:
            payload = response.read().decode("utf-8")
        if payload.lstrip().startswith("<"):
            raise AuthorListError(
                f"{source} returned HTML instead of CSV; the sheet is probably not "
                "shared with 'anyone with the link'. Export it manually instead."
            )
    else:
        payload = Path(source).read_text(encoding="utf-8")

    rows = list(csv.DictReader(io.StringIO(payload)))
    if not rows:
        raise AuthorListError(f"{source} has no data rows")

    required = {
        NUMBER_COLUMN,
        ABBREVIATION_COLUMN,
        AFFILIATION_COLUMN,
        AFFILIATION_ORDER_COLUMN,
    }
    missing = required - set(rows[0])
    if missing:
        raise AuthorListError(
            f"{source} is missing column(s) {sorted(missing)}; found {list(rows[0])}"
        )
    return rows


def sort_key(row: dict[str, str], source: str) -> int:
    raw = (row.get(NUMBER_COLUMN) or "").strip()
    try:
        return int(raw)
    except ValueError as error:
        name = (row.get(ABBREVIATION_COLUMN) or "?").strip()
        raise AuthorListError(
            f"{source}: author {name!r} has a non-numeric {NUMBER_COLUMN} {raw!r}"
        ) from error


def normalise(abbreviation: str) -> str:
    """Collapse whitespace and close the gaps between initials.

    The sheet mixes ``B. J. Wood`` and ``R.J.G. van Sloun``; the tighter form is
    used throughout.
    """
    name = unicodedata.normalize("NFC", abbreviation).strip()
    name = re.sub(r"\s+", " ", name)
    while True:
        tightened = re.sub(r"([A-Z]\.)\s+(?=[A-Z][.-])", r"\1", name)
        if tightened == name:
            return name
        name = tightened


def split_initials(name: str) -> tuple[str, str]:
    """Split ``V. van der Schaft`` into its initials and its surname."""
    match = INITIALS.match(name)
    if not match:
        return "", name
    return match.group(1).strip(), match.group(2).strip()


def disambiguate(names: list[str], rows: list[dict[str, str]]) -> list[str]:
    """Spell out the given name wherever two authors abbreviate identically.

    Yujia Wu and Yixuan Wu both reduce to ``Y. Wu``, which would otherwise read
    as one author listed twice.
    """
    counts: dict[str, int] = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1

    resolved = []
    for name, row in zip(names, rows):
        if counts[name] == 1:
            resolved.append(name)
            continue

        full = unicodedata.normalize("NFC", (row.get(NAME_COLUMN) or "").strip())
        given = full.split(" ")[0] if full else ""
        _, surname = split_initials(name)
        if not given or not surname:
            print(
                f"warning: {name!r} is ambiguous and has no full name to expand",
                file=sys.stderr,
            )
            resolved.append(name)
            continue
        resolved.append(f"{given} {surname}")
    return resolved


def escape(text: str) -> str:
    return "".join(LATEX_ESCAPES.get(character, character) for character in text)


def superscript(marks: list[str]) -> str:
    return rf"\textsuperscript{{{','.join(marks)}}}" if marks else ""


def to_latex(name: str, marks: list[str] = ()) -> str:
    """Escape a name and box it so it never breaks across lines.

    A ``~`` only ties spaces; TeX can still break after the hyphen in
    ``H.-M.`` or hyphenate a long surname. ``\\mbox`` prevents both and keeps the
    superscript marks attached.
    """
    escaped = escape(name)
    return rf"\mbox{{{escaped}{superscript(list(marks))}}}"


def wrap(names: list[str], per_line: int) -> list[str]:
    """Lay names out ``per_line`` to a source line, separated by ``, ``.

    The spaces between names are the only places TeX may break a line.
    """
    lines = []
    for start in range(0, len(names), per_line):
        lines.append(", ".join(names[start : start + per_line]))
    return lines


def build_block(groups: list[tuple[str, list[str]]], per_line: int) -> str:
    """Join the groups into one ``\\author`` body, one output row per group."""
    body = []
    populated = [(label, names) for label, names in groups if names]
    for index, (label, names) in enumerate(populated):
        body.append(f"% {label}")
        lines = wrap(names, per_line)
        last = index == len(populated) - 1
        for line_index, line in enumerate(lines):
            trailing = "" if last and line_index == len(lines) - 1 else ","
            body.append(line + trailing)
        if not last:
            body.append(r"\\[.3ex]")
    return "\n".join(body)


def compile_institutions(rows: list[dict[str, str]], source: str) -> str:
    """List every institution once, comma separated, in ``Affiliation order``.

    A cell like ``KAIST, Barreleye Inc.`` with order ``11, 12`` holds two
    institutions. Single names may contain commas themselves (``University of
    Oslo (UiO), Norway``), so a cell is only split when its order lists more
    than one number.
    """
    by_number: dict[int, str] = {}
    for row in rows:
        text = unicodedata.normalize("NFC", (row.get(AFFILIATION_COLUMN) or "").strip())
        order = (row.get(AFFILIATION_ORDER_COLUMN) or "").strip()
        who = (row.get(ABBREVIATION_COLUMN) or "?").strip()
        if not text or not order:
            print(f"warning: {who!r} has no affiliation", file=sys.stderr)
            continue
        try:
            numbers = [int(part) for part in order.split(",")]
        except ValueError as error:
            raise AuthorListError(
                f"{source}: {who!r} has a non-numeric {AFFILIATION_ORDER_COLUMN} {order!r}"
            ) from error
        names = [text] if len(numbers) == 1 else [n.strip() for n in text.split(",")]
        if len(names) != len(numbers):
            raise AuthorListError(
                f"{source}: {who!r} lists {len(numbers)} affiliation numbers "
                f"{order!r} but {len(names)} institutions in {text!r}"
            )
        for number, name in zip(numbers, names):
            name = re.sub(r"\s+", " ", name)
            known = by_number.setdefault(number, name)
            if known != name:
                raise AuthorListError(
                    f"{source}: affiliation {number} is both {known!r} and {name!r}"
                )

    institutions = [by_number[number] for number in sorted(by_number)]
    duplicates = sorted({n for n in institutions if institutions.count(n) > 1})
    if duplicates:
        print(
            f"warning: institution(s) under several numbers: {duplicates}",
            file=sys.stderr,
        )
    return (
        f"% Generated by compile_authors.py from {Path(source).name!r}.\n"
        f"% {len(institutions)} institutions. Edit the Google Sheet and regenerate; "
        "do not edit by hand.\n" + ", ".join(escape(name) for name in institutions) + "%\n"
    )


def compile_authors(
    rows: list[dict[str, str]],
    source: str,
    core: int,
    senior: int,
    first_marks: int,
    senior_marks: int,
    core_team_first: int,
    core_team_last: int,
    per_line: int,
) -> tuple[str, dict[str, list[str]]]:
    rows = sorted(rows, key=lambda row: sort_key(row, source))

    numbers = [sort_key(row, source) for row in rows]
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicates:
        raise AuthorListError(f"{source}: duplicate {NUMBER_COLUMN}(s) {duplicates}")
    gaps = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
    if gaps:
        print(f"warning: {NUMBER_COLUMN} gaps at {gaps}", file=sys.stderr)

    blank = [n for n, row in zip(numbers, rows) if not (row.get(ABBREVIATION_COLUMN) or "").strip()]
    if blank:
        raise AuthorListError(f"{source}: blank {ABBREVIATION_COLUMN} at author(s) {blank}")

    if core + senior > len(rows):
        raise AuthorListError(
            f"{core} core + {senior} senior authors exceeds the {len(rows)} on the roster"
        )
    if first_marks > core or senior_marks > senior:
        raise AuthorListError("more equal-contribution marks than authors in that group")
    if core_team_first + core_team_last > len(rows):
        raise AuthorListError(
            f"{core_team_first} + {core_team_last} core-team marks exceeds the "
            f"{len(rows)} on the roster"
        )

    names = disambiguate([normalise(row[ABBREVIATION_COLUMN]) for row in rows], rows)
    marks: list[list[str]] = [[] for _ in names]
    for index in range(first_marks):
        marks[index].append(FIRST_AUTHOR_MARK)
    for index in range(1, senior_marks + 1):
        marks[-index].append(SENIOR_AUTHOR_MARK)
    core_team = list(range(core_team_first))
    core_team += range(len(names) - core_team_last, len(names))
    for index in core_team:
        marks[index].append(CORE_TEAM_MARK)

    typeset = [to_latex(name, mark) for name, mark in zip(names, marks)]
    groups = [
        ("Core team", typeset[:core]),
        ("Contributors", typeset[core : len(typeset) - senior]),
        ("Senior authors", typeset[len(typeset) - senior :]),
    ]

    header = (
        f"% Generated by compile_authors.py from {Path(source).name!r}.\n"
        f"% {len(names)} authors. Edit the Google Sheet and regenerate; do not edit by hand.\n"
        "%\n"
        "% Put the contribution note in the title's \\thanks{...}:\n"
        f"%   {THANKS}\n"
        "\n"
        "\\newcommand{\\authorcontributions}{%\n"
        f"  {superscript([FIRST_AUTHOR_MARK])}Equal contribution as first authors.\n"
        f"  {superscript([SENIOR_AUTHOR_MARK])}Equal contribution as senior authors.\n"
        f"  {superscript([CORE_TEAM_MARK])}Core team.%\n"
        "}\n"
    )
    tex = f"{header}\n\\author{{%\n{build_block(groups, per_line)}\n}}\n"
    return tex, {label: group for label, group in groups}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--csv",
        default=str(DEFAULT_CSV),
        help="CSV path or export URL (default: authors.csv beside this script)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"output .tex (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--institutions-out",
        type=Path,
        default=DEFAULT_INSTITUTIONS_OUT,
        help=f"output .tex for the institution list (default: {DEFAULT_INSTITUTIONS_OUT})",
    )
    parser.add_argument(
        "--core", type=int, default=CORE, help=f"authors in the core-team row (default: {CORE})"
    )
    parser.add_argument(
        "--senior", type=int, default=SENIOR, help=f"authors in the senior row (default: {SENIOR})"
    )
    parser.add_argument(
        "--equal-first",
        type=int,
        default=EQUAL_FIRST,
        help=f"leading authors marked * (default: {EQUAL_FIRST})",
    )
    parser.add_argument(
        "--equal-senior",
        type=int,
        default=EQUAL_SENIOR,
        help=f"trailing authors marked \u2020 (default: {EQUAL_SENIOR})",
    )
    parser.add_argument(
        "--core-team-first",
        type=int,
        default=CORE_TEAM_FIRST,
        help=f"leading authors marked \u00a7 as core team (default: {CORE_TEAM_FIRST})",
    )
    parser.add_argument(
        "--core-team-last",
        type=int,
        default=CORE_TEAM_LAST,
        help=f"trailing authors marked \u00a7 as core team (default: {CORE_TEAM_LAST})",
    )
    parser.add_argument(
        "--per-line", type=int, default=8, help="names per source line (default: 8)"
    )
    parser.add_argument(
        "--print", action="store_true", help="write to stdout instead of the output files"
    )
    args = parser.parse_args()

    try:
        source = args.csv
        rows = read_rows(source)
        institutions = compile_institutions(rows, source)
        tex, groups = compile_authors(
            rows,
            source,
            args.core,
            args.senior,
            args.equal_first,
            args.equal_senior,
            args.core_team_first,
            args.core_team_last,
            args.per_line,
        )
    except AuthorListError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.print:
        sys.stdout.write(tex)
        sys.stdout.write("\n" + institutions)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(tex, encoding="utf-8")
        print(f"wrote {args.out}")
        args.institutions_out.parent.mkdir(parents=True, exist_ok=True)
        args.institutions_out.write_text(institutions, encoding="utf-8")
        print(f"wrote {args.institutions_out}")

    total = sum(len(names) for names in groups.values())
    print(f"{total} authors from {source}", file=sys.stderr)
    for label, names in groups.items():
        if names:
            plain = [MARKUP.sub("", MBOX.sub(r"\1", name)) for name in names]
            preview = ", ".join(plain)
            print(f"  {label} ({len(names)}): {preview[:96]}", file=sys.stderr)

    print("\nTitle \\thanks (\\authorcontributions is defined in the output):")
    print(THANKS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
