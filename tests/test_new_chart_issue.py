"""The chart-issue starter: one entry per chart, the index and the standards links rebuilt from the entries."""

import importlib.util
import shutil
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ISSUES = ROOT / "docs" / "chart-issues"
STANDARDS = ROOT / "docs" / "visualization-standards.md"
spec = importlib.util.spec_from_file_location("new_issue", ISSUES / "new_issue.py")
new_issue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(new_issue)


def _copy_log(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    folder = docs / "chart-issues"
    folder.mkdir(parents=True)
    shutil.copy(STANDARDS, docs)
    shutil.copy(ROOT / "docs" / "standards-suggestions.md", docs)
    for path in [ISSUES / "README.md", ISSUES / "TEMPLATE.md", *ISSUES.glob("[0-9]*.md")]:
        shutil.copy(path, folder)
    return folder


def test_every_checklist_rule_is_loaded_with_its_section():
    rules = {rule.number: rule for rule in new_issue.load_standards(STANDARDS)}
    assert rules["4.4"].anchor == "4-readability"
    assert rules["2.11"].text.startswith("A ranking or top N")
    assert "CI-" not in rules["4.4"].text


def test_the_logged_entries_are_read_with_their_problems():
    entries = new_issue.read_entries(ISSUES, new_issue.load_standards(STANDARDS))
    assert entries and all(entry.problems for entry in entries)
    assert all(p.severity in new_issue.SEVERITIES for entry in entries for p in entry.problems)


def test_a_new_chart_issue_lists_each_problem_and_updates_index_and_standards(tmp_path):
    folder = _copy_log(tmp_path)
    expected_id = new_issue.next_id(folder)
    readme_tail = (folder / "README.md").read_text().split("## Adding an issue")[1]

    new_issue.main(["Sales by channel", "--type", "pie", "--problem", "Labels overlap:medium:4.2",
                    "--problem", "Seven slices:high:2.3,4.1", "--date", "2026-11-02", "--folder", str(folder)])

    path = folder / "2026-11-02-sales-by-channel.md"
    body = path.read_text()
    assert body.startswith(f"# {expected_id}: Sales by channel (pie)\n")
    rule = '[4.2](../visualization-standards.md "Every category name shows; labels are never dropped silently.")'
    assert f"| 1 | Labels overlap | medium | open | {rule} |" in body
    assert f"- **Standard.** {rule} Every category name shows; labels are never dropped silently.\n- **Cause.**" in body
    assert "| 2 | Seven slices | high | open |" in body
    assert "### 1. Labels overlap" in body and "### 2. Seven slices" in body
    assert body.rstrip().endswith("depends on them.")

    readme = (folder / "README.md").read_text()
    assert f"| [{expected_id}]({path.name}) | Sales by channel (pie) | 1 high, 1 medium | high | open |" in readme
    assert readme.split("## Adding an issue")[1] == readme_tail
    standards = (tmp_path / "docs" / "visualization-standards.md").read_text()
    line = next(line for line in standards.split("\n") if line.startswith("- [ ] **2.3**"))
    assert f"[{expected_id}](chart-issues/{path.name})" in line


def test_sync_marks_a_chart_fixed_when_every_problem_is(tmp_path):
    folder = _copy_log(tmp_path)
    new_issue.main(["Tiny chart", "--type", "bar", "--problem", "One flaw:low:4.5", "--folder", str(folder)])
    path = next(folder.glob("*-tiny-chart.md"))
    path.write_text(path.read_text().replace("| low | open |", "| low | fixed |"))

    new_issue.main(["--sync", "--folder", str(folder)])

    row = next(line for line in (folder / "README.md").read_text().split("\n") if path.name in line)
    assert row.endswith("| 1 low (1 fixed) | low | fixed |")


def test_the_search_picks_and_unpicks_by_list_number():
    rules = new_issue.load_standards(STANDARDS)
    answers = iter(["zero", "1", "label", "1 1", "contrast", "1", ""])
    picked = new_issue.pick_standards(rules, read=lambda _: next(answers), write=lambda _: None)
    assert [rule.number for rule in picked] == ["3.1", "3.8"]


def test_a_badly_written_problem_is_refused():
    rules = new_issue.load_standards(STANDARDS)
    with pytest.raises(SystemExit):
        new_issue.parse_problem("Labels overlap:urgent:4.2", rules)
    with pytest.raises(SystemExit):
        new_issue.parse_problem("Labels overlap:medium:9.9", rules)


def test_the_file_name_is_dated_and_short():
    name = new_issue.file_name("A very long title about the horizontal bars that lose every label they have",
                               date(2026, 11, 2))
    assert name.startswith("2026-11-02-a-very-long-title")
    assert len(name) <= len("2026-11-02-") + 60 + len(".md")


def test_sync_is_stable_on_the_logged_entries(tmp_path):
    folder = _copy_log(tmp_path)
    new_issue.main(["--sync", "--folder", str(folder)])
    first = {p.name: p.read_text() for p in folder.glob("*.md")}
    new_issue.main(["--sync", "--folder", str(folder)])
    assert {p.name: p.read_text() for p in folder.glob("*.md")} == first


def test_every_chart_type_mapping_names_real_standards():
    numbers = {rule.number for rule in new_issue.load_standards(STANDARDS)}
    mapped = {n for picks in new_issue.CHART_STANDARDS.values() for n in picks} | set(new_issue.COMMON)
    assert mapped <= numbers


def test_related_standards_put_the_chart_type_first():
    rules = new_issue.load_standards(STANDARDS)
    pie = [rule.number for rule in new_issue.related_standards("donut", rules)]
    assert {"2.3", "3.4", "5.4"} <= set(pie) and "2.6" not in pie
    assert {"2.6", "3.2"} <= {rule.number for rule in new_issue.related_standards("scatter", rules)}


def _answers(*lines):
    it = iter(lines)
    return lambda _: next(it)


def test_a_suggested_standard_is_logged_cited_and_replaced_once_approved(tmp_path):
    folder = _copy_log(tmp_path)
    docs = folder.parent
    rules = new_issue.load_standards(docs / "visualization-standards.md")
    sections = new_issue.load_sections(docs / "visualization-standards.md")
    read = _answers("Labels overlap", "medium",
                    "2", "o", "zero", "1", "",
                    "s", "A donut shows its total in the middle", "4", "Readers want the whole", "",
                    "")
    problems = new_issue.ask_problems(rules, "donut", sections, docs / "standards-suggestions.md", "CI-099",
                                      "2026-11-02-sales.md", read=read, write=lambda _: None, checkboxes=False)
    assert [s.number for s in problems[0].standards] == ["2.3", "3.1"]
    (suggestion,) = problems[0].suggestions
    log = (docs / "standards-suggestions.md").read_text()
    assert f"| {suggestion.sid} | A donut shows its total in the middle | 4. Readability |" in log
    assert "[CI-099](chart-issues/2026-11-02-sales.md) | proposed | – |" in log

    new_issue.main(["Sales", "--type", "donut", "--problem", "x:low:4.5", "--date", "2026-11-02",
                    "--folder", str(folder)])
    entry = folder / "2026-11-02-sales.md"
    entry.write_text(entry.read_text().replace("| 1 | x | low | open |",
                                               f"| 1 | x | low | open | [{suggestion.sid}](../standards-suggestions.md), "))
    new_issue.main(["--sync", "--folder", str(folder)])
    assert "(proposed suggestion) A donut shows its total in the middle" in entry.read_text()

    log_path = docs / "standards-suggestions.md"
    log_path.write_text(log_path.read_text().replace("| proposed | – |", "| approved | 4.2 |"))
    new_issue.main(["--sync", "--folder", str(folder)])
    body = entry.read_text()
    assert suggestion.sid not in body and "[4.2](../visualization-standards.md" in body
