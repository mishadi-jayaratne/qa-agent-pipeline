#!/usr/bin/env python3
"""
QA Agent Pipeline Dashboard — a thin local web wrapper around the `claude` CLI.

Agent identities are built on the fly from this repo's own prompts/<id>.md +
config/agents.yaml (via `claude`'s --agents inline JSON flag), so the target project
you point --project-dir at does NOT need .claude/agents/ installed in it — that
requirement (and the copy step) is gone. The target project only needs to exist;
if it has its own templates/ and config/pipeline.config.yaml those are honored
(e.g. a team's real bug-report template), otherwise this repo's defaults are used.

Run from anywhere, pointing at whatever you want to test:
    python3 dashboard/server.py --project-dir /path/to/some/project [--port 8765]

Binds to 127.0.0.1 only. Runs one `claude` job at a time.
"""
import argparse
import asyncio
import csv
import io
import json
import os
import shutil
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import markdown as md
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

DASHBOARD_DIR = Path(__file__).resolve().parent
PIPELINE_ROOT = DASHBOARD_DIR.parent  # where prompts/, config/, templates/ live — source of truth
STATIC_DIR = DASHBOARD_DIR / "static"
LOGS_DIR = DASHBOARD_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# short tool name (config/agents.yaml) -> Claude tool name, same mapping as
# scripts/generate_agents.py's CLAUDE_TOOL_NAMES.
CLAUDE_TOOL_NAMES = {
    "read": "Read",
    "grep": "Grep",
    "glob": "Glob",
    "bash": "Bash",
    "write": "Write",
    "edit": "Edit",
}


# MCP server tools are passed through as-is (e.g. "mcp__gitlab" grants every tool the
# "gitlab" server in .mcp.json exposes), same as scripts/generate_agents.py's
# resolve_tool_name — needed for gitlab-publisher, the only agent with an mcp__ tool.
def resolve_tool_name(tool: str) -> str:
    if tool in CLAUDE_TOOL_NAMES:
        return CLAUDE_TOOL_NAMES[tool]
    if tool.startswith("mcp__"):
        return tool
    raise KeyError(tool)

# Default one-line action per agent, appended with any user-supplied extra context.
# These mirror the "Typical workflow" examples in the root README.
AGENT_DEFAULT_PROMPTS = {
    "context-analyzer": "Analyze this codebase and update context.md.",
    "changelog-analyzer": "Analyze the changelog/commits/diff for this release and produce changes.md.",
    "requirements-analyzer": "Extract requirements and cross-reference them against changes.md and code-scan.md for this run.",
    "code-scanner": "Review the changed code for this run and produce code-scan.md.",
    "test-planner": "Produce a test plan for this run.",
    "test-case-writer": "Write test cases from the approved test plan for this run.",
    "log-analyzer": "Analyze the logs for this run.",
    "rca-analyst": "Perform root cause analysis for the reported issue below.",
    "bug-reporter": "File a bug report using the RCA report and test case for this run.",
    "release-notes-writer": "Prepare the test closure report and release notes for this run.",
}

# ---------------------------------------------------------------------------
# CLI args / project context
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="QA Agent Pipeline Dashboard")
parser.add_argument("--project-dir", default=".", help="Project directory to invoke agents against")
parser.add_argument("--port", type=int, default=8765)
ARGS = parser.parse_args()
PROJECT_DIR = Path(ARGS.project_dir).resolve()

if not PROJECT_DIR.is_dir():
    sys.exit(f"--project-dir {PROJECT_DIR} does not exist or is not a directory.")

if not (PIPELINE_ROOT / "config" / "agents.yaml").exists() or not (PIPELINE_ROOT / "prompts").exists():
    sys.exit(
        f"config/agents.yaml or prompts/ not found under {PIPELINE_ROOT} — dashboard/server.py "
        "must live inside the qa-agent-pipeline repo (it reads agent definitions from its own "
        "parent directory, not from --project-dir)."
    )

CLAUDE_BIN = shutil.which("claude")

