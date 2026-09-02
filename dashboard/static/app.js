const runIdInput = document.getElementById("run-id");
const logPane = document.getElementById("log-pane");
const jobStatusEl = document.getElementById("job-status");
const approveBanner = document.getElementById("approve-banner");
const runsListEl = document.getElementById("runs-list");
const agentListEl = document.getElementById("agent-list");
const outputTreeEl = document.getElementById("output-tree");
const outputViewEl = document.getElementById("output-view");
const debugToggle = document.getElementById("toggle-debug");

const AGENT_ICONS = {
  "context-analyzer": "🧭",
  "changelog-analyzer": "📝",
  "requirements-analyzer": "📋",
  "code-scanner": "🔍",
  "test-planner": "🗂️",
  "test-case-writer": "✅",
  "log-analyzer": "📈",
  "rca-analyst": "🕵️",
  "bug-reporter": "🐞",
  "release-notes-writer": "📰",
};

const LOG_PREFIX = {
  tool_call: "→",
  tool_result: "·",
  error: "✗",
  result: "✓",
  stderr: "!",
  system: "ⓘ",
  text: "",
  debug: "⚙",
};

let AGENTS = [];
let APPROVED_RUN_IDS = new Set();
let currentEventSource = null;
let currentFilePath = null;

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}
runIdInput.value = todayStr();

function currentRunId() {
  return runIdInput.value.trim() || todayStr();
}

debugToggle.addEventListener("change", () => {
  logPane.classList.toggle("show-debug", debugToggle.checked);
});

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---------------------------------------------------------------------------
// Agents panel
// ---------------------------------------------------------------------------

async function loadAgents() {
  AGENTS = await fetchJSON("/api/agents");
  agentListEl.innerHTML = "";
  for (const agent of AGENTS) {
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.agentId = agent.id;
    card.innerHTML = `
      <div class="card-top"><span class="icon">${AGENT_ICONS[agent.id] || "🤖"}</span><span class="name">${agent.id}</span></div>
      <div class="desc">${agent.description}</div>
      <input type="text" placeholder="optional context (commit range, log path, symptom...)" />
      <button>▶ Run</button>
    `;
    const input = card.querySelector("input");
    const button = card.querySelector("button");
    button.addEventListener("click", () => runAgent(agent.id, input.value));
    agentListEl.appendChild(card);
  }
  applyApprovalGate();
}

function applyApprovalGate() {
  const card = agentListEl.querySelector('[data-agent-id="test-case-writer"]');
  if (!card) return;
  const button = card.querySelector("button");
  const approved = APPROVED_RUN_IDS.has(currentRunId());
  button.disabled = !approved;
  button.title = approved ? "" : `Approve the test plan for run_id "${currentRunId()}" first`;
}

runIdInput.addEventListener("input", applyApprovalGate);

async function refreshApproved() {
  const data = await fetchJSON("/api/approved");
  APPROVED_RUN_IDS = new Set(data.run_ids);
  applyApprovalGate();
}

// ---------------------------------------------------------------------------
// Running jobs
// ---------------------------------------------------------------------------

async function runAgent(agentId, extraInput) {
  const body = { mode: "agent", agent_id: agentId, run_id: currentRunId(), extra_input: extraInput };
  const { job_id } = await fetchJSON("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  streamJob(job_id, { mode: "agent", agent_id: agentId, run_id: currentRunId() });
}

document.getElementById("run-pipeline").addEventListener("click", async () => {
  const stages = document.getElementById("stages").value.trim() || "context changelog code-scan requirements test-plan";
  const body = { mode: "pipeline", stages, run_id: currentRunId() };
  const { job_id } = await fetchJSON("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  streamJob(job_id, { mode: "pipeline", stages, run_id: currentRunId() });
});

function appendLog(event) {
  const line = document.createElement("div");
  line.className = `log-line ${event.kind}`;
  const prefix = document.createElement("span");
  prefix.className = "prefix";
  prefix.textContent = LOG_PREFIX[event.kind] ?? "";
  const text = document.createElement("span");
  text.textContent = event.text || "";
  line.appendChild(prefix);
  line.appendChild(text);
  logPane.appendChild(line);
  logPane.scrollTop = logPane.scrollHeight;
}

function setStatusBadge(status) {
  jobStatusEl.className = `badge ${status}`;
  jobStatusEl.textContent = status;
}

function streamJob(jobId, meta) {
  if (currentEventSource) currentEventSource.close();
  logPane.innerHTML = "";
  approveBanner.classList.add("hidden");
  setStatusBadge("running");

  const es = new EventSource(`/api/runs/${jobId}/stream`);
  currentEventSource = es;
  es.onmessage = (msg) => {
    const event = JSON.parse(msg.data);
    if (event.kind === "done") {
      setStatusBadge(event.status);
      es.close();
      refreshRuns();
      refreshOutputTree();
      if (meta.mode === "agent" && meta.agent_id === "test-planner" && event.status === "success") {
        showApproveBanner(meta.run_id);
      }
      return;
    }
    appendLog(event);
  };
  es.onerror = () => { setStatusBadge("error"); es.close(); };
}

function showApproveBanner(runId) {
  approveBanner.classList.remove("hidden");
  approveBanner.innerHTML = `
    <span>✅ test-plan.md is ready for run_id <strong>${runId}</strong> — review it in the Output panel, then approve to unlock Test Case Writer.</span>
    <button id="approve-btn">Approve</button>
  `;
  document.getElementById("approve-btn").addEventListener("click", async () => {
    await fetchJSON("/api/approve", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_id: runId }),
    });
    await refreshApproved();
    approveBanner.classList.add("hidden");
  });
}

