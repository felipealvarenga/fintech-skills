#!/usr/bin/env python3
"""Run paired skill evaluations and retain the evidence and grades."""

import argparse
import base64
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
TEST_PATTERNS = ("test_*.py", "*_test.py", "*_test.go", "*.test.js", "*.test.ts",
                 "*.spec.js", "*.spec.ts", "*Test.java", "*_spec.rb")


def cli_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--skill", action="append")
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--subject-model", default="claude-sonnet-5-5")
    parser.add_argument("--grader-model", default="claude-sonnet-5-5")
    parser.add_argument("--effort", default="xhigh", choices=["low", "medium", "high", "xhigh", "max"],
                        help="effort level for both roles; the published runs used xhigh, Claude Code's default")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--budget", type=int, default=80)
    parser.add_argument("--results-dir", type=Path, default=ROOT / "evals" / "results")
    parser.add_argument("--agent", choices=("claude", "agy", "fake"), default="claude")
    parser.add_argument("--evals", choices=("dev", "heldout"), default="dev",
                        help="dev: skills/<skill>/evals/evals.json; heldout: evals/heldout/<skill>.json, never read when editing skills")
    return parser


def role_agent(args, role):
    if args.agent == "agy" and role == "grader" and args.grader_model.startswith("claude"):
        return "claude"
    return args.agent


def session_invocation(args, role, settings_path=None, prompt=None):
    agent = role_agent(args, role)
    if agent == "agy":
        model = args.subject_model if role == "subject" else args.grader_model
        command = ["agy", "--model", model, "--output-format", "stream-json", "--mode", "accept-edits",
                   "--print-timeout", f"{max(1, int(args.timeout))}s"]
        if settings_path is not None:
            command += ["--settings", str(settings_path)]
        command += ["-p", prompt or ""]
        return command
    command = ["claude", "-p", "--output-format", "json"]
    if role == "subject":
        command += ["--verbose", "--model", args.subject_model, "--effort", args.effort, "--max-turns", str(args.max_turns),
                    "--tools", "Read,Write,Edit,Glob,Grep,Skill", "--setting-sources", "project",
                    "--strict-mcp-config", "--permission-mode", "acceptEdits",
                    "--permission-prompts", "none", "--no-session-persistence"]
    else:
        command += ["--model", args.grader_model, "--effort", args.effort, "--tools", "", "--setting-sources", "project",
                    "--strict-mcp-config", "--no-session-persistence"]
    return command


def fake_session(role, project, prompt):
    if role == "subject":
        (project / "test_generated.py").write_text("def test_example():\n    assert 1 == 1\n")
        return json.dumps([
            {"type": "system", "subtype": "init", "tools": ["Read", "Write", "Edit", "Glob", "Grep", "Skill"],
             "skills": sorted(p.name for p in (project / ".claude/skills").glob("*")),
             "mcp_servers": [], "model": "fake"},
            {"type": "result", "result": f"Fake answer in {project}", "stop_reason": "end_turn",
             "usage": {"input_tokens": 10, "output_tokens": 5,
                       "cache_read_input_tokens": 2, "cache_creation_input_tokens": 1}}])
    expectations = json.loads(prompt)["expectations"]
    verdicts = [{"passed": True, "evidence": "Fake deterministic verdict; not a model judgment."}
                for _ in expectations]
    return json.dumps({"type": "result", "result": json.dumps(verdicts),
                       "usage": {"input_tokens": 4, "output_tokens": 3}})


# A session gets a small environment: what `claude` needs to find its config and credentials, plus the
# flags the method sets. Nothing else from the operator's shell reaches the subject or the grader.
ENV_PASSTHROUGH = ("HOME", "PATH", "USER", "LOGNAME", "SHELL", "TERM", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR",
                   "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR",
                   "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN")