# ---------------------------------------------------------------------------
# Agent + config loading — always from PIPELINE_ROOT (this repo), never from
# PROJECT_DIR. This is what lets --project-dir point at any target project
# without installing .claude/agents/ into it.
# ---------------------------------------------------------------------------


def load_agents():
    with open(PIPELINE_ROOT / "config" / "agents.yaml") as f:
        data = yaml.safe_load(f)
    return data["agents"]


def agents_by_id():
    return {a["id"]: a for a in load_agents()}


def read_prompt_body(agent_id: str) -> str:
    path = PIPELINE_ROOT / "prompts" / f"{agent_id}.md"
    if not path.exists():
        raise RuntimeError(f"prompts/{agent_id}.md not found under {PIPELINE_ROOT}")
    return path.read_text().strip()


def build_agents_json(agent_ids: list[str]) -> str:
    """Build the --agents inline JSON for the given agent ids, from this repo's
    own prompts/<id>.md + config/agents.yaml — the same source generate_agents.py
    uses, just assembled at request time instead of written to .claude/agents/."""
    by_id = agents_by_id()
    spec = {}
    for agent_id in agent_ids:
        agent = by_id.get(agent_id)
        if not agent:
            raise RuntimeError(f"unknown agent id: {agent_id}")
        spec[agent_id] = {
            "description": agent["description"],
            "prompt": read_prompt_body(agent_id),
            "tools": [resolve_tool_name(t) for t in agent["tools"]],
        }
    return json.dumps(spec)


def read_command_body(cmd_id: str) -> str:
    path = PIPELINE_ROOT / "prompts" / "commands" / f"{cmd_id}.md"
    if not path.exists():
        raise RuntimeError(f"prompts/commands/{cmd_id}.md not found under {PIPELINE_ROOT}")
    return path.read_text().strip()


def load_pipeline_config():
    """Non-location settings (runs_subdir, paths, inputs): project-specific
    pipeline.config.yaml wins if present, else this repo's own, else hardcoded
    defaults. output_dir's own location is handled separately by output_dir()
    below — see its docstring."""
    defaults = {
        "output_dir": "output",
        "runs_subdir": "runs",
        "paths": {"context": "context.md"},
    }
    for candidate in (PROJECT_DIR / "config" / "pipeline.config.yaml", PIPELINE_ROOT / "config" / "pipeline.config.yaml"):
        if candidate.exists():
            with open(candidate) as f:
                data = yaml.safe_load(f) or {}
            return {**defaults, **data, "paths": {**defaults["paths"], **(data.get("paths") or {})}}
    return defaults


def output_dir() -> Path:
    """Where this run's artifacts go, created if missing.

    If --project-dir has its own config/pipeline.config.yaml with an explicit
    output_dir, that wins (a team's deliberate customization for this specific
    project). Otherwise default to a sibling directory named after the project
    — <project-name>-qa-pipeline, next to --project-dir rather than nested
    inside it — created once and reused on every later run for that project."""
    project_cfg = PROJECT_DIR / "config" / "pipeline.config.yaml"
    if project_cfg.exists():
        with open(project_cfg) as f:
            data = yaml.safe_load(f) or {}
        if data.get("output_dir"):
            configured = Path(data["output_dir"])
            path = configured if configured.is_absolute() else (PROJECT_DIR / configured)
            path.mkdir(parents=True, exist_ok=True)
            return path

    path = PROJECT_DIR.parent / f"{PROJECT_DIR.name}-qa-pipeline"
    path.mkdir(parents=True, exist_ok=True)
    return path


def runs_dir() -> Path:
    cfg = load_pipeline_config()
    d = output_dir() / cfg["runs_subdir"]
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Job model + single-worker queue
# ---------------------------------------------------------------------------