// ---------------------------------------------------------------------------
// Run history
// ---------------------------------------------------------------------------

function timeAgo(ts) {
  if (!ts) return "";
  const diff = Math.max(0, Date.now() / 1000 - ts);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

async function refreshRuns() {
  const runs = await fetchJSON("/api/runs");
  runsListEl.innerHTML = "";
  if (!runs.length) {
    runsListEl.innerHTML = `<p class="hint">No runs yet.</p>`;
    return;
  }
  for (const run of runs) {
    const item = document.createElement("div");
    item.className = "run-item";
    const label = run.mode === "agent" ? `${AGENT_ICONS[run.agent_id] || "🤖"} ${run.agent_id}` : `🧵 pipeline: ${run.stages}`;
    item.innerHTML = `
      <div class="run-item-main">
        <span class="run-item-label">${label}</span>
        <span class="run-item-sub">run_id ${run.run_id || "(default)"} · ${timeAgo(run.created_at)}</span>
      </div>
      <span class="badge ${run.status}">${run.status}</span>
    `;
    item.addEventListener("click", () => streamJob(run.job_id, { mode: run.mode, agent_id: run.agent_id, run_id: run.run_id }));
    runsListEl.appendChild(item);
  }
}

// ---------------------------------------------------------------------------
// Output browser
// ---------------------------------------------------------------------------

const FILE_ICON = (label) => {
  if (label.endsWith(".csv")) return "📊";
  if (label.endsWith(".md")) return "📄";
  return "📁";
};

async function refreshOutputTree() {
  const runId = currentRunId();
  const data = await fetchJSON(`/api/output/tree?run_id=${encodeURIComponent(runId)}`);
  outputTreeEl.innerHTML = "";

  const addLabel = (text) => {
    const el = document.createElement("div");
    el.className = "tree-item section-label";
    el.textContent = text;
    outputTreeEl.appendChild(el);
  };
  const addFile = (path, label) => {
    const el = document.createElement("div");
    el.className = "tree-item";
    el.dataset.path = path;
    el.innerHTML = `<span>${FILE_ICON(label)}</span><span>${label}</span>`;
    el.addEventListener("click", () => viewFile(path, el));
    outputTreeEl.appendChild(el);
  };

  if (data.context_files.length) {
    addLabel("Project (unversioned)");
    for (const f of data.context_files) addFile(f.path, f.label);
  }
  if (data.run_files.length) {
    addLabel(`run_id: ${runId}`);
    for (const f of data.run_files) addFile(f.path, f.label);
  } else {
    addLabel(`run_id: ${runId} (no files yet)`);
  }
  if (data.available_runs.length) {
    addLabel("Other runs");
    for (const rid of data.available_runs) {
      const el = document.createElement("div");
      el.className = "tree-item";
      el.innerHTML = `<span>🗓️</span><span>${rid}</span>`;
      el.addEventListener("click", () => { runIdInput.value = rid; refreshOutputTree(); applyApprovalGate(); });
      outputTreeEl.appendChild(el);
    }
  }
}

async function viewFile(path, el) {
  currentFilePath = path;
  outputTreeEl.querySelectorAll(".tree-item.active").forEach((n) => n.classList.remove("active"));
  if (el) el.classList.add("active");

  const data = await fetchJSON(`/api/output/file?path=${encodeURIComponent(path)}`);
  if (data.type === "markdown") {
    outputViewEl.innerHTML = data.html;
  } else if (data.type === "csv") {
    const rows = [data.header, ...data.rows];
    const table = document.createElement("table");
    rows.forEach((row, i) => {
      const tr = document.createElement("tr");
      row.forEach((cell) => {
        const cellEl = document.createElement(i === 0 ? "th" : "td");
        cellEl.textContent = cell;
        tr.appendChild(cellEl);
      });
      table.appendChild(tr);
    });
    outputViewEl.innerHTML = "";
    outputViewEl.appendChild(table);
  } else {
    outputViewEl.innerHTML = `<pre>${data.raw}</pre>`;
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

async function refreshPaths() {
  const paths = await fetchJSON("/api/paths");
  document.getElementById("output-path-label").textContent = `💾 saving to ${paths.output_dir}`;
}

(async function init() {
  setStatusBadge("idle");
  await loadAgents();
  await refreshApproved();
  await refreshRuns();
  await refreshOutputTree();
  await refreshPaths();
})();
