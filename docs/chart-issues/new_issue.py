# /// script
# requires-python = ">=3.12"
# dependencies = ["questionary>=2.1"]
# ///
"""Start a chart issue: one entry per chart, listing every problem in it with its own severity.

    uv run docs/chart-issues/new_issue.py "Sales by channel"
    uv run docs/chart-issues/new_issue.py "Sales by channel" --type pie \\
        --problem "Labels overlap:medium:4.2" --problem "Seven slices:high:2.3,4.1"
    uv run docs/chart-issues/new_issue.py --suggest
    uv run docs/chart-issues/new_issue.py --sync

For each problem it offers the standards related to the chart type as a checklist, with "Other" for the rest and
"Suggest a new standard" for a rule that doesn't exist yet. Suggestions go to docs/standards-suggestions.md for
review. The index in README.md, the issue links in the standards checklist and the rule text in each entry are
rebuilt from the entries every time; after editing an entry or approving a suggestion, run --sync.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEVERITIES = ("high", "medium", "low")
STANDARDS_LINK = "../visualization-standards.md"
SUGGESTIONS_LINK = "../standards-suggestions.md"
ROW = re.compile(r"^\| (\d+) \| (.+?) \| (high|medium|low) \| ([^|]+?) \| (.*?) \|$", re.M)
SUGGESTION_ROW = re.compile(
    r"^\| (S-\d+) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (proposed|approved|rejected) \| (.*?) \|$", re.M)

# Standards offered first for a chart type, matched by words in the type. The rest are one "Other" away.
COMMON = ("1.1", "3.7", "4.2", "4.5", "4.6", "5.1", "5.2", "6.1", "6.4", "8.3")
CHART_STANDARDS = {
    ("bar", "column"): ("2.2", "2.11", "3.1", "4.1", "4.3", "4.4"),
    ("line",): ("2.1", "3.1", "3.5", "3.6", "3.9", "4.4"),
    ("area",): ("2.1", "2.4", "3.1", "3.4", "3.9"),
    ("stack",): ("2.4", "3.1", "3.4"),
    ("pie", "donut"): ("2.3", "2.9", "3.4", "4.1", "5.4"),
    ("scatter", "bubble"): ("2.6", "3.2", "3.3", "3.6", "4.4"),
    ("histogram", "box"): ("2.5", "3.1", "4.1", "4.4"),
    ("table",): ("2.10", "7.1"),
    ("indicator", "card", "kpi"): ("2.7", "5.3"),
    ("dual", "two axes"): ("2.8", "4.4"),
    ("not delivered", "no chart", "refused", "failed"): ("1.4", "7.1", "7.3", "8.2"),
}
OTHER, SUGGEST = "__other__", "__suggest__"


@dataclass(frozen=True)
class Standard:
    number: str
    text: str
    anchor: str

    def link(self) -> str:
        # No #section: the Markdown preview treats it as part of the file name. The title shows the rule on hover.
        return f'[{self.number}]({STANDARDS_LINK} "{_title(self.text)}")'


@dataclass(frozen=True)
class Suggestion:
    sid: str
    text: str
    section: str
    status: str = "proposed"
    decision: str = ""

    def link(self) -> str:
        return f'[{self.sid}]({SUGGESTIONS_LINK} "Suggested: {_title(self.text)}")'


@dataclass(frozen=True)
class Problem:
    title: str
    severity: str
    standards: tuple[Standard, ...]
    status: str = "open"
    suggestions: tuple[Suggestion, ...] = field(default=())


@dataclass(frozen=True)
class Entry:
    issue_id: str
    title: str
    path: Path
    problems: tuple[Problem, ...]


def _title(text: str) -> str:
    return text.replace('"', "'")


def _cell(text: str) -> str:
    return " ".join(text.replace("|", "/").split())


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9 -]", "", text.lower()).strip().replace(" ", "-")


def load_standards(path: Path) -> list[Standard]:
    """Every checklist rule, with the detailed section it belongs to."""
    text = path.read_text(encoding="utf-8")
    anchors = {m.group(1): slug(f"{m.group(1)}. {m.group(2)}")
               for m in re.finditer(r"^### (\d+)\. (.+)$", text, re.M)}
    rules = []
    for m in re.finditer(r"^- \[ \] \*\*(\d+\.\d+)\*\* (.+)$", text, re.M):
        plain = re.sub(r"\s*\(\[CI-\d+\].*$", "", m.group(2)).strip()
        rules.append(Standard(m.group(1), plain, anchors.get(m.group(1).split(".")[0], "")))
    return rules


def load_sections(path: Path) -> list[str]:
    """The numbered sections of the standards, e.g. '4. Readability', for placing a suggestion."""
    text = path.read_text(encoding="utf-8")
    return [f"{m.group(1)}. {m.group(2)}" for m in re.finditer(r"^### (\d+)\. (.+)$", text, re.M)
            if not m.group(2).startswith("Not adopted")]


def _ordered(rules) -> list[Standard]:
    return sorted(rules, key=lambda s: [int(n) for n in s.number.split(".")])


def related_standards(kind: str, rules: list[Standard]) -> list[Standard]:
    """The rules most likely to matter for this chart type, then the common ones."""
    words = kind.lower()
    numbers = [n for keys, picks in CHART_STANDARDS.items() if any(k in words for k in keys) for n in picks]
    by_number = {s.number: s for s in rules}
    chosen = dict.fromkeys(n for n in [*numbers, *COMMON] if n in by_number)
    return _ordered(by_number[n] for n in chosen)


# Suggestions --------------------------------------------------------------------------------------------------------

def load_suggestions(path: Path) -> dict[str, Suggestion]:
    if not path.exists():
        return {}
    return {m.group(1): Suggestion(m.group(1), m.group(2), m.group(3), m.group(6), m.group(7).strip())
            for m in SUGGESTION_ROW.finditer(path.read_text(encoding="utf-8"))}


def add_suggestion(path: Path, text: str, section: str, why: str, source: str) -> Suggestion:
    """Append a proposed rule to the suggestions table and return it."""
    content = path.read_text(encoding="utf-8")
    numbers = [int(sid[2:]) for sid in load_suggestions(path)]
    suggestion = Suggestion(f"S-{max(numbers, default=0) + 1:03d}", _cell(text), _cell(section))
    row = (f"| {suggestion.sid} | {suggestion.text} | {suggestion.section} | {_cell(why) or '–'} | "
           f"{source or '–'} | proposed | – |")
    lines = content.split("\n")
    table_rows = [i for i, line in enumerate(lines) if line.startswith("| S-") or line.startswith("| ---")]
    lines.insert(max(table_rows) + 1, row)
    path.write_text("\n".join(lines), encoding="utf-8")
    return suggestion


# Choosing standards -------------------------------------------------------------------------------------------------

def pick_standards(rules: list[Standard], read=input, write=print) -> list[Standard]:
    """Search by words or rule number; pick results by their list number; an empty line finishes."""
    chosen: list[Standard] = []
    shown: list[Standard] = []
    write("  Search the standards by words or rule number (for example: zero, label, 4.2).")
    write("  Type list numbers to pick or unpick results; press Enter on an empty line when done.")
    while True:
        answer = read("  > ").strip()
        if not answer:
            return _ordered(chosen)
        if all(part.isdigit() for part in answer.split()) and shown:
            for part in answer.split():
                index = int(part) - 1
                if 0 <= index < len(shown):
                    rule = shown[index]
                    if rule in chosen:
                        chosen.remove(rule)
                    else:
                        chosen.append(rule)
            write("  Picked: " + (", ".join(s.number for s in _ordered(chosen)) or "none"))
            continue
        words = answer.lower().split()
        shown = [s for s in rules if all(w in f"{s.number} {s.text}".lower() for w in words)]
        if not shown:
            write("  No standard matches. Try other words.")
        for i, rule in enumerate(shown, start=1):
            mark = "*" if rule in chosen else " "
            write(f"  {mark}{i:>2}. {rule.number:<5} {rule.text}")


def _suggest_typed(sections: list[str], read, write) -> tuple[str, str, str] | None:
    text = read("  The rule you'd add, in one line (empty to cancel): ").strip()
    if not text:
        return None
    for i, name in enumerate(sections, start=1):
        write(f"    {i}. {name}")
    answer = read("  Which section? [number]: ").strip()
    section = sections[int(answer) - 1] if answer.isdigit() and 0 < int(answer) <= len(sections) else "–"
    why = read("  Why is it needed? ").strip()
    return text, section, why


def choose_typed(kind: str, rules: list[Standard], sections: list[str], read=input, write=print):
    """Numbered menu: related standards, 'o' for all the others, 's' to suggest a new one."""
    related = related_standards(kind, rules)
    chosen: list[Standard] = []
    suggested: list[tuple[str, str, str]] = []
    write(f"  Standards related to {kind or 'this chart'}:")
    for i, rule in enumerate(related, start=1):
        write(f"    {i:>2}. {rule.number:<5} {rule.text}")
    write("     o. Other: search all standards")
    write("     s. Suggest a new standard")
    while True:
        answer = read("  Pick numbers (e.g. 1 3), o or s; Enter when done: ").strip().lower()
        if not answer:
            return _ordered(dict.fromkeys(chosen)), suggested
        for part in answer.split():
            if part.isdigit() and 0 < int(part) <= len(related):
                rule = related[int(part) - 1]
                chosen.remove(rule) if rule in chosen else chosen.append(rule)
            elif part == "o":
                chosen.extend(s for s in pick_standards(rules, read, write) if s not in chosen)
            elif part == "s" and (proposal := _suggest_typed(sections, read, write)):
                suggested.append(proposal)
        write("  Picked: " + (", ".join(s.number for s in _ordered(chosen)) or "none")
              + (f"; {len(suggested)} suggested" if suggested else ""))


def choose_with_checkboxes(kind: str, rules: list[Standard], sections: list[str]):
    """Arrow keys and space to pick; 'Other' opens every remaining standard with type-to-filter."""
    import questionary

    related = related_standards(kind, rules)
    choices = [questionary.Choice(f"{s.number:<5} {s.text}", value=s) for s in related]
    choices += [questionary.Separator(), questionary.Choice("Other: show all standards", value=OTHER),
                questionary.Choice("Suggest a new standard", value=SUGGEST)]
    picked = questionary.checkbox(f"Which standards does it break? (related to {kind or 'this chart'})",
                                  choices=choices, instruction="(space to pick, enter when done)").ask()
    if picked is None:
        raise SystemExit("Cancelled.")
    chosen = [p for p in picked if isinstance(p, Standard)]
    if OTHER in picked:
        rest = [s for s in rules if s not in related]
        more = questionary.checkbox("All other standards (type to filter)", use_search_filter=True,
                                    use_jk_keys=False, instruction="(space to pick, enter when done)",
                                    choices=[questionary.Choice(f"{s.number:<5} {s.text}", value=s) for s in rest]).ask()
        chosen += more or []
    suggested = []
    while SUGGEST in picked:
        text = questionary.text("The rule you'd add, in one line:").ask()
        if not text:
            break
        section = questionary.select("Which section?", choices=sections).ask() or "–"
        why = questionary.text("Why is it needed?").ask() or ""
        suggested.append((text, section, why))
        if not questionary.confirm("Suggest another?", default=False).ask():
            break
    return _ordered(chosen), suggested


def _interactive() -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        import questionary  # noqa: F401
    except ImportError:
        return False
    return True


def ask_problems(rules: list[Standard], kind: str, sections: list[str], suggestions_path: Path, issue_id: str,
                 entry_name: str, read=input, write=print, checkboxes: bool | None = None) -> list[Problem]:
    checkboxes = _interactive() if checkboxes is None else checkboxes
    problems = []
    while True:
        title = read(f"Problem {len(problems) + 1} in a few words (empty line when done): ").strip()
        if not title:
            return problems
        severity = ""
        while severity not in SEVERITIES:
            severity = read("  Severity (high, medium, low) [medium]: ").strip().lower() or "medium"
        if checkboxes:
            chosen, proposals = choose_with_checkboxes(kind, rules, sections)
        else:
            chosen, proposals = choose_typed(kind, rules, sections, read, write)
        source = f"[{issue_id}](chart-issues/{entry_name})"
        added = tuple(add_suggestion(suggestions_path, text, section, why, source) for text, section, why in proposals)
        problems.append(Problem(title, severity, tuple(chosen), suggestions=added))


def parse_problem(text: str, rules: list[Standard]) -> Problem:
    """'Labels overlap:medium:4.2,5.4' from the command line."""
    title, _, rest = text.partition(":")
    severity, _, numbers = rest.partition(":")
    by_number = {s.number: s for s in rules}
    wanted = [n.strip() for n in numbers.split(",") if n.strip()]
    unknown = [n for n in wanted if n not in by_number]
    if not title.strip() or severity not in SEVERITIES or unknown:
        raise SystemExit(f"bad --problem {text!r}: use 'title:high|medium|low:4.2,5.4'"
                         + (f"; unknown standards {', '.join(unknown)}" if unknown else ""))
    return Problem(title.strip(), severity, tuple(_ordered(by_number[n] for n in wanted)))


# Writing and syncing ------------------------------------------------------------------------------------------------

def _refs(problem: Problem) -> str:
    return ", ".join([*(s.link() for s in problem.standards), *(s.link() for s in problem.suggestions)]) or "–"


def entry_text(template: str, issue_id: str, title: str, kind: str, problems: list[Problem]) -> str:
    rows = "\n".join(f"| {i} | {p.title} | {p.severity} | open | {_refs(p)} |" for i, p in enumerate(problems, start=1))
    sections = "\n\n".join(
        f"### {i}. {p.title}\n\n"
        "- **Seen.** What the chart shows, in one or two sentences.\n"
        "- **Expected.** What a correct chart shows.\n"
        "- **Cause.** Where it goes wrong, with `file:line`. \"Not traced yet\" until it is known."
        for i, p in enumerate(problems, start=1))
    head, _, rest = template.partition("\n")
    head = f"# {issue_id}: {title}" + (f" ({kind})" if kind else "")
    table_start = rest.index("| # | Problem |")
    evidence = rest.index("**Evidence.**")
    table = "| # | Problem | Severity | Status | Standard |\n| --- | --- | --- | --- | --- |\n" + rows
    return head + "\n" + rest[:table_start] + table + "\n\n" + sections + "\n\n" + rest[evidence:]


def read_entries(folder: Path, rules: list[Standard]) -> list[Entry]:
    by_number = {s.number: s for s in rules}
    entries = []
    for path in sorted(folder.glob("[0-9]*.md")):
        text = path.read_text(encoding="utf-8")
        head = re.match(r"# (CI-\d+): (.+)", text)
        if not head:
            continue
        problems = tuple(
            Problem(m.group(2), m.group(3), tuple(by_number[n] for n in re.findall(r"\[(\d+\.\d+)\]", m.group(5))
                                                  if n in by_number), m.group(4).strip())
            for m in ROW.finditer(text))
        entries.append(Entry(head.group(1), head.group(2), path, problems))
    return sorted(entries, key=lambda e: int(e.issue_id[3:]))


def next_id(folder: Path) -> str:
    numbers = [int(m.group(1)) for p in folder.glob("[0-9]*.md")
               if (m := re.match(r"# CI-(\d+):", p.read_text(encoding="utf-8")))]
    return f"CI-{max(numbers, default=0) + 1:03d}"


def file_name(title: str, day: date) -> str:
    name, length = [], 0
    for word in filter(None, slug(title).split("-")):
        if length + len(word) > 60:
            break
        name.append(word)
        length += len(word) + 1
    return f"{day.isoformat()}-{'-'.join(name) or 'issue'}.md"


def summary(problems) -> str:
    counts = [f"{sum(p.severity == s for p in problems)} {s}" for s in SEVERITIES
              if any(p.severity == s for p in problems)]
    fixed = sum(p.status == "fixed" for p in problems)
    return ", ".join(counts) + (f" ({fixed} fixed)" if fixed else "")


def annotate(path: Path, rules: list[Standard], suggestions: dict[str, Suggestion]) -> None:
    """Write each cited rule's text into the entry: as a hover title in the table, and as a Standard line per problem.

    The preview can't jump to a section of the standards file, so the rule is shown where it is cited. A suggestion
    that has been approved as a rule is replaced by that rule."""
    by_number = {s.number: s for s in rules}
    text = path.read_text(encoding="utf-8")
    cited: dict[str, list] = {}

    def row(m: re.Match) -> str:
        numbers = re.findall(r"\[(\d+\.\d+)\]", m.group(5))
        pending = []
        for sid in re.findall(r"\[(S-\d+)\]", m.group(5)):
            suggestion = suggestions.get(sid)
            if suggestion and suggestion.status == "approved" and suggestion.decision in by_number:
                numbers.append(suggestion.decision)
            elif suggestion:
                pending.append(suggestion)
        found = _ordered({by_number[n] for n in numbers if n in by_number})
        cited[m.group(1)] = [*found, *pending]
        cell = ", ".join(s.link() for s in cited[m.group(1)]) or "–"
        return f"| {m.group(1)} | {m.group(2)} | {m.group(3)} | {m.group(4)} | {cell} |"

    text = ROW.sub(row, text)
    text = re.sub(r"^- \*\*Standard\.\*\*.*\n(?:  - .*\n)*", "", text, flags=re.M)

    def describe(ref) -> str:
        if isinstance(ref, Suggestion):
            return f"{ref.link()} ({ref.status} suggestion) {ref.text}"
        return f"{ref.link()} {ref.text}"

    def section(m: re.Match) -> str:
        found = cited.get(m.group(1), [])
        if not found:
            return m.group(0)
        if len(found) == 1:
            line = f"- **Standard.** {describe(found[0])}\n"
        else:
            line = "- **Standard.**\n" + "".join(f"  - {describe(r)}\n" for r in found)
        body = m.group(0)
        cause = re.search(r"^- \*\*Cause\.\*\*", body, re.M)
        if cause:
            return body[:cause.start()] + line + body[cause.start():]
        return body.rstrip("\n") + "\n" + line + "\n"

    text = re.sub(r"^### (\d+)\. .*?(?=^### |^\*\*Evidence\.\*\*|\Z)", section, text, flags=re.M | re.S)
    path.write_text(text, encoding="utf-8")


def sync(folder: Path) -> None:
    """Rebuild the README index, the checklist's issue links and the rule text in every entry."""
    standards_path = folder.parent / "visualization-standards.md"
    rules = load_standards(standards_path)
    suggestions = load_suggestions(folder.parent / "standards-suggestions.md")
    for path in folder.glob("[0-9]*.md"):
        annotate(path, rules, suggestions)
    entries = read_entries(folder, rules)

    rows = []
    for e in entries:
        still_open = [p for p in e.problems if p.status not in ("fixed", "withdrawn")]
        ranked = still_open or list(e.problems)
        highest = next((s for s in SEVERITIES if any(p.severity == s for p in ranked)), "–")
        rows.append(f"| [{e.issue_id}]({e.path.name}) | {e.title} | {summary(e.problems)} | {highest} | "
                    f"{'open' if still_open else 'fixed'} |")
    readme = folder / "README.md"
    text = readme.read_text(encoding="utf-8")
    header = "| ID | Chart | Problems | Highest severity | Status |\n| --- | --- | --- | --- | --- |\n"
    table = re.compile(r"^\| ID \|[^\n]*\n\| ---[^\n]*\n(?:\| \[CI-[^\n]*\n)*", re.M)
    if not table.search(text):
        raise SystemExit("README.md has no index table starting with '| ID |'.")
    text = table.sub(lambda _: header + "\n".join(rows) + "\n", text, count=1)
    readme.write_text(text, encoding="utf-8")

    broken: dict[str, list[Entry]] = {}
    for e in entries:
        for number in {s.number for p in e.problems for s in p.standards}:
            broken.setdefault(number, []).append(e)
    standards = standards_path.read_text(encoding="utf-8")

    def relink(m: re.Match) -> str:
        line = re.sub(r"\s*\(\[CI-\d+\].*\)$", "", m.group(0))
        found = broken.get(m.group(1), [])
        links = ", ".join(f"[{e.issue_id}](chart-issues/{e.path.name})" for e in found)
        return f"{line} ({links})" if links else line

    standards_path.write_text(re.sub(r"^- \[ \] \*\*(\d+\.\d+)\*\* .+$", relink, standards, flags=re.M),
                              encoding="utf-8")