class Job:
    def __init__(self, job_id, mode, agent_id=None, stages=None, run_id=None, extra_input=None):
        self.job_id = job_id
        self.mode = mode  # "agent" | "pipeline"
        self.agent_id = agent_id
        self.stages = stages
        self.run_id = run_id
        self.extra_input = extra_input
        self.status = "queued"  # queued | running | success | error
        self.created_at = time.time()
        self.started_at = None
        self.finished_at = None
        self.events = []  # replay buffer: list of dicts already sent to subscribers
        self.subscribers = []  # list[asyncio.Queue]
        self.log_path = LOGS_DIR / f"{job_id}.jsonl"

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "mode": self.mode,
            "agent_id": self.agent_id,
            "stages": self.stages,
            "run_id": self.run_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    async def emit(self, event: dict):
        self.events.append(event)
        for q in self.subscribers:
            await q.put(event)


JOBS: dict[str, Job] = {}
JOB_QUEUE: "asyncio.Queue[str]" = asyncio.Queue()
APPROVED_RUN_IDS: set[str] = set()


def pipeline_env() -> dict:
    """The dashboard's own env plus PIPELINE_ROOT/.env (e.g. GITLAB_PERSONAL_ACCESS_TOKEN,
    GITLAB_API_URL). The mcp-gitlab server's launch script also tries to `source .env`
    itself, but relative to the subprocess's cwd (PROJECT_DIR, the target project) —
    not PIPELINE_ROOT — so that lookup misses; loading it here and injecting into the
    subprocess env is what actually makes the values available."""
    env = os.environ.copy()
    env_file = PIPELINE_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def agent_uses_mcp(agent_id: str) -> bool:
    agent = agents_by_id().get(agent_id)
    return bool(agent) and any(t.startswith("mcp__") for t in agent["tools"])


def gitlab_config_hint() -> str:
    """gitlab-publisher's prompt tells it to read config/pipeline.config.yaml for the
    gitlab: block (project, wiki_release_notes_dir, severity_labels). That file lives
    in PIPELINE_ROOT, not PROJECT_DIR (the agent's cwd), so it's invisible to a plain
    Read the way output_dir isn't — output_dir has a safe hardcoded fallback, but
    gitlab.project doesn't, so the agent would otherwise correctly refuse to guess it.
    Resolve it here (same load_pipeline_config() the dashboard already uses) and hand
    the values over directly instead of leaving the agent to find the file itself."""
    cfg = load_pipeline_config()
    gitlab_cfg = cfg.get("gitlab") or {}
    if not gitlab_cfg.get("project"):
        return ""
    return (
        f" Do not try to read config/pipeline.config.yaml yourself — it lives in the "
        f"pipeline repo, not this project, so it won't be found here. Its `gitlab:` block "
        f"has already been resolved for you: project=`{gitlab_cfg['project']}`, "
        f"wiki_release_notes_dir=`{gitlab_cfg.get('wiki_release_notes_dir') or 'Version_History'}`, "
        f"severity_labels=`{gitlab_cfg.get('severity_labels')}`. Use these values directly."
    )


def mcp_config_args(agent_ids: list[str]) -> list[str]:
    """--mcp-config for PIPELINE_ROOT's .mcp.json, only when one of the given agents
    actually needs an mcp__ tool (e.g. gitlab-publisher). The subprocess runs with
    cwd=PROJECT_DIR (the target project being tested), which generally has no
    .mcp.json of its own, so the server definition has to be pointed at explicitly —
    it won't be auto-discovered from cwd."""
    if not any(agent_uses_mcp(a) for a in agent_ids):
        return []
    mcp_json = PIPELINE_ROOT / ".mcp.json"
    if not mcp_json.exists():
        raise RuntimeError(f".mcp.json not found under {PIPELINE_ROOT} (needed for mcp__ tools)")
    return ["--mcp-config", str(mcp_json)]