ENV_PREFIXES = ("ANTHROPIC_",)
SESSION_ENV = {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_BUNDLED_SKILLS": "1"}


def session_env(extra, environ=None):
    environ = os.environ if environ is None else environ
    env = {k: v for k, v in environ.items() if k in ENV_PASSTHROUGH or k.startswith(ENV_PREFIXES)}
    env.update(extra)
    return env


AGY_SETTINGS = {
    "allowNonWorkspaceAccess": False,
    "permissions": {
        "allow": [
            "command(ls)", "command(find)", "command(rg)", "command(grep)",
            "command(tree)", "command(wc)", "command(head)", "command(tail)", "command(cat)",
            "command(sort)", "command(uniq)", "command(cut)", "command(tr)", "command(diff)",
            "command(pwd)", "command(echo)", "command(true)", "command(false)", "command(stat)",
            "command(file)", "command(basename)", "command(dirname)", "command(realpath)",
            "command(readlink)", "command(nl)", "command(printf)", "command(test)", "command([)",
            "command(sed)", "command(awk)", "command(xargs)",
        ],
        "deny": [
            "mcp(*)",
            "command(which)", "command(type)", "command(whereis)", "command(command)",
            "command(python)", "command(python3)", "command(pytest)", "command(pip)", "command(pip3)", "command(uv)",
            "command(mutmut)", "command(cosmic-ray)",
            "command(node)", "command(npm)", "command(npx)", "command(vitest)",
            "command(go)", "command(cargo)", "command(ruby)", "command(java)", "command(php)", "command(perl)",
            "command(psql)", "command(postgres)", "command(initdb)", "command(pg_dump)", "command(sqlite3)",
            "command(bash)", "command(sh)", "command(zsh)", "command(fish)", "command(env)", "command(printenv)",
            "command(curl)", "command(wget)", "command(gh)", "command(git)", "command(bwrap)", "command(make)",
            "command(rm)", "command(mv)", "command(cp)", "command(chmod)", "command(chown)",
            "command(mkdir)", "command(touch)", "command(tee)",
        ],
    },
}


def prepare_agy_home(base):
    """Build an isolated HOME for agy with auth/config symlinked and no global ~/.agents or ~/.gemini/config skills."""
    real_home = Path.home()
    fake_home = base / "home"
    (fake_home / ".gemini").mkdir(parents=True)
    (fake_home / ".config").mkdir(parents=True)
    for rel in (".gemini/antigravity-cli", ".config/antigravity"):
        src = real_home / rel
        if src.exists():
            (fake_home / rel).symlink_to(src)
    settings_path = base / "agy-settings.json"
    settings_path.write_text(json.dumps(AGY_SETTINGS), encoding="utf-8")
    return fake_home, settings_path


def parse_agy_transcript(stdout):
    """Parse `agy --output-format stream-json` NDJSON into (result, reported, usage, thinking, error)."""
    init_ev, result_ev = {}, {}
    parsed_any = False
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        parsed_any = True
        if ev.get("event") == "init" and isinstance(ev.get("init"), dict):
            init_ev = ev
        elif ev.get("event") == "result" and isinstance(ev.get("result"), dict):
            result_ev = ev["result"]
    if not parsed_any or not result_ev:
        return {}, {}, {}, None, "invalid session JSON"
    init_info = init_ev.get("init", {})
    reported = {k: init_info[k] for k in ("model", "tools") if k in init_info}
    if "conversation_id" in init_ev:
        reported["conversation_id"] = init_ev["conversation_id"]
    raw_usage = result_ev.get("usage")
    if not isinstance(raw_usage, dict):
        return result_ev, reported, {}, None, "invalid session usage"
    usage = {
        "input_tokens": raw_usage.get("input_tokens", 0),
        "output_tokens": raw_usage.get("output_tokens", 0),
        "cache_read_input_tokens": raw_usage.get("cache_read_tokens", 0),
        "cache_creation_input_tokens": raw_usage.get("cache_creation_tokens", 0),
    }
    if any(type(usage[k]) is not int or usage[k] < 0 for k in TOKEN_KEYS):
        return result_ev, reported, {}, None, "invalid session usage"
    tk = raw_usage.get("thinking_tokens")
    thinking = tk if type(tk) is int and tk >= 0 else None
    err = None if result_ev.get("status") == "SUCCESS" else f"agy status: {result_ev.get('status')}"
    return result_ev, reported, usage, thinking, err


def call_session(args, role, project, prompt):
    agent = role_agent(args, role)
    start = time.monotonic()
    stdout, stderr, error = "", "", None
    exit_code = 0
    scrub_paths = [(str(project), "<project>")]
    if agent == "agy":
        with tempfile.TemporaryDirectory(prefix="fintech-agy-home-") as home_dir:
            fake_home, settings_path = prepare_agy_home(Path(home_dir))
            scrub_paths.append((str(fake_home), "<home>"))
            scrub_paths.append((str(home_dir), "<tmp>"))
            argv = session_invocation(args, role, settings_path=settings_path, prompt=prompt)
            invocation = {"argv": [a.replace(str(home_dir), "<tmp>") for a in argv[:-1]] + ["<prompt>"],
                          "cwd": "<project>", "stdin": prompt, "env": {"HOME": "<isolated-home>"}}
            env = session_env({"HOME": str(fake_home)})
            try:
                process = subprocess.run(argv, stdin=subprocess.DEVNULL, text=True,
                                         capture_output=True, cwd=project, timeout=args.timeout, env=env)
                stdout, stderr = process.stdout, process.stderr
                exit_code = process.returncode
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or b""
                stderr = exc.stderr or b""
                stdout = stdout.decode(errors="replace") if isinstance(stdout, bytes) else stdout
                stderr = stderr.decode(errors="replace") if isinstance(stderr, bytes) else stderr
                error = "timeout"
            except OSError as exc:
                error = str(exc)
    else:
        invocation = {"argv": session_invocation(args, role), "cwd": "<project>", "stdin": prompt,
                      "env": dict(SESSION_ENV)}
        try:
            if agent == "fake":
                stdout = fake_session(role, project, prompt)
            else:
                process = subprocess.run(invocation["argv"], input=prompt, text=True,
                                         capture_output=True, cwd=project, timeout=args.timeout,
                                         env=session_env(invocation["env"]))
                stdout, stderr = process.stdout, process.stderr
                exit_code = process.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            stdout = stdout.decode(errors="replace") if isinstance(stdout, bytes) else stdout
            stderr = stderr.decode(errors="replace") if isinstance(stderr, bytes) else stderr
            error = "timeout"
        except OSError as exc:
            error = str(exc)
    elapsed = time.monotonic() - start
    for old, new in scrub_paths:
        stdout, stderr = stdout.replace(old, new), stderr.replace(old, new)
        if error:
            error = error.replace(old, new)
    if agent == "agy":
        result_ev, reported, usage, thinking, parse_err = parse_agy_transcript(stdout)
        error = error or parse_err
        stopped = "end_turn" if result_ev.get("status") == "SUCCESS" else result_ev.get("status")
        if exit_code:
            error = f"exit code {exit_code}: {stderr[-4000:]}"
        final_answer = result_ev.get("response", "")
        for old, new in scrub_paths:
            final_answer = final_answer.replace(old, new)
        if not error and not final_answer.strip() and "no output produced" in stderr:
            error = f"headless permission abort: {stderr.strip()[:300]}"
        return {"invocation": invocation, "transcript": stdout, "stderr": stderr,
                "error": error, "final_answer": final_answer, "reported": reported,
                "exit_code": exit_code,
                "tokens": {key: usage.get(key, 0) for key in TOKEN_KEYS},
                "thinking_tokens": thinking,
                "stop_reason": stopped, "stopped": stopped, "wall_time": elapsed}
    result, reported = {}, {}
    try:
        transcript = json.loads(stdout)
        messages = transcript if isinstance(transcript, list) else [transcript]
        for message in messages:
            if message.get("type") == "system" and message.get("subtype") == "init":
                reported = {key: message[key] for key in ("tools", "skills", "mcp_servers", "model") if key in message}
            if message.get("type") == "result":
                result = message
    except (ValueError, AttributeError, TypeError):
        error = error or "invalid session JSON"
    usage = result.get("usage", {})
    if not isinstance(usage, dict) or any(type(usage.get(key, 0)) is not int or usage.get(key, 0) < 0 for key in TOKEN_KEYS):
        usage, error = {}, error or "invalid session usage"
    stopped = result.get("stop_reason")
    if result.get("subtype") in ("error_max_turns", "error_max_turns_reached") or stopped == "max_turns":
        stopped = "max_turns"
    if exit_code and stopped != "max_turns":
        error = f"exit code {exit_code}: {stderr[-4000:]}"
    return {"invocation": invocation, "transcript": stdout, "stderr": stderr,
            "error": error.replace(str(project), "<project>") if error else None,
            "final_answer": result.get("result", ""), "reported": reported,
            "exit_code": exit_code,
            "tokens": {key: usage.get(key, 0) for key in TOKEN_KEYS},
            "thinking_tokens": thinking_tokens(usage),  # part of output_tokens, reported when the CLI breaks it out
            "stop_reason": result.get("stop_reason"), "stopped": stopped, "wall_time": elapsed}


def thinking_tokens(usage):
    """Thinking tokens when the CLI reports them (`usage.output_tokens_details.thinking_tokens`), else None."""
    details = usage.get("output_tokens_details") if isinstance(usage, dict) else None
    value = details.get("thinking_tokens") if isinstance(details, dict) else None
    return value if type(value) is int and value >= 0 else None


def project_files(project):
    return {p.relative_to(project).as_posix(): p.read_bytes()
            for p in sorted(project.rglob("*"))
            if p.relative_to(project).parts[0] not in (".claude", ".agents", ".git") and p.is_file() and not p.is_symlink()}


def skill_folders():
    return {p.name: p for p in sorted((ROOT / "skills").iterdir()) if p.is_dir()}


def fixture_target(skill, name, files_root=None):
    """Development evals list files under the skill's evals/files/; held-out evals list files under
    evals/heldout/files/<skill>/ (files_root). A flat name goes to src/<name>; a nested one keeps its path
    below the first folder."""
    path = Path(name)
    if files_root is not None:
        source = files_root / path
        if (path.is_absolute() or ".." in path.parts or not source.is_file()
                or not source.resolve().is_relative_to(files_root.resolve())):
            raise ValueError(f"invalid or missing eval file: {name}")
        return Path("src") / path if len(path.parts) == 1 else Path(*path.parts[1:])
    source = skill / path
    if (path.is_absolute() or ".." in path.parts or path.parts[:2] != ("evals", "files")
            or len(path.parts) < 3 or not source.is_file()
            or not source.resolve().is_relative_to(skill.resolve())):
        raise ValueError(f"invalid or missing eval file: {name}")
    relative = path.relative_to("evals/files")
    return Path("src") / relative if len(relative.parts) == 1 else Path(*relative.parts[1:])


def install_skill(skill, project, skill_root=".claude/skills"):
    installed = []
    root = skill.resolve()
    for source in sorted(skill.rglob("*")):
        relative = source.relative_to(skill)
        if "__pycache__" in relative.parts or relative.parts[0] == "evals":
            continue  # nothing under evals/: the vectors carry reference implementations
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError(f"{source} is a symlink or resolves outside {skill}: a skill installs plain files only")
        if not source.is_file():
            continue
        target = project / skill_root / skill.name / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        installed.append(target.relative_to(project).as_posix())
    return installed


def install_project(skill, evaluation, project, condition, agent="claude"):
    sources = {}
    files_root = Path(evaluation["files_root"]) if evaluation.get("files_root") else None
    for name in evaluation.get("files", []):
        target = fixture_target(skill, name, files_root)
        if target in sources:
            raise ValueError(f"duplicate eval file target: {target}")
        sources[target] = (files_root / name) if files_root is not None else (skill / name)
    for path, source in sources.items():
        target = project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if agent == "agy":
        subprocess.run(["git", "init", "-q"], cwd=project, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    installed = []
    if condition == "with":
        skill_root = ".agents/skills" if agent == "agy" else ".claude/skills"
        pack = skill_folders().values() if skill.name == "fintech-audit" else [skill]
        for folder in pack:
            installed.extend(install_skill(folder, project, skill_root=skill_root))
    return installed


def produced_files(project, before, raw, run_dir):
    files = []
    for name, content in project_files(project).items():
        if before.get(name) == content:
            continue
        item = {"path": name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        if len(content) <= 256 * 1024:
            try:
                item["content"] = content.decode("utf-8").replace(str(project), "<project>")
                content = item["content"].encode()
            except UnicodeDecodeError:
                item["base64"] = base64.b64encode(content).decode()
            destination = raw / "files" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            item["raw_path"] = destination.relative_to(run_dir).as_posix()
        files.append(item)
    return files


def static_checks(expectation, files):
    names = [item["path"] for item in files]
    checks = []
    if re.match(r"^(?:Tests\b|A test\b|(?:Adds|Includes)\b.*\btests?\b)", expectation):
        found = any(any(fnmatch.fnmatchcase(Path(name).name, pattern) for pattern in TEST_PATTERNS)
                    or bool(set(Path(name).parts[:-1]) & {"tests", "test", "__tests__", "spec"})
                    for name in names)
        checks.append({"kind": "test_file", "passed": found})
    for path in re.findall(r"`([^`]+)`", expectation):
        if "/" in path or re.search(r"\.[A-Za-z0-9]+$", path):
            checks.append({"kind": "path", "path": path, "passed": path in names})
    return checks


def parse_verdicts(text):
    """The grader's answer is a JSON array, sometimes wrapped in a ```json fence or prose."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    elif not text.startswith("["):
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            text = text[start:end + 1]
    return json.loads(text)


SKILL_DIRS = (".claude/skills", ".agents/skills")


def blind_agy_transcript(stdout):
    """Blinded view of an agy stream-json transcript: strips reads/listings of .agents/skills/ and
    coalesces streaming text_delta events so the grader gets compact, condition-blind evidence."""
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            return None
        if not isinstance(ev, dict) or "event" not in ev:
            return None
        events.append(ev)
    if not events:
        return None
    out = []
    text_by_step = {}
    order = []
    for ev in events:
        kind = ev.get("event")
        if kind == "init":
            init_info = ev.get("init") if isinstance(ev.get("init"), dict) else {}
            out.append({"event": "init", "model": init_info.get("model")})
        elif kind == "step_update":
            su = ev.get("step_update") if isinstance(ev.get("step_update"), dict) else {}
            st = su.get("step_type")
            idx = su.get("step_index")
            if st == "tool":
                blob = json.dumps(su.get("tool_info", {}))
                if any(d in blob for d in SKILL_DIRS):
                    # If a read/list targeted .agents/skills directly, drop it; if find/ls listed workspace
                    # files including .agents, scrub .agents lines from its output so condition stays hidden.
                    params_blob = json.dumps((su.get("tool_info") or {}).get("parameters", {}))
                    if any(d in params_blob for d in SKILL_DIRS):
                        continue
                    info = dict(su.get("tool_info") or {})
                    if isinstance(info.get("output"), str):
                        info["output"] = "\n".join(
                            ln for ln in info["output"].splitlines()
                            if ".agents" not in ln and ".claude" not in ln
                        )
                    if su.get("state") in ("DONE", "ERROR"):
                        out.append({"event": "tool", "step_index": idx, "state": su.get("state"),
                                    "tool_name": su.get("tool_name"), "tool_info": info})
                    continue
                if su.get("state") in ("DONE", "ERROR"):
                    out.append({"event": "tool", "step_index": idx, "state": su.get("state"),
                                "tool_name": su.get("tool_name"), "tool_info": su.get("tool_info")})
            elif st == "agent_response":
                delta = su.get("text_delta", "")
                if delta:
                    if idx not in text_by_step:
                        text_by_step[idx] = []
                        order.append(idx)
                    text_by_step[idx].append(delta)
                if su.get("state") == "DONE" and idx in text_by_step:
                    out.append({"event": "agent_response", "step_index": idx, "text": "".join(text_by_step.pop(idx))})
        elif kind == "result":
            res = ev.get("result") if isinstance(ev.get("result"), dict) else {}
            out.append({"event": "result", "status": res.get("status"), "response": res.get("response", "")})
    for idx in order:
        if idx in text_by_step:
            out.append({"event": "agent_response", "step_index": idx, "text": "".join(text_by_step[idx])})
    return json.dumps(out)


def blind_transcript(stdout):
    """What the grader reads: the subject transcript without the installed-skill list in the session
    header, without the Skill tool calls and without the reads of files under .claude/skills/ or
    .agents/skills/ (and their results), so the condition is not shown to it. The subject's own prose
    can still name the skill. The stored raw transcript is untouched."""
    try:
        messages = json.loads(stdout)
    except (ValueError, TypeError):
        agy_blinded = blind_agy_transcript(stdout)
        return agy_blinded if agy_blinded is not None else stdout
    if not isinstance(messages, list):
        return stdout
    hidden, out = set(), []
    for message in messages:
        if not isinstance(message, dict):
            out.append(message)
            continue
        if message.get("type") == "system" and message.get("subtype") == "init":
            message = {k: v for k, v in message.items() if k not in ("skills", "slash_commands", "plugins")}
        inner = message.get("message") if isinstance(message.get("message"), dict) else None
        content = (inner if inner is not None else message).get("content")
        if isinstance(content, list):
            kept = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    serialized = json.dumps(block.get("input", {}))
                    if block.get("name") == "Skill" or any(d in serialized for d in SKILL_DIRS):
                        hidden.add(block.get("id"))
                        continue
                if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("tool_use_id") in hidden:
                    continue
                kept.append(block)
            message = {**message, "message": {**inner, "content": kept}} if inner is not None else {**message, "content": kept}
        out.append(message)
    return json.dumps(out)


def combine_verdicts(expectations, files, grader, error=None):
    try:
        verdicts = parse_verdicts(grader["final_answer"]) if not error else []
        if not isinstance(verdicts, list):
            raise ValueError()
    except (ValueError, TypeError):
        verdicts, error = [], "invalid grader JSON"
    results = []
    for index, expectation in enumerate(expectations):
        verdict = verdicts[index] if index < len(verdicts) else None
        checks = static_checks(expectation, files)
        valid = (isinstance(verdict, dict) and type(verdict.get("passed")) is bool
                 and isinstance(verdict.get("evidence"), str) and bool(verdict["evidence"].strip()))
        reason = error or (None if valid else "missing or malformed grader verdict")
        status = "error" if reason else "passed" if verdict["passed"] and all(c["passed"] for c in checks) else "failed"
        results.append({"expectation": expectation, "status": status, "grader_verdict": verdict,
                        "evidence": reason or verdict["evidence"], "code_checks": checks})
    return results


def save_text(raw, name, text, run_dir):
    path = raw / name
    path.write_text(text, encoding="utf-8")
    return path.relative_to(run_dir).as_posix()


def evaluate_prompt(args, skill, evaluation, condition, run, run_dir):
    raw = run_dir / "raw" / skill.name / f"{evaluation['id']}-{condition}-{run}"
    raw.mkdir(parents=True)
    record = {"eval_id": evaluation["id"], "condition": condition, "run": run,
              "installed_paths": [], "files": [], "subject": None, "grader": None}
    started = 0
    error = None
    with tempfile.TemporaryDirectory(prefix="fintech-eval-") as directory:
        project = Path(directory)
        try:
            record["installed_paths"] = (
                install_project(skill, evaluation, project, condition, agent=args.agent)
                if args.agent == "agy" else install_project(skill, evaluation, project, condition)
            )
        except (ValueError, OSError) as exc:
            error = str(exc).replace(directory, "<project>")
        if not error:
            before = project_files(project)
            record["subject"] = call_session(args, "subject", project, evaluation["prompt"])
            started += 1
            record["files"] = produced_files(project, before, raw, run_dir)
            error = record["subject"]["error"]
    if not error:
        payload = {"prompt": evaluation["prompt"], "expectations": evaluation["expectations"],
                   "final_answer": record["subject"]["final_answer"],
                   "transcript": blind_transcript(record["subject"]["transcript"]), "produced_files": record["files"],
                   "instructions": "Judge each expectation from the evidence. Return only a JSON array, in expectation order, with boolean passed and non-empty evidence for each verdict."}
        # Raw storage paths reveal the condition; the grader receives only the captured files.
        payload["produced_files"] = [{k: v for k, v in item.items() if k != "raw_path"} for item in record["files"]]
        with tempfile.TemporaryDirectory(prefix="fintech-grader-") as directory:
            record["grader"] = call_session(args, "grader", Path(directory), json.dumps(payload))
            started += 1
        error = record["grader"]["error"]
    record["verdicts"] = combine_verdicts(evaluation["expectations"], record["files"], record["grader"], error)
    for role in ("subject", "grader"):
        session = record[role]
        if session is not None:
            session["raw_paths"] = {
                key: save_text(raw, f"{role}-{key}.txt", session.pop(key), run_dir)
                for key in ("transcript", "stderr")}
            if role == "grader":
                session["invocation"]["stdin_path"] = save_text(
                    raw, "grader-stdin.json", session["invocation"].pop("stdin"), run_dir)
    record["files"] = [{k: v for k, v in item.items() if k not in ("content", "base64")}
                       for item in record["files"]]
    record["files_raw_path"] = save_text(raw, "files.json", json.dumps(record["files"], indent=2), run_dir)
    return record, started


def repository_state():
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--", "skills/"], cwd=ROOT, text=True).strip())
    return sha, dirty


def summary_text(metadata, skills, planned, started, raw_size, fake):
    lines = ["# FAKE evaluation (no model judgments)" if fake else "# Evaluation results", "",
             *[f"{key}: {value}" for key, value in metadata.items()],
             f"Planned sessions: {planned}; started sessions: {started}", f"Raw size: {raw_size} bytes", "",
             "Tokens include input, output, cache read and cache creation. Wall time includes both roles.", "",
             "| Skill | Condition | Pass rate | Passed | Failed | Errors | Max-turns stops | Subject tokens | Grader tokens | Wall seconds |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    groups = [(name, data["records"]) for name, data in skills.items()]
    groups.append(("all-skills", [r for data in skills.values() for r in data["records"]]))
    for name, records in groups:
        for condition in ("with", "without"):
            selected = [r for r in records if r["condition"] == condition]
            counts = {status: sum(v["status"] == status for r in selected for v in r["verdicts"])
                      for status in ("passed", "failed", "error")}
            denominator = counts["passed"] + counts["failed"]
            rate = f"{counts['passed'] / denominator:.1%}" if denominator else "n/a"
            stops = sum(bool(r["subject"] and r["subject"]["stopped"] == "max_turns") for r in selected)
            tokens = [sum(sum(r[role]["tokens"].values()) for r in selected if r[role]) for role in ("subject", "grader")]
            wall = sum(r[role]["wall_time"] for r in selected for role in ("subject", "grader") if r[role])
            lines.append(f"| {name} | {condition} | {rate} | {counts['passed']} | {counts['failed']} | {counts['error']} | {stops} | {tokens[0]} | {tokens[1]} | {wall:.3f} |")
    return "\n".join(lines) + "\n"


def eval_main(argv=None):
    parser = cli_parser()
    args = parser.parse_args(argv)
    if min(args.runs, args.max_turns, args.timeout, args.budget) <= 0:
        parser.error("runs, max-turns, timeout and budget must be positive")
    available = skill_folders()
    names = list(available) if args.all else list(dict.fromkeys(args.skill))
    if any(name not in available for name in names):
        parser.error("unknown skill: " + ", ".join(name for name in names if name not in available))
    if args.evals == "heldout":
        evaluations = {}
        for name in names:
            source = ROOT / "evals/heldout" / f"{name}.json"
            if not source.is_file():
                parser.error(f"no held-out evals for {name}: {source}")
            items = json.loads(source.read_text())["evals"]
            for item in items:
                item["files_root"] = str(ROOT / "evals/heldout/files" / name)
            evaluations[name] = items
    else:
        evaluations = {name: json.loads((available[name] / "evals/evals.json").read_text())["evals"] for name in names}
    prompts = sum(len(items) for items in evaluations.values())
    subjects = prompts * 2 * args.runs
    total = subjects * 2
    print(f"Plan: prompts={prompts}, conditions=2, runs={args.runs}, subject sessions={subjects}, grader sessions={subjects}, total={total}, budget={args.budget}")
    if total > args.budget:
        print(f"Refused: {total} sessions exceed --budget {args.budget}; use --budget {total}.", file=sys.stderr)
        return 1
    sha, dirty = repository_state()
    date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{date}-{sha[:7]}" + ("-heldout" if args.evals == "heldout" else "")
    run_dir = args.results_dir / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"Refused: results already exist: {run_dir}", file=sys.stderr)
        return 1
    if args.agent == "fake":
        args.subject_model = args.grader_model = "fake"
    metadata = {"run_id": run_id, "date": date, "subject_model": args.subject_model,
                "grader_model": args.grader_model, "effort": args.effort, "git_sha": sha, "skills_dirty": dirty, "prompt_set": args.evals}
    skills, started = {}, 0
    for name, items in evaluations.items():
        data = {**metadata, "skill": name, "installed_paths": [], "records": []}
        for evaluation in items:
            for condition in ("with", "without"):
                for run in range(1, args.runs + 1):
                    record, count = evaluate_prompt(args, available[name], evaluation, condition, run, run_dir)
                    started += count
                    data["records"].append(record)
                    data["installed_paths"] = sorted(set(data["installed_paths"]) | set(record["installed_paths"]))
        skills[name] = data
        (run_dir / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
    raw_size = sum(p.stat().st_size for p in (run_dir / "raw").rglob("*") if p.is_file())
    (run_dir / "summary.md").write_text(summary_text(metadata, skills, total, started, raw_size, args.agent == "fake"))
    print(f"Results: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(eval_main())