def create(folder: Path, path: Path, issue_id: str, title: str, kind: str, problems: list[Problem]) -> Path:
    template = (folder / "TEMPLATE.md").read_text(encoding="utf-8")
    path.write_text(entry_text(template, issue_id, title, kind, problems), encoding="utf-8")
    sync(folder)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start a chart issue, suggest a standard, or rebuild the links.")
    parser.add_argument("title", nargs="?", help="The chart, in a few words, e.g. 'Sales by channel'.")
    parser.add_argument("--type", default=None, help="The chart type, e.g. 'pie' or 'horizontal bars'.")
    parser.add_argument("--problem", action="append", default=[],
                        help="'title:severity:standards', e.g. 'Labels overlap:medium:4.2'. Repeat for each problem.")
    parser.add_argument("--date", type=date.fromisoformat, default=date.today(), help="Date seen (YYYY-MM-DD).")
    parser.add_argument("--suggest", action="store_true", help="Only suggest a new standard for review.")
    parser.add_argument("--sync", action="store_true", help="Only rebuild the index, the links and the rule text.")
    parser.add_argument("--folder", type=Path, default=HERE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    folder = args.folder.resolve()
    standards_path = folder.parent / "visualization-standards.md"
    suggestions_path = folder.parent / "standards-suggestions.md"

    if args.sync:
        sync(folder)
        print("Rebuilt the index, the standards links and the rule text in every entry.")
        return 0
    if args.suggest:
        proposal = _suggest_typed(load_sections(standards_path), input, print)
        if proposal:
            suggestion = add_suggestion(suggestions_path, *proposal, source="–")
            print(f"Added {suggestion.sid} to {suggestions_path.name} for review.")
        return 0

    title = args.title or input("Which chart, in a few words? ").strip()
    if not title:
        parser.error("a chart title is needed")
    kind = args.type if args.type is not None else input("Chart type (e.g. pie, horizontal bars): ").strip()
    rules = load_standards(standards_path)
    issue_id = next_id(folder)
    path = folder / file_name(title, args.date)
    if path.exists():
        raise SystemExit(f"{path.name} already exists; choose another title.")
    problems = [parse_problem(p, rules) for p in args.problem] or ask_problems(
        rules, kind, load_sections(standards_path), suggestions_path, issue_id, path.name)
    if not problems:
        parser.error("list at least one problem")
    create(folder, path, issue_id, title, kind, problems)
    print(f"Created {path.name} ({issue_id}) with {len(problems)} problem(s); updated the index and the links.")
    print("Fill in Asked, Data, each problem's Seen, Expected and Cause, Evidence, and add the image.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
