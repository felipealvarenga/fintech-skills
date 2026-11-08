import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import run_evals as runner


@pytest.fixture
def runner_args(tmp_path):
    return runner.cli_parser().parse_args([
        "--skill", "money-arithmetic", "--agent", "fake", "--results-dir", str(tmp_path / "results")])


@pytest.fixture(autouse=True)
def isolated_metadata(monkeypatch):
    monkeypatch.setattr(runner, "repository_state", lambda: ("abcdef0123456789", False))


def test_cli_defaults():
    args = runner.cli_parser().parse_args(["--all"])
    assert vars(args) == {
        "skill": None, "all": True, "subject_model": "claude-sonnet-5-5",
        "grader_model": "claude-sonnet-5-5", "runs": 1, "max_turns": 30,
        "timeout": 900, "budget": 80, "results_dir": runner.ROOT / "evals" / "results", "agent": "claude"}


@pytest.mark.parametrize("selection", [[], ["--skill", "missing"], ["--all", "--skill", "money-tests"]])
def test_selection(selection, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "fake_session", lambda *a: calls.append(a))
    with pytest.raises(SystemExit) as exc:
        runner.eval_main(selection + ["--agent", "fake", "--results-dir", str(tmp_path / "results")])
    assert exc.value.code != 0
    assert calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("selection,budget,prompts,subjects,total,allowed", [
    (["--all"], 80, 91, 182, 364, False),
    (["--all"], 364, 91, 182, 364, True),
    (["--skill", "money-tests"], 80, 7, 14, 28, True),
    (["--skill", "money-tests", "--skill", "money-arithmetic"], 80, 14, 28, 56, True),
])
def test_budget_plan(selection, budget, prompts, subjects, total, allowed, tmp_path, monkeypatch, capsys):
    calls = []
    original = runner.fake_session
    monkeypatch.setattr(runner, "fake_session", lambda *a: (calls.append(a[0]), original(*a))[1])
    result = runner.eval_main(selection + ["--agent", "fake", "--budget", str(budget),
                                           "--results-dir", str(tmp_path / "results")])
    output = capsys.readouterr()
    assert f"prompts={prompts}, conditions=2, runs=1, subject sessions={subjects}, grader sessions={subjects}, total={total}, budget={budget}" in output.out
    assert result == (0 if allowed else 1)
    assert len(calls) == (total if allowed else 0)
    if not allowed:
        assert "364" in output.err and "--budget" in output.err
        assert list(tmp_path.iterdir()) == []


