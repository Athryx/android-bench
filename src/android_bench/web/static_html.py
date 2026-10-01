from __future__ import annotations

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>android-bench Results Viewer</title>
<style>
:root {
  color-scheme: dark;
  --bg: #0d1117;
  --panel: #161b22;
  --panel-hover: #1c2128;
  --panel-active: #21262d;
  --border: #30363d;
  --border-subtle: #21262d;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --text-dim: #6e7681;
  --accent: #58a6ff;
  --accent-muted: rgba(88, 166, 255, 0.15);
  --green: #3fb950;
  --green-bg: rgba(63, 185, 80, 0.15);
  --red: #f85149;
  --red-bg: rgba(248, 81, 73, 0.15);
  --yellow: #d29922;
  --yellow-bg: rgba(210, 153, 34, 0.15);
  --purple: #bc8cff;
  --purple-bg: rgba(188, 140, 255, 0.15);
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
}

* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: var(--font-sans); font-size: 13px; line-height: 1.5; overflow: hidden; }

/* Layout */
.app-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  width: 320px;
  min-width: 260px;
  max-width: 500px;
  background: var(--panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 100%;
  user-select: none;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.app-brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: var(--text);
  letter-spacing: -0.2px;
}

.brand-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  background: var(--accent-muted);
  color: var(--accent);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid rgba(88, 166, 255, 0.3);
}

.sidebar-search-row {
  display: flex;
  gap: 6px;
  align-items: center;
}

.search-input {
  flex: 1;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 9px;
  color: var(--text);
  font-size: 12px;
  outline: none;
  transition: border-color 0.15s;
}
.search-input:focus {
  border-color: var(--accent);
}

.btn-icon {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 5px 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.btn-icon:hover {
  background: var(--panel-hover);
  color: var(--text);
  border-color: var(--text-muted);
}

.tree-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 6px;
}

/* Tree items */
.tree-node {
  margin: 1px 0;
}

.tree-folder-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-radius: 4px;
  cursor: pointer;
  color: var(--text);
  font-weight: 500;
  font-size: 12px;
  transition: background 0.1s;
}
.tree-folder-row:hover {
  background: var(--panel-hover);
}

.tree-chevron {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s ease;
  color: var(--text-muted);
}
.tree-chevron.expanded {
  transform: rotate(90deg);
}

.tree-folder-children {
  padding-left: 14px;
  border-left: 1px solid var(--border-subtle);
  margin-left: 7px;
}
.tree-folder-children.hidden {
  display: none;
}

.tree-run-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 7px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.12s;
  border-left: 3px solid transparent;
  margin: 2px 0;
}
.tree-run-item:hover {
  background: var(--panel-hover);
}
.tree-run-item.active {
  background: #1c2633;
  border-left-color: var(--accent);
}

.run-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.run-item-title {
  font-weight: 550;
  font-size: 12.5px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.run-item-badges {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.run-item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--text-dim);
  font-size: 11px;
}

/* Badges & Pills */
.pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 10px;
  line-height: 1.4;
  white-space: nowrap;
}
.pill-sm { font-size: 10px; padding: 0 5px; }

.pill-completed, .pill-passed {
  background: var(--green-bg);
  color: var(--green);
  border: 1px solid rgba(63, 185, 80, 0.3);
}
.pill-running {
  background: var(--accent-muted);
  color: var(--accent);
  border: 1px solid rgba(88, 166, 255, 0.3);
}
.pill-failed {
  background: var(--red-bg);
  color: var(--red);
  border: 1px solid rgba(248, 81, 73, 0.3);
}
.pill-warn, .pill-partial {
  background: var(--yellow-bg);
  color: var(--yellow);
  border: 1px solid rgba(210, 153, 34, 0.3);
}
.pill-pending {
  background: rgba(110, 118, 129, 0.15);
  color: var(--text-muted);
  border: 1px solid rgba(110, 118, 129, 0.3);
}
.pill-score {
  font-family: var(--font-mono);
  font-weight: 600;
}

/* Main content */
.main-view {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: var(--bg);
}