def build_command(job: Job):
    if not CLAUDE_BIN:
        raise RuntimeError("`claude` was not found on PATH")

    output_dir_hint = (
        f" Use `{output_dir()}` as output_dir for this run (it already exists — write "
        f"there, do not use any other output_dir default or fall back to a bare `output/`)."
    )

    if job.mode == "agent":
        prompt = AGENT_DEFAULT_PROMPTS.get(job.agent_id, "Run your instructions for this run.")
        if job.extra_input:
            prompt += f" Additional context: {job.extra_input}"
        if job.run_id:
            prompt += f" Use run_id {job.run_id}."
        prompt += output_dir_hint
        if job.agent_id == "gitlab-publisher":
            prompt += gitlab_config_hint()
        agents_json = build_agents_json([job.agent_id])
        return [
            CLAUDE_BIN, "-p", "--agents", agents_json, "--agent", job.agent_id,
            *mcp_config_args([job.agent_id]),
            "--output-format", "stream-json", "--verbose",
            "--permission-mode", "bypassPermissions",
            "--no-session-persistence",
            "--setting-sources", "project",
            prompt,
        ]

    # mode == "pipeline": the /qa-pipeline slash command also lives under .claude/
    # (not installed in the target project), so send its prompt body directly —
    # same $ARGUMENTS substitution a slash-command invocation would do — instead of
    # depending on the command being registered. Behavior/rules are unchanged, still
    # single-sourced from prompts/commands/qa-pipeline.md. The orchestrating session
    # gets every agent registered (via --agents) plus Task to delegate into them, but
    # no other tool — it can only hand off to subagents, never touch files itself.
    stage_args = job.stages.strip() if job.stages else ""
    prompt = read_command_body("qa-pipeline").replace("$ARGUMENTS", stage_args)
    if job.run_id:
        prompt += f"\n\nUse run_id {job.run_id} for every stage in this invocation."
    prompt += "\n\n" + output_dir_hint + " Pass this same output_dir instruction down to every subagent you delegate to."
    all_agent_ids = [a["id"] for a in load_agents()]
    agents_json = build_agents_json(all_agent_ids)
    return [
        CLAUDE_BIN, "-p", "--agents", agents_json,
        *mcp_config_args(all_agent_ids),
        "--output-format", "stream-json", "--verbose",
        "--allowedTools", "Task",
        "--permission-mode", "bypassPermissions",
        "--no-session-persistence",
        "--setting-sources", "project",
        prompt,
    ]


def describe_tool_call(name: str, tool_input: dict) -> str:
    """Plain-language description of a tool call, for a QA audience, not a code dump."""
    if name == "Read":
        return f"Reading {tool_input.get('file_path', '?')}"
    if name == "Write":
        return f"Writing {tool_input.get('file_path', '?')}"
    if name == "Grep":
        pattern = tool_input.get("pattern", "?")
        path = tool_input.get("path")
        return f"Searching for \"{pattern}\"" + (f" in {path}" if path else "")
    if name == "Glob":
        return f"Finding files matching {tool_input.get('pattern', '?')}"
    if name == "Bash":
        cmd = tool_input.get("command", "")
        return f"Running: {cmd[:200]}"
    if name == "Task":
        return f"Delegating to {tool_input.get('subagent_type', 'a subagent')}: {str(tool_input.get('description', ''))[:120]}"
    return f"{name}({json.dumps(tool_input)[:200]})"


def summarize_line(raw: dict) -> dict | None:
    """Turn one stream-json line into a small display event, or None to skip it."""
    t = raw.get("type")
    if t == "system" and raw.get("subtype") == "init":
        return {"kind": "system", "text": f"Session started (model {raw.get('model')})"}
    if t == "assistant":
        parts = []
        for block in raw.get("message", {}).get("content", []):
            if block.get("type") == "text" and block.get("text"):
                parts.append({"kind": "text", "text": block["text"]})
            elif block.get("type") == "tool_use":
                parts.append({"kind": "tool_call", "text": describe_tool_call(block.get("name", "?"), block.get("input", {}))})
        return parts or None
    if t == "user":
        for block in raw.get("message", {}).get("content", []):
            if block.get("type") == "tool_result":
                content = block.get("content")
                text = content if isinstance(content, str) else json.dumps(content)
                return {"kind": "tool_result", "text": text[:300]}
    if t == "result":
        kind = "error" if raw.get("is_error") else "result"
        return {"kind": kind, "text": raw.get("result", "")}
    return None