def test_existing_run(tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(runner, "fake_session", lambda *a: calls.append(a))
    class FixedDate:
        @staticmethod
        def now(zone):
            return SimpleNamespace(strftime=lambda _: "20261108T030000Z")
    monkeypatch.setattr(runner, "datetime", FixedDate)
    directory = tmp_path / "20261108T030000Z-abcdef0"
    directory.mkdir()
    (directory / "summary.md").write_text("keep me")
    assert runner.eval_main(["--skill", "money-tests", "--agent", "fake", "--results-dir", str(tmp_path)]) == 1
    assert "already exist" in capsys.readouterr().err
    assert calls == []
    assert (directory / "summary.md").read_text() == "keep me"
    assert list(directory.iterdir()) == [directory / "summary.md"]


@pytest.mark.parametrize("name,skill_names", [
    ("money-arithmetic", ["money-arithmetic"]),
    ("fintech-audit", ["accounting-sync", "audit-trail", "brazil-payment-rails", "double-entry-ledger",
                       "fintech-audit", "idempotent-payments", "interest-and-amortization", "money-arithmetic",
                       "money-tests", "pii-and-card-data", "reconciliation", "transaction-classification",
                       "webhook-handling"]),
])
def test_installed_projects(name, skill_names, runner_args, tmp_path, monkeypatch):
    projects = []
    original = runner.fake_session
    expected = {p.relative_to(runner.ROOT / "skills").as_posix(): p.read_bytes()
                for skill_name in skill_names for p in (runner.ROOT / "skills" / skill_name).rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and "evals" not in p.parts}
    def inspect(role, project, prompt):
        assert not project.resolve().is_relative_to(runner.ROOT)
        projects.append(project)
        if role == "subject":
            installed = {p.relative_to(project / ".claude/skills").as_posix(): p.read_bytes()
                         for p in (project / ".claude/skills").rglob("*") if p.is_file()}
            assert installed == (expected if len(projects) == 1 else {})
            assert sorted(p.split("/")[0] for p in installed if p.endswith("/SKILL.md")) == (skill_names if len(projects) == 1 else [])
            assert not any("/evals/" in p for p in installed), "nothing under evals/ reaches the subject"
            if len(projects) == 1:
                assert "money-arithmetic/SKILL.md" in installed
                if name == "fintech-audit":
                    assert len([p for p in installed if p.endswith("/SKILL.md")]) == 13
                    assert "fintech-audit/scripts/money_lint.py" in installed
                else:
                    assert len([p for p in installed if p.endswith("/SKILL.md")]) == 1
            if len(projects) != 1:
                assert not (project / ".claude").exists()
            assert runner.project_files(project) == {}
        else:
            assert list(project.iterdir()) == []
        return original(role, project, prompt)
    monkeypatch.setattr(runner, "fake_session", inspect)
    evaluation = {"id": 1, "prompt": "Synthetic task", "expectations": ["Explains"]}
    for condition in ("with", "without"):
        record, count = runner.evaluate_prompt(runner_args, runner.ROOT / "skills" / name,
                                              evaluation, condition, 1, tmp_path)
        assert count == 2
        assert record["installed_paths"] == ([".claude/skills/" + p for p in sorted(expected)] if condition == "with" else [])
    assert len(set(projects)) == 4
    assert all(not project.exists() for project in projects)


@pytest.mark.parametrize("name", ["/absolute.txt", "../escape.txt", "evals/files/../escape.txt",
                                 "evals/files/missing.txt", "SKILL.md"])
def test_invalid_input_files(name, runner_args, tmp_path, monkeypatch):
    calls, projects = [], []
    original = runner.install_project
    def inspect(skill, evaluation, project, condition):
        projects.append(project)
        return original(skill, evaluation, project, condition)
    monkeypatch.setattr(runner, "install_project", inspect)
    monkeypatch.setattr(runner, "fake_session", lambda *a: calls.append(a))
    evaluation = {"id": 1, "prompt": "Synthetic", "files": [name], "expectations": ["First", "Second"]}
    record, count = runner.evaluate_prompt(runner_args, runner.ROOT / "skills/money-tests", evaluation, "with", 1, tmp_path)
    assert count == 0 and calls == []
    assert [v["status"] for v in record["verdicts"]] == ["error", "error"]
    assert all(name in v["evidence"] for v in record["verdicts"])
    assert all(not project.exists() for project in projects)


@pytest.mark.parametrize("condition", ["with", "without"])
def test_cli_invocations(condition, runner_args, tmp_path):
    evaluation = {"id": 1, "prompt": "Synthetic", "expectations": ["Explains"]}
    record, _ = runner.evaluate_prompt(runner_args, runner.ROOT / "skills/money-tests", evaluation, condition, 1, tmp_path)
    assert record["subject"]["invocation"] == {
        "argv": ["claude", "-p", "--output-format", "json", "--verbose", "--model", "claude-sonnet-5-5",
                 "--max-turns", "30", "--tools", "Read,Write,Edit,Glob,Grep,Skill", "--setting-sources", "project",
                 "--strict-mcp-config", "--permission-mode", "acceptEdits", "--permission-prompts", "none", "--no-session-persistence"],
        "cwd": "<project>", "stdin": "Synthetic", "env": {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"}}
    assert record["grader"]["invocation"]["argv"] == [
        "claude", "-p", "--output-format", "json", "--model", "claude-sonnet-5-5", "--tools", "",
        "--setting-sources", "project", "--strict-mcp-config", "--no-session-persistence"]
    assert record["grader"]["invocation"]["env"] == {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"}


@pytest.mark.parametrize("role", ["subject", "grader"])
def test_real_transport(role, runner_args, tmp_path, monkeypatch):
    runner_args.agent = "claude"
    calls = []
    def transport(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"type":"result","result":"done"}', stderr="")
    monkeypatch.setattr(subprocess, "run", transport)
    monkeypatch.setenv("EVAL_INHERITED_TEST", "inherited")
    monkeypatch.setenv("CLAUDE_CODE_DISABLE_CLAUDE_MDS", "0")
    session = runner.call_session(runner_args, role, tmp_path, "stdin prompt")
    assert len(calls) == 1
    assert calls[0] == (session["invocation"]["argv"], {
        "input": "stdin prompt", "text": True, "capture_output": True, "cwd": tmp_path, "timeout": 900,
        "env": {**os.environ, "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"}})
    assert calls[0][1]["env"]["EVAL_INHERITED_TEST"] == "inherited"
    assert calls[0][1]["env"]["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1"
    assert session["final_answer"] == "done"


@pytest.mark.parametrize("verbose", [False, True])
def test_capture(verbose, runner_args, tmp_path, monkeypatch):
    project_paths = []
    raw_transcripts = []
    def capture(role, project, prompt):
        if role == "grader":
            return json.dumps({"type": "result", "result": '[{"passed":true,"evidence":"yes"}]'})
        project_paths.append(project)
        (project / "answer.txt").write_text(f"in {project}")
        (project / "large.txt").write_bytes(b"x" * (256 * 1024 + 1))
        (project / "boundary.txt").write_bytes(b"y" * (256 * 1024))
        (project / "binary.bin").write_bytes(b"\xff\x00")
        (project / ".claude/private.txt").write_text("not an artifact")
        result = {"type": "result", "result": f"Answer {project}", "subtype": "error_max_turns",
                  "usage": {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 4}}
        init = {"type": "system", "subtype": "init", "tools": ["Read"], "skills": ["money-tests"], "mcp_servers": [], "model": "reported"}
        text = json.dumps([init, {"type": "assistant", "message": "whole transcript"}, result] if verbose else result, indent=2)
        raw_transcripts.append(text.replace(str(project), "<project>"))
        return text
    times = iter([1.0, 2.25, 3.0, 5.5])
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(runner, "fake_session", capture)
    record, count = runner.evaluate_prompt(runner_args, runner.ROOT / "skills/money-tests",
                                          {"id": 1, "prompt": "Capture", "expectations": ["Explains"]}, "with", 1, tmp_path)
    assert count == 2
    subject = record["subject"]
    assert subject["final_answer"] == "Answer <project>"
    assert subject["tokens"] == {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 4}
    assert subject["wall_time"] == 1.25 and record["grader"]["wall_time"] == 2.5
    assert subject["stopped"] == "max_turns"
    assert (tmp_path / subject["raw_paths"]["transcript"]).read_text() == raw_transcripts[0]
    assert subject["reported"] == ({"tools": ["Read"], "skills": ["money-tests"], "mcp_servers": [], "model": "reported"} if verbose else {})
    files = {f["path"]: f for f in record["files"]}
    assert sorted(files) == ["answer.txt", "binary.bin", "boundary.txt", "large.txt"]
    assert files["large.txt"] == {"path": "large.txt", "size": 262145, "sha256": hashlib.sha256(b"x" * 262145).hexdigest()}
    assert (tmp_path / files["answer.txt"]["raw_path"]).read_text() == "in <project>"
    assert (tmp_path / files["boundary.txt"]["raw_path"]).stat().st_size == 262144
    assert (tmp_path / files["binary.bin"]["raw_path"]).read_bytes() == b"\xff\x00"
    payload = json.loads((tmp_path / record["grader"]["invocation"]["stdin_path"]).read_text())
    assert next(f for f in payload["produced_files"] if f["path"] == "binary.bin")["base64"] == "/wA="
    assert "whole transcript" not in json.dumps(record)
    assert "in <project>" not in json.dumps(record)
    assert all(set(f) <= {"path", "size", "sha256", "raw_path"} for f in files.values())
    assert all(not p.exists() for p in project_paths)
    assert all(str(p) not in json.dumps(record) for p in project_paths)


@pytest.mark.parametrize("condition", ["with", "without"])
@pytest.mark.parametrize("skill,source,target", [
    ("money-arithmetic", "evals/files/api_amount.py", "src/api_amount.py"),
    ("fintech-audit", "evals/files/audit-fixture/src/billing.py", "src/billing.py"),
    ("fintech-audit", "evals/files/audit-fixture/README.md", "README.md"),
])
def test_fixture_placement(condition, skill, source, target, runner_args, tmp_path, monkeypatch):
    original = runner.fake_session
    inputs = []
    def inspect(role, project, prompt):
        if role == "subject":
            inputs.append(runner.project_files(project))
        return original(role, project, prompt)
    monkeypatch.setattr(runner, "fake_session", inspect)
    folder = runner.ROOT / "skills" / skill
    record, count = runner.evaluate_prompt(runner_args, folder, {
        "id": 1, "prompt": "Synthetic", "files": [source], "expectations": ["Explains"]}, condition, 1, tmp_path)
    assert inputs == [{target: (folder / source).read_bytes()}]
    assert count == 2
    assert [v["status"] for v in record["verdicts"]] == ["passed"]


@pytest.mark.parametrize("files", [
    ["evals/files/input.py", "evals/files/fixture/src/input.py"],
    ["evals/files/input.py", "evals/files/input.py"],
])
def test_duplicate_input_files(files, runner_args, tmp_path, monkeypatch):
    skill = tmp_path / "synthetic-skill"
    (skill / "evals/files/fixture/src").mkdir(parents=True)
    (skill / "evals/files/input.py").write_text("flat")
    (skill / "evals/files/fixture/src/input.py").write_text("tree")
    calls = []
    monkeypatch.setattr(runner, "fake_session", lambda *a: calls.append(a))
    record, count = runner.evaluate_prompt(runner_args, skill, {
        "id": 1, "prompt": "Synthetic", "files": files, "expectations": ["First", "Second"]}, "with", 1, tmp_path)
    assert count == 0 and calls == []
    assert [v["status"] for v in record["verdicts"]] == ["error", "error"]
    assert [v["evidence"] for v in record["verdicts"]] == ["duplicate eval file target: src/input.py"] * 2


def test_fixture_changes(runner_args, tmp_path, monkeypatch):
    skill = tmp_path / "synthetic-skill"
    (skill / "evals/files/fixture/nested").mkdir(parents=True)
    (skill / "evals/files/fixture/nested/input.txt").write_text("original")
    (skill / "evals/files/unchanged.txt").write_text("unchanged")
    (skill / "SKILL.md").write_text("Synthetic")
    (skill / "evals/vectors/__pycache__").mkdir(parents=True)
    (skill / "evals/vectors/__pycache__/reference.pyc").write_bytes(b"synthetic cache")
    inputs = []
    original = runner.fake_session
    def change(role, project, prompt):
        if role == "subject":
            assert not list(project.rglob("__pycache__"))
            inputs.append(runner.project_files(project))
            (project / "nested/input.txt").write_text("changed")
        return original(role, project, prompt)
    monkeypatch.setattr(runner, "fake_session", change)
    for condition in ("with", "without"):
        record, _ = runner.evaluate_prompt(runner_args, skill, {
            "id": 1, "prompt": "Synthetic", "files": ["evals/files/fixture/nested/input.txt", "evals/files/unchanged.txt"], "expectations": ["Explains"]}, condition, 1, tmp_path)
        assert [f["path"] for f in record["files"]] == ["nested/input.txt", "test_generated.py"]
        assert (tmp_path / record["files"][0]["raw_path"]).read_text() == "changed"
    assert inputs == [{"nested/input.txt": b"original", "src/unchanged.txt": b"unchanged"}] * 2


def test_grader_payload(runner_args, tmp_path, monkeypatch):
    payloads = []
    original = runner.fake_session
    def inspect(role, project, prompt):
        if role == "grader":
            assert list(project.iterdir()) == []
            payloads.append(json.loads(prompt))
        return original(role, project, prompt)
    monkeypatch.setattr(runner, "fake_session", inspect)
    record, _ = runner.evaluate_prompt(runner_args, runner.ROOT / "skills/money-tests", {
        "id": 1, "prompt": "Synthetic prompt", "expectations": ["Tests exist"]}, "without", 1, tmp_path)
    payload = payloads[0]
    assert set(payload) == {"prompt", "expectations", "final_answer", "transcript", "produced_files", "instructions"}
    assert payload["prompt"] == "Synthetic prompt" and payload["expectations"] == ["Tests exist"]
    assert payload["final_answer"] == "Fake answer in <project>"
    assert json.loads(payload["transcript"])[-1]["type"] == "result"
    assert payload["produced_files"][0]["path"] == "test_generated.py"
    assert payload["produced_files"][0]["content"] == "def test_example():\n    assert 1 == 1\n"
    assert "stdin" not in record["grader"]["invocation"]
    assert json.loads((tmp_path / record["grader"]["invocation"]["stdin_path"]).read_text()) == payload
    assert "condition" not in json.dumps(payload) and "without" not in json.dumps(payload)
    assert "raw_path" not in payload["produced_files"][0]
    assert record["subject"]["tokens"]["input_tokens"] == 10
    assert record["grader"]["tokens"] == {"input_tokens": 4, "output_tokens": 3, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}


@pytest.mark.parametrize("answer,statuses", [
    ("not JSON", ["error", "error"]),
    ('{"passed":true,"evidence":"wrong shape"}', ["error", "error"]),
    ('[{"passed":true,"evidence":"first"}]', ["passed", "error"]),
    ('[{"passed":"true","evidence":"bad"},{"passed":false,"evidence":"second"}]', ["error", "failed"]),
    ('[{"passed":true,"evidence":" "},{"passed":true,"evidence":"second"}]', ["error", "passed"]),
    ('[null,{"passed":true,"evidence":"second"}]', ["error", "passed"]),
])
def test_grader_verdicts(answer, statuses, runner_args, tmp_path, monkeypatch):
    original = runner.fake_session
    def malformed(role, project, prompt):
        return json.dumps({"type": "result", "result": answer}) if role == "grader" else original(role, project, prompt)
    monkeypatch.setattr(runner, "fake_session", malformed)
    record, count = runner.evaluate_prompt(runner_args, runner.ROOT / "skills/money-tests", {
        "id": 1, "prompt": "Synthetic", "expectations": ["First", "Second"]}, "without", 1, tmp_path)
    assert count == 2
    assert [v["status"] for v in record["verdicts"]] == statuses
    assert all(v["evidence"].strip() for v in record["verdicts"])


@pytest.mark.parametrize("name", ["test_math.py", "math_test.py", "math_test.go", "math.test.js", "math.test.ts",
                                "math.spec.js", "math.spec.ts", "MoneyTest.java", "money_spec.rb", "tests/anything",
                                "nested/test/anything", "__tests__/anything", "spec/anything"])
def test_static_test_files(name):
    verdicts = runner.combine_verdicts(["Tests cover behavior"], [{"path": name}], {
        "final_answer": '[{"passed":true,"evidence":"checked"}]'})
    assert verdicts == [{"expectation": "Tests cover behavior", "status": "passed",
                         "grader_verdict": {"passed": True, "evidence": "checked"}, "evidence": "checked",
                         "code_checks": [{"kind": "test_file", "passed": True}]}]


def test_static_classification():
    checks = [runner.static_checks(expectation, [])
              for path in (runner.ROOT / "skills").glob("*/evals/evals.json")
              for evaluation in json.loads(path.read_text())["evals"] for expectation in evaluation["expectations"]]
    assert sum(c["kind"] == "test_file" for items in checks for c in items) == 58
    advice = next(e for e in json.loads((runner.ROOT / "skills/money-tests/evals/evals.json").read_text())["evals"] if e["id"] == 2)
    assert [runner.static_checks(e, []) for e in advice["expectations"]] == [[], [], [], []]


@pytest.mark.parametrize("files,passed,status", [
    (["src/amount.py", "tests/amount.py"], True, "passed"),
    (["src/amount.py", "not_a_test.py.txt"], True, "failed"),
    (["test_amount.py"], True, "failed"),
    (["src/amount.py", "test_amount.py"], False, "failed"),
])
def test_named_paths(files, passed, status):
    results = runner.combine_verdicts(["Adds tests for `src/amount.py`"], [{"path": p} for p in files], {
        "final_answer": json.dumps([{"passed": passed, "evidence": "Reviewed files"}])})
    assert results[0]["status"] == status
    assert results[0]["grader_verdict"] == {"passed": passed, "evidence": "Reviewed files"}
    assert results[0]["code_checks"] == [{"kind": "test_file", "passed": any("test" in p and not p.endswith(".txt") for p in files)},
                                           {"kind": "path", "path": "src/amount.py", "passed": "src/amount.py" in files}]


@pytest.mark.parametrize("role", ["subject", "grader"])
@pytest.mark.parametrize("failure", ["timeout", "exit", "oserror", "invalid_json"])
def test_subject_failures(role, failure, runner_args, tmp_path, monkeypatch):
    runner_args.agent = "claude"
    projects, roles = [], []
    def transport(argv, **kwargs):
        actual_role = "subject" if "--verbose" in argv else "grader"
        project = kwargs["cwd"]
        projects.append(project)
        roles.append(actual_role)
        if actual_role == role:
            (project / "partial.txt").write_text("partial output")
            if failure == "timeout":
                raise subprocess.TimeoutExpired(argv, 900, output=b"partial transcript", stderr=b"partial stderr")
            if failure == "oserror":
                raise OSError(f"cannot start in {project}")
            if failure == "exit":
                return SimpleNamespace(returncode=7, stdout="", stderr="x" * 5000 + f" tail {project}")
            return SimpleNamespace(returncode=0, stdout="not json", stderr="")
        return SimpleNamespace(returncode=0, stdout=runner.fake_session(actual_role, project, kwargs["input"]), stderr="")
    monkeypatch.setattr(subprocess, "run", transport)
    record, count = runner.evaluate_prompt(runner_args, runner.ROOT / "skills/money-tests", {
        "id": 1, "prompt": "Synthetic", "expectations": ["First", "Second"]}, "without", 1, tmp_path)
    assert count == (1 if role == "subject" else 2)
    assert roles == (["subject"] if role == "subject" else ["subject", "grader"])
    assert [v["status"] for v in record["verdicts"]] == ["error", "error"]
    reason = record["verdicts"][0]["evidence"]
    assert {"timeout": "timeout", "exit": "exit code 7:", "oserror": "cannot start in <project>", "invalid_json": "invalid session JSON"}[failure] in reason
    if failure == "exit":
        assert "tail <project>" in reason and len(reason) < 4100
    if failure == "timeout":
        assert (tmp_path / record[role]["raw_paths"]["transcript"]).read_text() == "partial transcript"
    if role == "subject":
        assert record["files"][0]["path"] == "partial.txt"
    assert all(not project.exists() for project in projects)
    assert all(str(project) not in json.dumps(record) for project in projects)


def test_full_fake_flow(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Fake sessions must not start a process")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert runner.eval_main(["--skill", "money-arithmetic", "--runs", "2", "--agent", "fake",
                             "--results-dir", str(tmp_path)]) == 0
    run_dir, = tmp_path.iterdir()
    assert run_dir.name.endswith("-abcdef0")
    assert len(run_dir.name) == 24
    skill_json = (run_dir / "money-arithmetic.json").read_text()
    data = json.loads(skill_json)
    assert "def test_example()" not in skill_json
    assert data["run_id"] == run_dir.name and data["date"] == run_dir.name[:16]
    assert data["subject_model"] == data["grader_model"] == "fake"
    assert data["skill"] == "money-arithmetic" and data["git_sha"] == "abcdef0123456789"
    assert data["skills_dirty"] is False
    assert ".claude/skills/money-arithmetic/SKILL.md" in data["installed_paths"]
    assert len(data["records"]) == 28
    assert [(r["eval_id"], r["condition"], r["run"]) for r in data["records"]] == [
        (e, c, n) for e in (1, 2, 3, 4, 5, 6, 7) for c in ("with", "without") for n in (1, 2)]
    for record in data["records"]:
        assert record["subject"]["final_answer"] == "Fake answer in <project>"
        assert all(v["status"] == "passed" and v["evidence"] for v in record["verdicts"])
        prefix = f"raw/money-arithmetic/{record['eval_id']}-{record['condition']}-{record['run']}/"
        for role in ("subject", "grader"):
            for path in record[role]["raw_paths"].values():
                assert path.startswith(prefix) and (run_dir / path).is_file()
        assert record["files_raw_path"].startswith(prefix)
        manifest = json.loads((run_dir / record["files_raw_path"]).read_text())
        assert manifest == record["files"]
        assert all(set(f) == {"path", "size", "sha256", "raw_path"} for f in manifest)
        stdin_path = record["grader"]["invocation"]["stdin_path"]
        assert stdin_path == prefix + "grader-stdin.json"
        payload = json.loads((run_dir / stdin_path).read_text())
        assert json.dumps(payload["transcript"])[1:-1] not in skill_json
    summary = (run_dir / "summary.md").read_text()
    assert summary.startswith("# FAKE evaluation (no model judgments)\n")
    assert "Planned sessions: 56; started sessions: 56" in summary
    raw_size = sum(p.stat().st_size for p in (run_dir / "raw").rglob("*") if p.is_file())
    assert f"Raw size: {raw_size} bytes" in summary
    assert "| money-arithmetic | with | 100.0% | 60 | 0 | 0 | 0 | 252 | 98 |" in summary
    assert "| all-skills | without | 100.0% | 60 | 0 | 0 | 0 | 252 | 98 |" in summary


@pytest.mark.parametrize("statuses,expected", [
    (["passed", "failed", "error"], "50.0% | 1 | 1 | 1"),
    (["error", "error"], "n/a | 0 | 0 | 2"),
])
def test_summary(statuses, expected):
    session = {"tokens": {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 4},
               "wall_time": 1.5, "stopped": "max_turns"}
    records = [{"condition": "with", "verdicts": [{"status": s} for s in statuses], "subject": session, "grader": session}]
    text = runner.summary_text({"run_id": "run", "date": "date", "subject_model": "subject", "grader_model": "grader", "git_sha": "sha"},
                               {"synthetic": {"records": records}}, 2, 2, 123, False)
    assert f"| synthetic | with | {expected} | 1 | 10 | 10 | 3.000 |" in text
    assert "| synthetic | without | n/a | 0 | 0 | 0 | 0 | 0 | 0 | 0.000 |" in text
    assert f"| all-skills | with | {expected} | 1 | 10 | 10 | 3.000 |" in text
    for literal in ("run_id: run", "date: date", "subject_model: subject", "grader_model: grader", "git_sha: sha", "Raw size: 123 bytes"):
        assert literal in text


def test_timeout_kills_process(runner_args, tmp_path, monkeypatch):
    runner_args.agent = "claude"
    runner_args.timeout = 0.2
    command = [sys.executable, "-c", "import os, pathlib, time; pathlib.Path('pid').write_text(str(os.getpid())); time.sleep(30)"]
    monkeypatch.setattr(runner, "session_invocation", lambda *args: command)
    session = runner.call_session(runner_args, "subject", tmp_path, "Synthetic")
    assert session["error"] == "timeout"
    pid = int((tmp_path / "pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.parametrize("flag", ["--runs", "--max-turns", "--timeout", "--budget"])
def test_positive_limits(flag, tmp_path):
    with pytest.raises(SystemExit) as exc:
        runner.eval_main(["--all", flag, "0", "--results-dir", str(tmp_path / "results")])
    assert exc.value.code != 0
    assert list(tmp_path.iterdir()) == []


def test_git_metadata(monkeypatch):
    calls = []
    def read_git(argv, **kwargs):
        calls.append((argv, kwargs))
        return "1234567abcdef\n" if "rev-parse" in argv else " M skills/money-tests/SKILL.md\n"
    monkeypatch.undo()
    # The autouse fixture hides Git in flow tests; this test calls the actual metadata reader.
    monkeypatch.setattr(subprocess, "check_output", read_git)
    assert runner.repository_state() == ("1234567abcdef", True)
    assert calls == [
        (["git", "rev-parse", "HEAD"], {"cwd": runner.ROOT, "text": True}),
        (["git", "status", "--porcelain", "--", "skills/"], {"cwd": runner.ROOT, "text": True})]


def test_nonzero_max_turns(runner_args, tmp_path, monkeypatch):
    runner_args.agent = "claude"
    roles = []
    def transport(argv, **kwargs):
        role = "subject" if "--verbose" in argv else "grader"
        roles.append(role)
        stdout = runner.fake_session(role, kwargs["cwd"], kwargs["input"])
        if role == "subject":
            transcript = json.loads(stdout)
            transcript[-1]["subtype"] = "error_max_turns"
            stdout = json.dumps(transcript)
        return SimpleNamespace(returncode=1 if role == "subject" else 0, stdout=stdout, stderr="")
    monkeypatch.setattr(subprocess, "run", transport)
    record, count = runner.evaluate_prompt(runner_args, runner.ROOT / "skills/money-tests", {
        "id": 1, "prompt": "Synthetic", "expectations": ["Tests exist"]}, "without", 1, tmp_path)
    assert count == 2 and roles == ["subject", "grader"]
    assert record["subject"]["stopped"] == "max_turns"
    assert record["subject"]["exit_code"] == 1
    assert record["subject"]["error"] is None
    assert record["verdicts"][0]["status"] == "passed"


@pytest.mark.parametrize("role", ["subject", "grader"])
@pytest.mark.parametrize("usage", [[1], None, {"input_tokens": "bad"}, {"output_tokens": -1}])
def test_malformed_usage_flow(role, usage, tmp_path, monkeypatch):
    original = runner.fake_session
    def malformed(actual_role, project, prompt):
        stdout = original(actual_role, project, prompt)
        if actual_role == role:
            transcript = json.loads(stdout)
            result = transcript[-1] if isinstance(transcript, list) else transcript
            result["usage"] = usage
            stdout = json.dumps(transcript)
        return stdout
    monkeypatch.setattr(runner, "fake_session", malformed)
    assert runner.eval_main(["--skill", "money-tests", "--agent", "fake", "--results-dir", str(tmp_path)]) == 0
    run_dir, = tmp_path.iterdir()
    data = json.loads((run_dir / "money-tests.json").read_text())
    assert len(data["records"]) == 14
    for record in data["records"]:
        assert record[role]["error"] == "invalid session usage"
        assert all(v["status"] == "error" and v["evidence"] == "invalid session usage" for v in record["verdicts"])
    summary = (run_dir / "summary.md").read_text()
    assert "| money-tests | with | n/a | 0 | 0 | 30 |" in summary
    assert f"Planned sessions: 28; started sessions: {14 if role == 'subject' else 28}" in summary


def test_parse_verdicts_accepts_fenced_json_and_prose():
    from scripts.run_evals import parse_verdicts
    fenced = "```json\n[{\"passed\": true, \"evidence\": \"ok\"}]\n```"
    assert parse_verdicts(fenced) == [{"passed": True, "evidence": "ok"}]
    prose = "Here are the verdicts:\n[{\"passed\": false, \"evidence\": \"no\"}]\nDone."
    assert parse_verdicts(prose) == [{"passed": False, "evidence": "no"}]
    assert parse_verdicts("[]") == []


def test_blind_transcript_hides_the_condition():
    from scripts.run_evals import blind_transcript
    transcript = json.dumps([
        {"type": "system", "subtype": "init", "skills": ["money-arithmetic", "doctor"], "tools": ["Read", "Skill"], "model": "m"},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "money-arithmetic"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "Launching skill: money-arithmetic"}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "<project>/.claude/skills/money-arithmetic/SKILL.md"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": "# Money arithmetic rules"}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t3", "name": "Read", "input": {"file_path": "<project>/src/money.py"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t3", "content": "amount = 1.1"}]}},
        {"type": "result", "result": "done"},
    ])
    blinded = blind_transcript(transcript)
    assert "money-arithmetic" not in blinded and "Money arithmetic rules" not in blinded and "Launching skill" not in blinded
    assert "amount = 1.1" in blinded and '"tools"' in blinded and '"result": "done"' in blinded
    assert blind_transcript("not json") == "not json"


def test_heldout_mode_reads_the_separate_set_and_names_the_folder(runner_args, tmp_path, monkeypatch):
    heldout = runner.ROOT / "evals/heldout"
    assert (heldout / "money-arithmetic.json").is_file(), "held-out set missing"
    items = json.loads((heldout / "money-arithmetic.json").read_text())["evals"]
    for item in items:
        for name in item.get("files", []):
            assert (heldout / "files/money-arithmetic" / name).is_file()
    code = runner.eval_main(["--skill", "money-arithmetic", "--agent", "fake", "--evals", "heldout",
                             "--results-dir", str(tmp_path), "--budget", "40"])
    assert code == 0
    run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
    assert run_dir.name.endswith("-heldout")
    data = json.loads((run_dir / "money-arithmetic.json").read_text())
    assert data["prompt_set"] == "heldout" and len(data["records"]) == len(items) * 2
    assert all(r["eval_id"] in {i["id"] for i in items} for r in data["records"])