.empty-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  gap: 12px;
  padding: 40px;
  text-align: center;
}
.empty-view svg {
  width: 48px;
  height: 48px;
  stroke: var(--text-dim);
}

.run-content {
  padding: 24px 32px;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Header Section */
.run-header-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.run-header-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.run-title-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.run-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.run-meta-row {
  display: flex;
  align-items: center;
  gap: 16px;
  color: var(--text-muted);
  font-size: 12px;
  flex-wrap: wrap;
}

.run-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--panel-active);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s;
  text-decoration: none;
}
.btn:hover {
  background: #30363d;
  border-color: var(--text-muted);
}
.btn-primary {
  background: #238636;
  border-color: rgba(240, 246, 252, 0.1);
  color: #fff;
}
.btn-primary:hover {
  background: #2ea043;
}

.run-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-item {
  background: var(--bg);
  border: 1px solid var(--border-subtle);
  border-radius: 5px;
  padding: 3px 8px;
  font-size: 11.5px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 5px;
}
.tag-item strong {
  color: var(--text);
  font-weight: 550;
}

/* Notes Card */
.notes-card {
  background: #121820;
  border: 1px solid rgba(88, 166, 255, 0.3);
  border-radius: 8px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notes-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(88, 166, 255, 0.15);
  padding-bottom: 8px;
  font-weight: 600;
  color: var(--accent);
  font-size: 13px;
}

.notes-body {
  font-size: 13px;
  color: var(--text);
  white-space: pre-wrap;
  line-height: 1.6;
}

/* Section Headings */
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Challenges List */
.challenges-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.challenge-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.15s;
}
.challenge-card:hover {
  border-color: #444c56;
}

.challenge-header {
  padding: 14px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  background: var(--panel);
  gap: 12px;
  user-select: none;
}
.challenge-header:hover {
  background: var(--panel-hover);
}

.challenge-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.challenge-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.challenge-pkg {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--text-muted);
}

.challenge-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.axes-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  font-size: 12px;
}
.axes-table th {
  background: var(--panel-active);
  padding: 9px 12px;
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.axes-table td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--border-subtle);
  vertical-align: middle;
}
.axes-table tr:last-child td {
  border-bottom: none;
}
.axes-table tr:hover td {
  background: rgba(255, 255, 255, 0.02);
}

.tag-clean {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: var(--green);
  font-weight: 500;
  font-size: 11.5px;
}
.tag-warn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: var(--yellow);
  font-weight: 500;
  font-size: 11.5px;
}
.tag-alert {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: var(--red-bg);
  color: var(--red);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 11px;
  border: 1px solid rgba(248, 81, 73, 0.3);
}

.challenge-body {
  border-top: 1px solid var(--border);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  background: #11151c;
}
.challenge-body.hidden {
  display: none;
}

/* Trace Link Banner */
.trace-banner {
  background: rgba(88, 166, 255, 0.08);
  border: 1px solid rgba(88, 166, 255, 0.25);
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.trace-session-text {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

/* Attempts Tabs */
.attempts-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.attempt-tabs {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}

.tab-btn {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 550;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
}
.tab-btn:hover {
  color: var(--text);
  background: var(--panel-hover);
}
.tab-btn.active {
  background: var(--panel-active);
  border-color: var(--border);
  color: var(--accent);
}

.attempt-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Collapsible Box */
.collapse-box {
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--panel);
  overflow: hidden;
}

.collapse-header {
  padding: 8px 12px;
  background: var(--panel);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 550;
  font-size: 12.5px;
  color: var(--text);
  user-select: none;
}
.collapse-header:hover {
  background: var(--panel-hover);
}

.collapse-body {
  padding: 12px;
  border-top: 1px solid var(--border);
  background: var(--bg);
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow: auto;
  line-height: 1.5;
}
.collapse-body.hidden {
  display: none;
}

.reprompt-alert {
  border-color: rgba(210, 153, 34, 0.4);
}
.reprompt-alert .collapse-header {
  color: var(--yellow);
  background: var(--yellow-bg);
}

/* Capabilities Grid */
.caps-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
}

.cap-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cap-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cap-name {
  font-weight: 600;
  font-size: 12.5px;
}