async def run_job(job: Job):
    job.status = "running"
    job.started_at = time.time()
    try:
        cmd = build_command(job)
        if job.run_id:
            (runs_dir() / job.run_id).mkdir(parents=True, exist_ok=True)
    except RuntimeError as e:
        await job.emit({"kind": "error", "text": str(e)})
        job.status = "error"
        job.finished_at = time.time()
        await job.emit({"kind": "done", "status": job.status})
        return

    label = job.agent_id if job.mode == "agent" else f"pipeline: {job.stages}"
    await job.emit({"kind": "system", "text": f"Starting {label} (run_id {job.run_id or 'default'})"})
    # Full command incl. the inline --agents JSON — useful for debugging, too noisy for
    # the default log view, so it's tagged "debug" and the UI hides it behind a toggle.
    await job.emit({"kind": "debug", "text": " ".join(cmd[:-1]) + " <prompt>"})

    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(PROJECT_DIR), env=pipeline_env(),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        # stream-json lines can carry a full tool result (e.g. a large file read or
        # directory listing) inline as a single line — asyncio's default 64KB
        # StreamReader limit is too small for that and raises LimitOverrunError.
        limit=32 * 1024 * 1024,
    )

    with open(job.log_path, "a") as logf:
        async def pump_stdout():
            async for line in proc.stdout:
                text = line.decode(errors="replace").strip()
                if not text:
                    continue
                logf.write(text + "\n")
                logf.flush()
                try:
                    raw = json.loads(text)
                except json.JSONDecodeError:
                    await job.emit({"kind": "raw", "text": text})
                    continue
                summary = summarize_line(raw)
                if summary is None:
                    continue
                if isinstance(summary, list):
                    for s in summary:
                        await job.emit(s)
                else:
                    await job.emit(summary)

        async def pump_stderr():
            async for line in proc.stderr:
                text = line.decode(errors="replace").strip()
                if text:
                    await job.emit({"kind": "stderr", "text": text})

        await asyncio.gather(pump_stdout(), pump_stderr())
        returncode = await proc.wait()

    job.status = "success" if returncode == 0 else "error"
    job.finished_at = time.time()
    await job.emit({"kind": "done", "status": job.status})


async def worker_loop():
    while True:
        job_id = await JOB_QUEUE.get()
        job = JOBS[job_id]
        try:
            await run_job(job)
        except Exception as e:  # keep the worker alive no matter what
            job.status = "error"
            job.finished_at = time.time()
            await job.emit({"kind": "error", "text": f"dashboard error: {e}"})
            await job.emit({"kind": "done", "status": job.status})
        finally:
            JOB_QUEUE.task_done()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(worker_loop())
    yield
    task.cancel()


