import argparse
from pathlib import Path


INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Board</title>
  <style>
    body { font: 14px system-ui, sans-serif; margin: 32px; background: #111; color: #eee; }
    table { width: 100%; border-collapse: collapse; margin-top: 24px; }
    th, td { padding: 10px; border-bottom: 1px solid #333; text-align: left; }
    #diagnostics:not(:empty) { color: #ffb4a8; white-space: pre-wrap; }
  </style>
</head>
<body>
  <h1 id="project-name">Agent Board</h1>
  <p id="project-goal"></p>
  <p id="project-phase"></p>
  <p id="diagnostics" role="alert"></p>
  <table>
    <thead><tr><th>Task</th><th>Title</th><th>Status</th><th>Claim</th></tr></thead>
    <tbody id="tasks"></tbody>
  </table>
  <h2>Runs</h2>
  <table>
    <thead><tr><th>Run</th><th>Task</th><th>Summary</th></tr></thead>
    <tbody id="runs"></tbody>
  </table>
  <h2>Reviews</h2>
  <table>
    <thead><tr><th>Review</th><th>Task</th><th>Status</th></tr></thead>
    <tbody id="reviews"></tbody>
  </table>
  <script src="app.js"></script>
</body>
</html>
"""


APP = """(function () {
  const text = (value) => value == null ? "" : String(value);
  const setText = (id, value) => { document.getElementById(id).textContent = text(value); };
  const records = (value) => Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];

  function renderRecords(id, entries, values) {
    const tbody = document.getElementById(id);
    tbody.replaceChildren();
    records(entries).forEach((entry) => {
      const row = document.createElement("tr");
      values(entry).forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = text(value);
        row.appendChild(cell);
      });
      tbody.appendChild(row);
    });
  }

  function render(snapshot) {
    const project = snapshot.project || {};
    setText("project-name", project.name || "Agent Board");
    setText("project-goal", project.goal || "");
    setText("project-phase", project.phase ? "Phase: " + project.phase : "");
    const diagnostics = Array.isArray(snapshot.diagnostics) ? snapshot.diagnostics : [];
    setText("diagnostics", diagnostics.join("\\n"));

    const claims = Array.isArray(snapshot.claims) ? snapshot.claims : [];
    const claimsByTask = Object.fromEntries(claims.map((claim) => [claim.task, claim]));
    const states = snapshot.states || {};
    renderRecords("tasks", snapshot.tasks, (task) => {
      const state = states[task.id] || {};
      const claim = claimsByTask[task.id] || {};
      return [task.id, task.title, state.status, claim.worker_id || claim.worker || claim.owner];
    });
    renderRecords("runs", snapshot.runs, (run) => [run.run_id || run.id, run.task, run.result && run.result.summary]);
    renderRecords("reviews", snapshot.reviews, (review) => [review.review_id || review.id, review.task, review.status || review.decision]);
  }

  async function refresh() {
    try {
      const response = await fetch("/api/board", { cache: "no-store" });
      if (!response.ok) throw new Error("Dashboard API returned " + response.status);
      render(await response.json());
    } catch (error) {
      setText("diagnostics", "Unable to load live board: " + error.message);
    }
  }

  refresh();
  window.setInterval(refresh, 5000);
}());
"""


parser = argparse.ArgumentParser()
parser.add_argument("--board", default=".agent-board")
args = parser.parse_args()
dashboard = Path(args.board) / "dashboard"
dashboard.mkdir(parents=True, exist_ok=True)
(dashboard / "index.html").write_text(INDEX)
(dashboard / "app.js").write_text(APP)
print((dashboard / "index.html").resolve())