.cap-detail {
  font-size: 11px;
  color: var(--text-muted);
}

.cap-review {
  font-size: 10.5px;
  padding: 4px 6px;
  border-radius: 4px;
  background: var(--bg);
  border: 1px solid var(--border-subtle);
  color: var(--text-dim);
}

/* Toast */
.toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: #238636;
  color: #fff;
  padding: 8px 14px;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  font-size: 12px;
  font-weight: 500;
  opacity: 0;
  transform: translateY(10px);
  transition: all 0.2s ease;
  pointer-events: none;
  z-index: 1000;
}
.toast.show {
  opacity: 1;
  transform: translateY(0);
}

/* Scrollbars */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #484f58; }
</style>
</head>
<body>

<div class="app-container">
  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="app-brand">
        <div class="brand-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
            <line x1="8" y1="21" x2="16" y2="21"></line>
            <line x1="12" y1="17" x2="12" y2="21"></line>
          </svg>
          android-bench
        </div>
        <span class="brand-badge">Results</span>
      </div>
      <div class="sidebar-search-row">
        <input type="text" id="searchInput" class="search-input" placeholder="Search runs..." oninput="filterTree()">
        <button class="btn-icon" onclick="refreshTree()" title="Refresh Tree">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 4 23 10 17 10"></polyline>
            <polyline points="1 20 1 14 7 14"></polyline>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
        </button>
      </div>
    </div>
    <div class="tree-container" id="treeContainer">
      <div style="padding: 16px; color: var(--text-muted); text-align: center;">Loading runs...</div>
    </div>
  </aside>

  <!-- Main View -->
  <main class="main-view" id="mainView">
    <div class="empty-view" id="emptyView">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
        <polyline points="10 9 9 9 8 9"></polyline>
      </svg>
      <div><strong>No Benchmark Run Selected</strong></div>
      <div style="font-size: 12px;">Select a benchmark run from the sidebar to inspect scores, reprompts, and traces.</div>
    </div>

    <div class="run-content" id="runContent" style="display: none;">
      <!-- Populated via JavaScript -->
    </div>
  </main>
</div>

<div id="toast" class="toast">Path copied to clipboard</div>

<script>
let currentTree = [];
let selectedRunPath = null;
let currentRunDetail = null;

// On load
window.addEventListener('DOMContentLoaded', () => {
  refreshTree();
});

async function refreshTree() {
  try {
    const res = await fetch('/api/tree');
    const data = await res.json();
    currentTree = data.items || [];
    renderTree(currentTree);
    if (selectedRunPath) {
      loadRun(selectedRunPath);
    } else if (currentTree.length > 0) {
      // Auto-select first run if available
      const firstRun = findFirstRun(currentTree);
      if (firstRun) {
        loadRun(firstRun.path);
      }
    }
  } catch (err) {
    document.getElementById('treeContainer').innerHTML = `<div style="padding:16px;color:var(--red);">Failed to load runs: ${err.message}</div>`;
  }
}

function findFirstRun(nodes) {
  for (const n of nodes) {
    if (n.type === 'run') return n;
    if (n.children && n.children.length > 0) {
      const found = findFirstRun(n.children);
      if (found) return found;
    }
  }
  return null;
}