app = FastAPI(title="QA Agent Pipeline Dashboard", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index():
    # Cache-bust style.css/app.js with each file's own mtime, so browsers always
    # pick up edits during development instead of serving a stale cached copy.
    html = (STATIC_DIR / "index.html").read_text()
    for asset in ("style.css", "app.js"):
        mtime = int((STATIC_DIR / asset).stat().st_mtime)
        html = html.replace(f"/static/{asset}", f"/static/{asset}?v={mtime}")
    return html


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/api/agents")
async def api_agents():
    return load_agents()


@app.get("/api/paths")
async def api_paths():
    return {"project_dir": str(PROJECT_DIR), "output_dir": str(output_dir())}


@app.get("/api/runs")
async def api_runs():
    return sorted((j.to_dict() for j in JOBS.values()), key=lambda j: j["created_at"], reverse=True)


@app.post("/api/run")
async def api_run(request: Request):
    body = await request.json()
    mode = body.get("mode")
    if mode not in ("agent", "pipeline"):
        raise HTTPException(400, "mode must be 'agent' or 'pipeline'")
    if mode == "agent" and not body.get("agent_id"):
        raise HTTPException(400, "agent_id is required for mode=agent")
    if mode == "pipeline" and not body.get("stages"):
        raise HTTPException(400, "stages is required for mode=pipeline")

    job_id = uuid.uuid4().hex[:12]
    job = Job(
        job_id, mode,
        agent_id=body.get("agent_id"),
        stages=body.get("stages"),
        run_id=(body.get("run_id") or "").strip() or None,
        extra_input=(body.get("extra_input") or "").strip() or None,
    )
    JOBS[job_id] = job
    await JOB_QUEUE.put(job_id)
    return {"job_id": job_id}


@app.get("/api/runs/{job_id}/stream")
async def api_stream(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job_id")

    async def gen():
        for event in list(job.events):
            yield f"data: {json.dumps(event)}\n\n"
        if job.status in ("success", "error"):
            yield f"data: {json.dumps({'kind': 'done', 'status': job.status})}\n\n"
            return
        q: asyncio.Queue = asyncio.Queue()
        job.subscribers.append(q)
        try:
            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("kind") == "done":
                    break
        finally:
            job.subscribers.remove(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/approve")
async def api_approve(request: Request):
    body = await request.json()
    run_id = (body.get("run_id") or "").strip()
    if not run_id:
        raise HTTPException(400, "run_id is required")
    APPROVED_RUN_IDS.add(run_id)
    return {"approved": sorted(APPROVED_RUN_IDS)}


@app.get("/api/approved")
async def api_approved():
    return {"run_ids": sorted(APPROVED_RUN_IDS)}


def _safe_output_path(rel_path: str) -> Path:
    base = output_dir().resolve()
    candidate = (base / rel_path).resolve()
    if base not in candidate.parents and candidate != base:
        raise HTTPException(400, "path escapes output_dir")
    return candidate


@app.get("/api/output/tree")
async def api_output_tree(run_id: str | None = None):
    base = output_dir()
    cfg = load_pipeline_config()
    entries = []
    context_name = cfg["paths"].get("context", "context.md")
    if (base / context_name).exists():
        entries.append({"path": context_name, "label": context_name})

    regression_inventory_name = cfg["paths"].get("regression_inventory", "regression-inventory.md")
    if (base / regression_inventory_name).exists():
        entries.append({"path": regression_inventory_name, "label": regression_inventory_name})

    regression_inventory_csv_name = cfg["paths"].get("regression_inventory_csv", "regression-inventory.csv")
    if (base / regression_inventory_csv_name).exists():
        entries.append({"path": regression_inventory_csv_name, "label": regression_inventory_csv_name})

    rd = runs_dir()
    available_runs = sorted(
        [p.name for p in rd.iterdir() if p.is_dir()] if rd.exists() else [],
        reverse=True,
    )

    files = []
    if run_id and (rd / run_id).exists():
        run_root = rd / run_id
        for p in sorted(run_root.rglob("*")):
            if p.is_file():
                rel = p.relative_to(base)
                files.append({"path": str(rel), "label": str(p.relative_to(run_root))})

    return {"context_files": entries, "available_runs": available_runs, "run_files": files}


@app.get("/api/output/file")
async def api_output_file(path: str):
    full = _safe_output_path(path)
    if not full.exists() or not full.is_file():
        raise HTTPException(404, "file not found")

    if full.suffix.lower() == ".csv":
        text = full.read_text(errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
        header, body = (rows[0], rows[1:]) if rows else ([], [])
        return {"type": "csv", "header": header, "rows": body}

    if full.suffix.lower() in (".md", ".markdown"):
        text = full.read_text(errors="replace")
        html = md.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
        return {"type": "markdown", "html": html, "raw": text}

    return {"type": "text", "raw": full.read_text(errors="replace")}


if __name__ == "__main__":
    import uvicorn

    print(f"QA Agent Pipeline Dashboard")
    print(f"  pipeline source: {PIPELINE_ROOT}")
    print(f"  target project:  {PROJECT_DIR}")
    if not CLAUDE_BIN:
        print("WARNING: `claude` not found on PATH — runs will fail until it is installed.")
    uvicorn.run(app, host="127.0.0.1", port=ARGS.port)