function renderTree(nodes, container = document.getElementById('treeContainer'), level = 0) {
  if (level === 0) container.innerHTML = '';
  if (!nodes || nodes.length === 0) {
    if (level === 0) {
      container.innerHTML = '<div style="padding:16px;color:var(--text-muted);text-align:center;">No benchmark runs found.</div>';
    }
    return;
  }

  for (const node of nodes) {
    if (node.type === 'folder') {
      const folderDiv = document.createElement('div');
      folderDiv.className = 'tree-node';

      const row = document.createElement('div');
      row.className = 'tree-folder-row';
      row.innerHTML = `
        <span class="tree-chevron expanded">▶</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:#e3b341;">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
        </svg>
        <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(node.name)}</span>
      `;

      const childrenContainer = document.createElement('div');
      childrenContainer.className = 'tree-folder-children';

      row.onclick = () => {
        const isHidden = childrenContainer.classList.toggle('hidden');
        row.querySelector('.tree-chevron').classList.toggle('expanded', !isHidden);
      };

      folderDiv.appendChild(row);
      folderDiv.appendChild(childrenContainer);
      container.appendChild(folderDiv);

      renderTree(node.children, childrenContainer, level + 1);
    } else {
      // Run node
      const runDiv = document.createElement('div');
      runDiv.className = `tree-run-item ${selectedRunPath === node.path ? 'active' : ''}`;
      runDiv.dataset.path = node.path;
      runDiv.dataset.name = node.name.toLowerCase();
      runDiv.dataset.display = node.display_name.toLowerCase();

      const scoreText = (node.score !== null && node.score !== undefined) ? node.score.toFixed(3) : '-';
      let scorePillClass = 'pill-pending';
      if (node.score !== null && node.score !== undefined) {
        if (node.score >= 0.99) scorePillClass = 'pill-completed';
        else if (node.score > 0) scorePillClass = 'pill-partial';
        else scorePillClass = 'pill-failed';
      }

      runDiv.innerHTML = `
        <div class="run-item-top">
          <span class="run-item-title" title="${escapeHtml(node.display_name)}">${escapeHtml(node.display_name)}</span>
          <div class="run-item-badges">
            <span class="pill pill-score ${scorePillClass} pill-sm">${scoreText}</span>
          </div>
        </div>
        <div class="run-item-meta">
          <span>${escapeHtml(node.started_at || '')}</span>
          <span class="pill pill-${node.status || 'pending'} pill-sm">${node.status || 'unknown'}</span>
        </div>
      `;

      runDiv.onclick = () => {
        loadRun(node.path);
      };

      container.appendChild(runDiv);
    }
  }
}

function filterTree() {
  const query = document.getElementById('searchInput').value.trim().toLowerCase();
  const runItems = document.querySelectorAll('.tree-run-item');
  runItems.forEach(item => {
    const match = !query || item.dataset.name.includes(query) || item.dataset.display.includes(query);
    item.style.display = match ? 'flex' : 'none';
  });
}

async function loadRun(path) {
  selectedRunPath = path;
  // Update active state in sidebar
  document.querySelectorAll('.tree-run-item').forEach(item => {
    item.classList.toggle('active', item.dataset.path === path);
  });

  try {
    const res = await fetch(`/api/runs/${encodeURIComponent(path)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentRunDetail = data;
    renderRunDetail(data);
  } catch (err) {
    alert(`Could not load run: ${err.message}`);
  }
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '0s';
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const remS = s % 60;
  if (m > 0) return `${m}m ${remS}s`;
  return `${s}s`;
}

function renderRunDetail(run) {
  document.getElementById('emptyView').style.display = 'none';
  const content = document.getElementById('runContent');
  content.style.display = 'flex';

  const scoreNum = run.score || 0.0;
  const scorePct = Math.round(scoreNum * 100);
  let scoreClass = 'pill-failed';
  if (scoreNum >= 0.99) scoreClass = 'pill-completed';
  else if (scoreNum > 0) scoreClass = 'pill-partial';

  let notesHtml = '';
  if (run.notes && run.notes.trim()) {
    notesHtml = `
      <div class="notes-card">
        <div class="notes-header">
          <span>📝 Run Notes (NOTES.md)</span>
          <button class="btn btn-sm" onclick="copyText(${JSON.stringify(run.notes)}, 'Notes copied')">Copy Notes</button>
        </div>
        <div class="notes-body">${escapeHtml(run.notes)}</div>
      </div>
    `;
  }

  // Tags
  const cfg = run.config || {};
  let tags = [];
  if (cfg.model) tags.push(`<span class="tag-item">Model: <strong>${escapeHtml(cfg.model)}${cfg.model_effort ? ' (' + cfg.model_effort + ')' : ''}</strong></span>`);
  if (cfg.harness) tags.push(`<span class="tag-item">Harness: <strong>${escapeHtml(cfg.harness)}</strong></span>`);
  if (cfg.num_instances) tags.push(`<span class="tag-item">Instances: <strong>${cfg.num_instances}</strong></span>`);
  if (cfg.max_reprompts !== undefined && cfg.max_reprompts !== null) tags.push(`<span class="tag-item">Max Reprompts: <strong>${cfg.max_reprompts}</strong></span>`);
  if (cfg.internet_enabled) tags.push(`<span class="tag-item">Internet: <strong>Enabled</strong></span>`);
  if (cfg.time_limit) tags.push(`<span class="tag-item">Timeout: <strong>${formatDuration(cfg.time_limit)}</strong></span>`);

  // Challenges HTML
  let challengesHtml = '';
  for (const ch of run.challenges) {
    const chScore = ch.score || 0.0;
    let chScoreClass = chScore >= 0.99 ? 'pill-completed' : (chScore > 0 ? 'pill-partial' : 'pill-failed');

    // Trace Link
    let traceHtml = '';
    if (ch.trace_url) {
      traceHtml = `
        <div class="trace-banner">
          <span class="trace-session-text">Session: <strong>${escapeHtml(ch.session_id || '')}</strong></span>
          <a href="${escapeHtml(ch.trace_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
              <polyline points="15 3 21 3 21 9"></polyline>
              <line x1="10" y1="14" x2="21" y2="3"></line>
            </svg>
            Open Trace in kexploit-agent ↗
          </a>
        </div>
      `;
    }

    // Attempts HTML
    let attemptsHtml = '';
    if (ch.attempts && ch.attempts.length > 0) {
      attemptsHtml = `
        <div class="attempts-section">
          <div class="attempt-tabs" id="tabs-${ch.name}">
            ${ch.attempts.map((att, idx) => `
              <button class="tab-btn ${idx === ch.attempts.length - 1 ? 'active' : ''}" onclick="switchAttemptTab('${ch.name}', ${att.attempt})">
                Attempt ${att.attempt}${idx === ch.attempts.length - 1 ? ' (Latest)' : ''}
              </button>
            `).join('')}
          </div>
          ${ch.attempts.map((att, idx) => renderAttemptView(ch.name, att, idx === ch.attempts.length - 1)).join('')}
        </div>
      `;
    }

    challengesHtml += `
      <div class="challenge-card" id="card-${ch.name}">
        <div class="challenge-header" onclick="toggleChallengeBody('${ch.name}')">
          <div class="challenge-info">
            <span class="challenge-name">${escapeHtml(ch.name)}</span>
            ${ch.package ? `<span class="challenge-pkg">${escapeHtml(ch.package)}</span>` : ''}
            <span class="pill pill-${ch.status} pill-sm">${ch.status}</span>
          </div>
          <div class="challenge-right">
            <span class="pill pill-score ${chScoreClass}">Score: ${chScore.toFixed(3)}</span>
            <span style="color:var(--text-dim);font-size:11px;">${formatDuration(ch.runtime)}</span>
            <span class="btn btn-sm" style="padding:2px 8px;font-size:11px;">Details ▾</span>
          </div>
        </div>
        <div class="challenge-body" id="body-${ch.name}">
          ${traceHtml}
          ${attemptsHtml}
        </div>
      </div>
    `;
  }

  content.innerHTML = `
    <!-- Run Header Card -->
    <div class="run-header-card">
      <div class="run-header-top">
        <div class="run-title-group">
          <h1 class="run-title">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
            </svg>
            ${escapeHtml(run.display_name)}
          </h1>
          <div class="run-meta-row">
            <span>Started: <strong>${escapeHtml(run.started_at)}</strong></span>
            <span>Total Runtime: <strong>${formatDuration(run.total_runtime)}</strong></span>
            <span>Path: <code style="font-size:11px;color:var(--accent);">${escapeHtml(run.full_path)}</code></span>
          </div>
        </div>
        <div class="run-header-actions">
          <span class="pill pill-score ${scoreClass}" style="font-size:14px;padding:4px 10px;">
            Score: ${scoreNum.toFixed(4)} (${scorePct}%)
          </span>
          <button class="btn" onclick="copyText(${JSON.stringify(run.full_path)}, 'Results path copied')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            Copy Results Path
          </button>
        </div>
      </div>

      ${tags.length > 0 ? `<div class="run-tags">${tags.join('')}</div>` : ''}
    </div>

    <!-- Notes Section -->
    ${notesHtml}

    <!-- Challenges Section -->
    <div style="display:flex;flex-direction:column;gap:12px;">
      <h2 class="section-title">
        <span>Challenges (${run.challenges.length})</span>
      </h2>
      <div class="challenges-container">
        ${challengesHtml || '<div style="padding:20px;color:var(--text-muted);text-align:center;">No challenges found in this run.</div>'}
      </div>
    </div>
  `;
}

function renderAttemptView(chName, att, isActive) {
  // Axes Table
  let rowsHtml = '';
  for (const [capName, cap] of Object.entries(att.capabilities || {})) {
    const isPassed = cap.passed;
    const resultBadge = isPassed
      ? `<span class="pill pill-completed pill-sm">PASSED</span>`
      : `<span class="pill pill-failed pill-sm">FAILED</span>`;

    // Local app
    let localAppHtml = '<span style="color:var(--text-dim);">-</span>';
    if (cap.attempted) {
      if (cap.declared_local_app !== null && cap.requires_local_app !== null && cap.declared_local_app !== cap.requires_local_app) {
        localAppHtml = `<span class="tag-alert" title="Declared: ${cap.declared_local_app ? 'Yes' : 'No'}, Required: ${cap.requires_local_app ? 'Yes' : 'No'}">⚠️ Mismatch</span>`;
      } else if (cap.requires_local_app) {
        localAppHtml = `<span class="tag-warn">Required</span>`;
      } else {
        localAppHtml = `<span class="tag-clean">No</span>`;
      }
    }

    // 0-Click vs 1-Click
    let clickHtml = '<span style="color:var(--text-dim);">-</span>';
    if (cap.attempted) {
      if (cap.declared_user_interaction !== null && cap.requires_user_interaction !== null && cap.declared_user_interaction !== cap.requires_user_interaction) {
        clickHtml = `<span class="tag-alert" title="Declared: ${cap.declared_user_interaction ? '1-Click' : '0-Click'}, Required: ${cap.requires_user_interaction ? '1-Click' : '0-Click'}">⚠️ Mismatch</span>`;
      } else if (cap.requires_user_interaction) {
        clickHtml = `<span class="tag-warn">1-Click</span>`;
      } else {
        clickHtml = `<span class="tag-clean">0-Click</span>`;
      }
    }

    // Cheating
    let cheatingHtml = '<span style="color:var(--text-dim);">-</span>';
    if (cap.attempted) {
      if (cap.cheating === true) {
        cheatingHtml = `<span class="pill pill-failed pill-sm">⚠️ Cheating</span>`;
      } else if (cap.cheating === false) {
        cheatingHtml = `<span class="tag-clean">No</span>`;
      }
    }

    let capScoreClass = 'pill-failed';
    if (cap.score > 0) {
      capScoreClass = (cap.weight > 0 && cap.score >= cap.weight * 0.99) ? 'pill-completed' : 'pill-partial';
    } else {
      capScoreClass = 'pill-failed';
    }

    const scorePill = `<span class="pill pill-score ${capScoreClass} pill-sm">${cap.score.toFixed(2)} / ${cap.weight.toFixed(2)}</span>`;

    rowsHtml += `
      <tr>
        <td>
          <div style="font-weight:600;font-size:12.5px;color:var(--text);">${escapeHtml(capName)}</div>
          <div style="font-size:11px;color:var(--text-muted);">${escapeHtml(cap.detail || '')}</div>
        </td>
        <td>${resultBadge}${cap.exit_code !== null ? ` <span style="font-size:10.5px;color:var(--text-dim);">(exit ${cap.exit_code})</span>` : ''}</td>
        <td>${scorePill}</td>
        <td>${localAppHtml}</td>
        <td>${clickHtml}</td>
        <td>${cheatingHtml}</td>
        <td>
          ${cap.reasoning ? `<div style="font-size:11px;color:var(--text-muted);max-width:320px;white-space:normal;overflow-wrap:anywhere;">${escapeHtml(cap.reasoning.substring(0, 180))}${cap.reasoning.length > 180 ? '...' : ''}</div>` : '<span style="color:var(--text-dim);">-</span>'}
        </td>
      </tr>
    `;
  }

  const axesTableHtml = `
    <div style="overflow-x:auto;">
      <table class="axes-table">
        <thead>
          <tr>
            <th>Axis / Capability</th>
            <th>Result</th>
            <th>Score</th>
            <th>Local App</th>
            <th>0 vs 1-Click</th>
            <th>Cheating</th>
            <th>Reasoning / Detail</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHtml || '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:14px;">No capabilities evaluated</td></tr>'}
        </tbody>
      </table>
    </div>
  `;

  // PoC Outputs
  let outputsHtml = '';
  for (const [capName, cap] of Object.entries(att.capabilities || {})) {
    if (cap.stdout || cap.stderr || cap.logcat) {
      outputsHtml += `
        <div class="collapse-box" style="margin-top:8px;">
          <div class="collapse-header" onclick="toggleCollapse(this)">
            <span>PoC Logs: <strong>${escapeHtml(capName)}</strong> (Exit code: ${cap.exit_code !== null ? cap.exit_code : 'N/A'})</span>
            <span style="font-size:11px;color:var(--text-muted);">Toggle ▾</span>
          </div>
          <div class="collapse-body hidden">
${cap.stdout ? `=== STDOUT ===\n${escapeHtml(cap.stdout)}\n` : ''}${cap.stderr ? `=== STDERR ===\n${escapeHtml(cap.stderr)}\n` : ''}${cap.logcat ? `=== LOGCAT ===\n${escapeHtml(cap.logcat)}` : ''}
          </div>
        </div>
      `;
    }
  }

  return `
    <div class="attempt-view" id="att-view-${chName}-${att.attempt}" style="${isActive ? '' : 'display:none;'}">
      <!-- Axes Table -->
      ${axesTableHtml}

      <!-- Agent Response -->
      ${att.response ? `
        <div class="collapse-box">
          <div class="collapse-header" onclick="toggleCollapse(this)">
            <span>Agent Final Response (${att.response.split('\n').length} lines)</span>
            <span style="font-size:11px;color:var(--text-muted);">Toggle ▾</span>
          </div>
          <div class="collapse-body hidden">${escapeHtml(att.response)}</div>
        </div>
      ` : ''}

      <!-- Grader Reprompt -->
      ${att.reprompt ? `
        <div class="collapse-box reprompt-alert">
          <div class="collapse-header" onclick="toggleCollapse(this)">
            <span>⚠️ Grader Feedback / Reprompt</span>
            <span style="font-size:11px;">Toggle ▾</span>
          </div>
          <div class="collapse-body hidden">${escapeHtml(att.reprompt)}</div>
        </div>
      ` : ''}

      <!-- Outputs -->
      ${outputsHtml}
    </div>
  `;
}

function switchAttemptTab(chName, attemptNum) {
  const tabsContainer = document.getElementById(`tabs-${chName}`);
  if (tabsContainer) {
    tabsContainer.querySelectorAll('.tab-btn').forEach((btn, idx) => {
      btn.classList.toggle('active', btn.textContent.includes(`Attempt ${attemptNum}`));
    });
  }
  const views = document.querySelectorAll(`[id^="att-view-${chName}-"]`);
  views.forEach(v => {
    v.style.display = v.id === `att-view-${chName}-${attemptNum}` ? 'flex' : 'none';
  });
}

function toggleChallengeBody(chName) {
  const body = document.getElementById(`body-${chName}`);
  if (body) {
    body.classList.toggle('hidden');
  }
}

function toggleCollapse(headerEl) {
  const body = headerEl.nextElementSibling;
  if (body) {
    body.classList.toggle('hidden');
  }
}

function copyText(text, message) {
  navigator.clipboard.writeText(text).then(() => {
    showToast(message || 'Copied to clipboard');
  }).catch(() => {
    // Fallback
    const input = document.createElement('textarea');
    input.value = text;
    document.body.appendChild(input);
    input.select();
    document.execCommand('copy');
    document.body.removeChild(input);
    showToast(message || 'Copied to clipboard');
  });
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 2200);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
</script>
</body>
</html>
"""
