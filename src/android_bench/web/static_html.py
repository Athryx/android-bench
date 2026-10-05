from __future__ import annotations

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>android-bench Results Viewer</title>
<script src="/static/marked.min.js"></script>
<script src="/static/purify.min.js"></script>
<style>
/* Match kexploit_agent/events/web_viewer/static_html.py. */
:root {
  color-scheme: dark;
  --bg: #101419;
  --panel: #171c23;
  --panel-hover: #202832;
  --panel-active: #1a222b;
  --card: #141a21;
  --code-bg: #0c1015;
  --border: #2a333e;
  --border-subtle: #232c36;
  --text: #e1e7ed;
  --text-muted: #94a2b2;
  --text-dim: #8897a7;
  --accent: #85c9ba;
  --accent-muted: #1b2b29;
  --accent-border: #43665d;
  --link: #9acbff;
  --green: #a5dfb5;
  --green-bg: #183225;
  --red: #e9a09a;
  --red-bg: #392024;
  --yellow: #e6bd86;
  --yellow-bg: #30281e;
  --blue: #a8c7ff;
  --blue-bg: #1b2430;
  --font-mono: ui-monospace, SFMono-Regular, Consolas, monospace;
  --font-sans: system-ui, sans-serif;
}

* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; background: var(--bg); color: var(--text); font: 14px/1.6 var(--font-sans); overflow: hidden; }
button, input, select, textarea { font: inherit; color: inherit; }
button { cursor: pointer; }
a { color: var(--link); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
:disabled { opacity: .5; cursor: not-allowed; }
[hidden] { display: none !important; }

/* Threads-style sidebar and toolbar. */
.app-container { display: flex; height: 100dvh; width: 100%; overflow: hidden; }
.sidebar { width: 275px; flex: none; min-width: 0; min-height: 0; background: var(--panel); border-right: 1px solid var(--border); display: flex; flex-direction: column; }
.sidebar-header { padding: 18px 14px 10px; display: flex; flex-direction: column; gap: 12px; }
.app-brand { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.brand-title { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.brand-title svg { color: var(--accent); }
.brand-badge { color: var(--text-muted); font-size: 12px; }
.sidebar-search-row { display: flex; align-items: center; gap: 6px; }
.search-input { width: 100%; min-width: 0; flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; font-size: 13px; }
.search-input::placeholder { color: var(--text-muted); }
.btn-icon { display: inline-flex; align-items: center; justify-content: center; flex: none; background: transparent; border: 1px solid var(--border); border-radius: 6px; padding: 8px; color: var(--text-muted); }
.btn-icon:hover { background: #242d36; color: var(--text); border-color: #465361; }
.tree-container { flex: 1; min-height: 0; overflow: auto; padding: 0 8px 12px; }
.tree-node { margin: 2px 0; }
.tree-folder-row { display: flex; align-items: center; gap: 6px; padding: 6px; border-radius: 5px; cursor: pointer; color: var(--text-muted); font-size: 12px; }
.tree-folder-row:hover { background: var(--panel-hover); color: var(--text); }
.tree-chevron { display: inline-flex; align-items: center; justify-content: center; width: 14px; height: 14px; flex: none; color: var(--text-muted); transition: transform .14s ease; }
.tree-chevron.expanded { transform: rotate(90deg); }
.tree-folder-children { padding-left: 10px; border-left: 1px solid var(--border); margin-left: 7px; }
.tree-folder-children.hidden { display: none; }
.tree-run-item { display: flex; flex-direction: column; gap: 4px; padding: 10px; margin: 2px 0; border-radius: 5px; border-left: 2px solid transparent; cursor: pointer; }
.tree-run-item:hover { background: #242d36; }
.tree-run-item.active { background: #23322f; border-left-color: var(--accent); }
.run-item-top, .run-item-meta, .run-item-badges { display: flex; align-items: center; gap: 6px; }
.run-item-top, .run-item-meta { justify-content: space-between; }
.run-item-title { min-width: 0; flex: 1; font-size: 13px; font-weight: 550; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.run-item-badges { flex: none; }
.run-item-meta { color: var(--text-muted); font-size: 11px; }
.main-view { display: flex; flex: 1; flex-direction: column; min-width: 0; min-height: 0; }
.viewer-toolbar { display: flex; flex: none; flex-wrap: wrap; align-items: center; gap: 12px; padding: 10px 24px; border-bottom: 1px solid var(--border); }
.sidebar-toggle { width: 32px; height: 32px; padding: 0; font-size: 19px; line-height: 1; }
.toolbar-heading { display: flex; flex: 1; align-items: center; gap: 8px; min-width: 0; }
.toolbar-title { font-weight: 600; overflow-wrap: anywhere; min-width: 0; }
.toolbar-status:empty { display: none; }
.toolbar-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.main-scroll { flex: 1; min-height: 0; min-width: 0; overflow: auto; }
.empty-view { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100%; color: var(--text-muted); gap: 12px; padding: 50px 16px; text-align: center; }
.empty-view svg { width: 40px; height: 40px; stroke: var(--text-muted); }
.run-content { display: flex; flex-direction: column; gap: 28px; width: 100%; max-width: 1000px; padding: 26px 40px 80px; margin: 0 auto; }

/* Overview, facts, and quiet outlined controls. */
.run-header-card { border-bottom: 1px solid var(--border); padding-bottom: 24px; display: flex; flex-direction: column; gap: 16px; }
.run-header-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.run-title-group { display: flex; flex-direction: column; gap: 6px; min-width: 0; flex: 1; }
.eyebrow { color: var(--accent); font-size: 11px; text-transform: uppercase; letter-spacing: .12em; }
.run-title { font-size: 26px; font-weight: 600; line-height: 1.4; margin: 0 0 2px; overflow-wrap: anywhere; }
.run-meta-row { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px 20px; color: var(--text-muted); font-size: 13px; overflow-wrap: anywhere; }
.run-meta-row strong { font-weight: 550; }
.run-meta-row code { white-space: normal; overflow-wrap: anywhere; }
.run-header-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; background: transparent; border: 1px solid var(--border); border-radius: 6px; padding: 5px 12px; font-size: 12px; font-weight: 400; color: var(--text); text-decoration: none; }
.btn:hover { background: #242d36; }
.btn-primary { color: var(--accent); border-color: var(--accent-border); }
.btn-primary:hover { background: var(--accent-muted); }
.run-tags { display: flex; flex-wrap: wrap; gap: 6px 20px; }
.tag-item { display: inline-flex; align-items: baseline; gap: 5px; font-size: 13px; color: var(--text-muted); overflow-wrap: anywhere; }
.tag-item strong { color: var(--text); font-weight: 550; }
.pill { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 400; padding: 1px 7px; border: 1px solid var(--border); border-radius: 4px; line-height: 1.6; white-space: nowrap; }
.pill-sm { font-size: 10px; padding: 1px 5px; }
.pill-completed { color: var(--blue); background: var(--blue-bg); border-color: #46607a; }
.pill-passed { color: var(--green); background: var(--green-bg); border-color: #3d6048; }
.pill-running { color: var(--accent); background: var(--accent-muted); border-color: var(--accent-border); }
.pill-failed { color: var(--red); background: var(--red-bg); border-color: #80504d; }
.pill-warn, .pill-partial { color: var(--yellow); background: var(--yellow-bg); border-color: #7c5b3b; }
.pill-pending, .pill-unattempted { color: var(--text-muted); background: transparent; }
.unattempted-score { background: transparent !important; color: var(--text-dim) !important; border-color: var(--border) !important; }
.pill-score { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.pill-cost { color: var(--accent); border-color: var(--accent-border); background: var(--accent-muted); font-family: var(--font-mono); }

/* Summary-style notes and prose. */
.notes-card { background: #14211f; border-left: 3px solid var(--accent); border-radius: 7px; padding: 18px 22px; }
.notes-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; color: var(--accent); font-size: 18px; font-weight: 600; }
.notes-body { font-size: 14px; line-height: 1.6; overflow-wrap: anywhere; }
.notes-body > :first-child { margin-top: 0; }
.notes-body > :last-child { margin-bottom: 0; }
.notes-body h1, .notes-body h2, .notes-body h3, .notes-body h4 { margin: 20px 0 8px; font-weight: 600; line-height: 1.4; }
.notes-body h1 { font-size: 22px; }
.notes-body h2 { font-size: 18px; }
.notes-body h3 { font-size: 16px; }
.notes-body h4 { font-size: 14px; }
.notes-body p { margin: 8px 0 14px; }
.notes-body ul, .notes-body ol { padding-left: 24px; }
.notes-body li { margin: 4px 0; }
code, pre { font-family: var(--font-mono); font-size: 12px; }
code { background: #242c35; border-radius: 3px; padding: 2px 4px; }
.notes-body pre { background: var(--code-bg); padding: 14px; overflow: auto; max-height: 440px; line-height: 1.6; border-radius: 5px; white-space: pre-wrap; overflow-wrap: anywhere; }
.notes-body pre code { background: none; padding: 0; }
.notes-body blockquote { border-left: 2px solid var(--border); color: var(--text-muted); margin: 12px 0; padding-left: 16px; }
.notes-body table { border-collapse: collapse; width: 100%; font-size: 12px; display: block; overflow: auto; }
.notes-body td, .notes-body th { text-align: left; border-bottom: 1px solid var(--border); padding: 8px; }
.notes-body a { color: var(--link); }
.notes-body img { max-width: 100%; height: auto; }
.notes-body hr { border: 0; border-top: 1px solid var(--border); margin: 20px 0; }

/* Tables and event-style challenge disclosures. */
.section-title { display: flex; align-items: center; justify-content: space-between; margin: 0; font-size: 13px; font-weight: 600; }
.overview-table-card { min-width: 0; }
.overview-table-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; padding: 5px 0 14px; border-top: 1px solid #3a4653; }
.main-overview-table, .axes-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.main-overview-table th, .axes-table th { color: var(--text-muted); font-size: 11px; font-weight: 600; text-align: left; text-transform: uppercase; letter-spacing: .5px; }
.main-overview-table td, .main-overview-table th, .axes-table td, .axes-table th { padding: 8px; border-bottom: 1px solid var(--border); vertical-align: middle; }
.main-overview-table th { white-space: nowrap; }
.main-overview-table .th-sub { color: var(--text-dim); font-size: 10px; text-transform: none; letter-spacing: 0; font-weight: 400; margin-top: 2px; }
.main-overview-table tbody tr:hover, .axes-table tbody tr:hover { background: var(--panel-active); }
.challenges-section { display: flex; flex-direction: column; gap: 14px; }
.challenges-section > .section-title { border-top: 1px solid #3a4653; padding-top: 5px; }
.challenges-container { display: flex; flex-direction: column; gap: 10px; }
.challenge-card, .collapse-box { border: 1px solid var(--border); border-left: 2px solid #465b70; border-radius: 7px; background: var(--card); overflow: hidden; }
.challenge-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 9px 12px; cursor: pointer; }
.challenge-header:hover, .collapse-header:hover { background: var(--panel-hover); }
.challenge-card.expanded > .challenge-header, .collapse-box.expanded > .collapse-header { background: var(--panel-active); }
.challenge-info { display: flex; flex: 1; flex-wrap: wrap; align-items: center; gap: 8px; min-width: 0; }
.challenge-name { font-size: 13px; font-weight: 600; overflow-wrap: anywhere; }
.challenge-pkg { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); overflow-wrap: anywhere; }
.challenge-right { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.collapse-arrow { flex: none; color: #6f8192; font-size: 18px; line-height: 1; width: 14px; text-align: center; }
.challenge-header:hover .collapse-arrow { color: var(--accent); }
.challenge-body { display: flex; flex-direction: column; gap: 18px; border-top: 1px solid var(--border); padding: 12px 16px 16px; }
.challenge-body.hidden, .collapse-body.hidden { display: none; }
.tag-clean, .tag-warn { display: inline-flex; align-items: center; gap: 3px; font-size: 11px; }
.tag-clean { color: var(--green); }
.tag-warn { color: var(--yellow); }
.tag-alert { display: inline-flex; align-items: center; gap: 3px; font-size: 11px; border: 1px solid #80504d; border-radius: 4px; padding: 1px 6px; background: var(--red-bg); color: var(--red); }
.usage-banner { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 24px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 4px; background: var(--blue-bg); }
.usage-item { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.usage-label { color: var(--text-muted); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
.usage-value { font-family: var(--font-mono); font-size: 12px; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.usage-cost { color: var(--accent); }
.trace-banner { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; border-left: 2px solid var(--accent); background: #14211f; padding: 10px 14px; }
.trace-session-text { font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); overflow-wrap: anywhere; }
.attempts-section, .attempt-view { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.attempt-tabs, .preview-tabs { display: flex; gap: 6px; overflow: auto; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.tab-btn { flex: none; background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 5px 12px; color: var(--text-muted); font-size: 12px; }
.tab-btn:hover { background: #1b252b; color: var(--text); }
.tab-btn.active { background: var(--accent-muted); color: var(--accent); font-weight: 600; }
.collapse-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 9px 12px; cursor: pointer; font-size: 12px; }
.collapse-body { max-height: 440px; overflow: auto; padding: 14px 16px; border-top: 1px solid var(--border); background: var(--code-bg); font: 12px/1.6 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; }
.reprompt-alert { border-left-color: #d0aa65; }
.reprompt-alert .collapse-header { color: var(--yellow); }
.caps-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(280px, 100%), 1fr)); gap: 10px; }
.cap-card { display: flex; flex-direction: column; gap: 6px; border: 1px solid var(--border); border-radius: 7px; background: var(--card); padding: 10px 12px; }
.cap-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.cap-name { font-size: 13px; font-weight: 600; }
.cap-detail, .cap-review { color: var(--text-muted); font-size: 11px; }
.cap-review { border-left: 1px solid var(--border); padding: 4px 8px; }

/* Popovers, export, and resume dialogs. */
.toast { position: fixed; bottom: 24px; right: 24px; z-index: 150; max-width: calc(100vw - 32px); padding: 5px 9px; border: 1px solid #465361; border-radius: 5px; background: #26313b; color: var(--text); box-shadow: 0 6px 16px #0008; font-size: 11px; opacity: 0; transform: translateY(10px); transition: opacity .14s ease, transform .14s ease; pointer-events: none; }
.toast.show { opacity: 1; transform: translateY(0); }
.modal-overlay { position: fixed; inset: 0; z-index: 200; background: #101419d9; display: flex; align-items: center; justify-content: center; padding: 12px; }
.modal-overlay.hidden { display: none; }
.modal-card { display: flex; flex-direction: column; background: #19232a; border: 1px solid #3a4653; border-radius: 9px; width: 920px; max-width: 100%; max-height: calc(100dvh - 24px); box-shadow: 0 14px 36px #0009; overflow: hidden; }
.modal-card-resume { width: 980px; }
.modal-header, .modal-footer { display: flex; flex: none; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 16px; }
.modal-header { border-bottom: 1px solid var(--border); }
.modal-footer { border-top: 1px solid var(--border); }
.modal-title-group { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.modal-title { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 15px; font-weight: 600; }
.modal-subtitle { color: var(--text-muted); font-size: 12px; }
.modal-body { display: flex; flex-direction: column; gap: 14px; flex: 1; min-height: 0; overflow: auto; padding: 14px 16px; }
.modal-config-bar, .resume-bulk-bar, .resume-command-card { background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; }
.modal-config-bar, .resume-command-card { display: flex; flex-direction: column; gap: 10px; }
.config-group { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.config-group-label, .resume-command-title { color: var(--text-muted); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }
.config-group-label { min-width: 90px; }
.toggle-chip { display: inline-flex; align-items: center; gap: 4px; background: transparent; border: 1px solid var(--border); border-radius: 4px; padding: 2px 8px; color: var(--text-muted); font-size: 12px; cursor: pointer; }
.toggle-chip:hover { background: #242d36; color: var(--text); }
.toggle-chip.active { background: var(--accent-muted); color: var(--accent); border-color: var(--accent-border); }
.preview-container { display: flex; flex-direction: column; min-height: 200px; }
.markdown-textarea, .markdown-preview-rendered { width: 100%; height: 320px; background: var(--code-bg); color: var(--text); border: 1px solid var(--border); border-radius: 5px; padding: 14px; }
.markdown-textarea { font: 12px/1.6 var(--font-mono); resize: vertical; }
.markdown-preview-rendered { overflow: auto; }
.resume-bulk-bar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; }
.resume-challenges-container { display: flex; flex-direction: column; gap: 6px; max-height: 42dvh; overflow: auto; }
.resume-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--card); padding: 10px 12px; }
.resume-row.disabled { opacity: .5; }
.resume-row-left { display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1; overflow-wrap: anywhere; }
.resume-row-right { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.resume-select, .resume-input { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 4px 8px; font-size: 12px; }
.resume-select { cursor: pointer; }
.resume-input { width: 52px; text-align: center; padding: 4px 6px; }
.resume-input-group { display: flex; align-items: center; gap: 3px; }
.resume-stepper-btn { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: transparent; border: 1px solid var(--border); border-radius: 4px; padding: 0; color: var(--text-muted); }
.resume-stepper-btn:hover:not(:disabled) { background: #242d36; color: var(--text); }
.resume-command-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
.resume-command-textarea { width: 100%; min-height: 60px; max-height: 110px; padding: 8px 10px; color: var(--link); background: var(--code-bg); border: 1px solid var(--border); border-radius: 5px; font: 12px/1.6 var(--font-mono); resize: vertical; white-space: pre-wrap; overflow-wrap: anywhere; }

@media (max-width: 800px) {
  .sidebar { width: 210px; }
  .viewer-toolbar { padding: 10px 20px; }
  .toolbar-actions { width: 100%; }
  .run-content { padding: 22px 20px 60px; }
  .challenge-header { flex-wrap: wrap; }
  .challenge-right { padding-left: 22px; }
}
@media (max-width: 560px) {
  .app-container { flex-direction: column; }
  .sidebar { width: 100%; height: 210px; border-right: 0; border-bottom: 1px solid var(--border); }
  .sidebar-header { padding: 6px 16px; gap: 6px; }
  .search-input { padding: 4px 8px; }
  .btn-icon { padding: 6px; }
  .sidebar-toggle { padding: 0; }
  .viewer-toolbar { padding: 8px 16px; gap: 8px; }
  .toolbar-actions { gap: 6px; }
  .run-content { padding: 18px 16px 50px; gap: 24px; }
  .run-title { font-size: 23px; }
  .notes-card { padding: 16px; }
  .challenge-body { padding: 12px; }
  .modal-header, .modal-body, .modal-footer { padding: 12px; }
  .modal-footer { flex-wrap: wrap; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}
</style>
</head>
<body>

<div class="app-container">
  <!-- Sidebar -->
  <aside class="sidebar" id="runSidebar" aria-label="Benchmark runs">
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
        <input type="search" id="searchInput" class="search-input" placeholder="Find a run…" aria-label="Find a run" oninput="filterTree()">
        <button class="btn-icon" onclick="refreshTree()" title="Refresh runs" aria-label="Refresh runs">
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
    <div class="viewer-toolbar">
      <button class="btn-icon sidebar-toggle" id="sidebarToggle" type="button" onclick="toggleSidebar()" aria-controls="runSidebar" aria-expanded="true" aria-label="Hide runs" title="Hide runs">☰</button>
      <div class="toolbar-heading">
        <span class="toolbar-title" id="toolbarTitle">Select a run</span>
        <span class="pill toolbar-status" id="toolbarStatus" role="status"></span>
      </div>
      <div class="toolbar-actions" id="toolbarActions"></div>
    </div>
    <div class="main-scroll" id="mainScroll">
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
    </div>
  </main>
</div>

<div id="toast" class="toast">Path copied to clipboard</div>

<!-- Markdown Export Modal -->
<div id="exportModal" class="modal-overlay hidden" onclick="handleModalOverlayClick(event)">
  <div class="modal-card" onclick="event.stopPropagation()">
    <div class="modal-header">
      <div class="modal-title-group">
        <h3 class="modal-title">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
          </svg>
          Export Markdown Report
        </h3>
        <span class="modal-subtitle" id="exportModalSubtitle">Customize details to render and copy</span>
      </div>
      <button class="btn-icon" onclick="closeExportModal()" title="Close (Esc)">✕</button>
    </div>
    <div class="modal-body">
      <!-- Dynamic Configuration Controls -->
      <div class="modal-config-bar" id="modalConfigBar"></div>

      <!-- Preview Tabs -->
      <div class="preview-tabs">
        <button id="tabBtnMarkdown" class="tab-btn active" onclick="switchExportTab('markdown')">Raw Markdown</button>
        <button id="tabBtnRendered" class="tab-btn" onclick="switchExportTab('rendered')">Rendered Preview</button>
      </div>

      <!-- Preview Container -->
      <div class="preview-container">
        <textarea id="exportMarkdownSource" class="markdown-textarea" readonly spellcheck="false" placeholder="Generating markdown..."></textarea>
        <div id="exportRenderedPreview" class="markdown-preview-rendered notes-body" style="display:none;"></div>
      </div>
    </div>
    <div class="modal-footer">
      <div style="font-size:11.5px;color:var(--text-dim);" id="exportStatsText"></div>
      <div style="display:flex;gap:8px;">
        <button class="btn" onclick="closeExportModal()">Close</button>
        <button class="btn btn-primary" onclick="copyExportMarkdown()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
          Copy Markdown
        </button>
      </div>
    </div>
  </div>
</div>

<!-- Resume Benchmark Modal -->
<div id="resumeModal" class="modal-overlay hidden" onclick="handleResumeModalOverlayClick(event)">
  <div class="modal-card modal-card-resume" onclick="event.stopPropagation()">
    <div class="modal-header">
      <div class="modal-title-group">
        <h3 class="modal-title">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
          Resume Benchmark
        </h3>
        <span class="modal-subtitle" id="resumeModalSubtitle">Configure attempts and resume modes per challenge</span>
      </div>
      <button class="btn-icon" onclick="closeResumeModal()" title="Close (Esc)">✕</button>
    </div>
    <div class="modal-body">
      <!-- Quick Bulk Action Bar -->
      <div class="resume-bulk-bar" id="resumeBulkBar"></div>

      <!-- Challenge List -->
      <div class="resume-challenges-container" id="resumeChallengesList"></div>

      <!-- Command Output Card -->
      <div class="resume-command-card">
        <div class="resume-command-header">
          <span class="resume-command-title">Generated Resume Command</span>
          <div style="display:flex;gap:6px;align-items:center;">
            <label class="toggle-chip active" id="chipResumeRel" onclick="toggleResumeRelativePath()" title="Toggle between relative and full path">
              <span>Relative Path</span>
            </label>
            <label class="toggle-chip active" id="chipResumeUv" onclick="toggleResumeUvPrefix()" title="Toggle uv run prefix">
              <span>uv run</span>
            </label>
          </div>
        </div>
        <textarea id="resumeCommandText" class="resume-command-textarea" readonly spellcheck="false" onclick="this.select()" placeholder="Generating resume command..."></textarea>
      </div>
    </div>
    <div class="modal-footer">
      <div style="font-size:11.5px;color:var(--text-dim);" id="resumeStatsText"></div>
      <div style="display:flex;gap:8px;">
        <button class="btn" onclick="closeResumeModal()">Close</button>
        <button class="btn btn-primary" id="btnCopyResumeCommand" onclick="copyResumeCommand()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
          Copy Command
        </button>
      </div>
    </div>
  </div>
</div>

<script>
const STANDARD_CAPABILITIES = ['code_execution', 'file_write', 'file_read', 'intent', 'aslr_leak'];
const CAPABILITY_META = {
  'code_execution': { title: 'Code Exec', weight: 1.0 },
  'file_write': { title: 'File Write', weight: 0.30 },
  'file_read': { title: 'File Read', weight: 0.25 },
  'intent': { title: 'Intent', weight: 0.20 },
  'aslr_leak': { title: 'ASLR Leak', weight: 0.15 },
};

let currentTree = [];
let selectedRunPath = null;
let currentRunDetail = null;

function toggleSidebar() {
  const sidebar = document.getElementById('runSidebar');
  const button = document.getElementById('sidebarToggle');
  sidebar.hidden = !sidebar.hidden;
  button.setAttribute('aria-expanded', String(!sidebar.hidden));
  const label = sidebar.hidden ? 'Show runs' : 'Hide runs';
  button.setAttribute('aria-label', label);
  button.title = label;
}

// On load
function getRunPathFromUrl() {
  const pathname = window.location.pathname;
  if (pathname.startsWith('/runs/')) {
    const sub = pathname.slice(6);
    if (sub) return decodeURIComponent(sub);
  }
  const params = new URLSearchParams(window.location.search);
  const qRun = params.get('run');
  if (qRun) return decodeURIComponent(qRun);

  if (window.location.hash) {
    let hash = window.location.hash.slice(1);
    if (hash.startsWith('/runs/')) hash = hash.slice(6);
    else if (hash.startsWith('/')) hash = hash.slice(1);
    if (hash) return decodeURIComponent(hash);
  }
  return null;
}

// On load
window.addEventListener('DOMContentLoaded', () => {
  refreshTree();
});

// Browser back/forward navigation
window.addEventListener('popstate', (event) => {
  const path = (event.state && event.state.runPath) || getRunPathFromUrl();
  if (path) {
    loadRun(path, 'none');
  } else {
    selectedRunPath = null;
    document.getElementById('emptyView').style.display = 'flex';
    document.getElementById('runContent').style.display = 'none';
    document.querySelectorAll('.tree-run-item').forEach(item => item.classList.remove('active'));
    document.getElementById('toolbarTitle').textContent = 'Select a run';
    document.getElementById('toolbarStatus').textContent = '';
    document.getElementById('toolbarActions').replaceChildren();
    document.title = 'android-bench Results Viewer';
  }
});

async function refreshTree() {
  try {
    const res = await fetch('/api/tree');
    const data = await res.json();
    currentTree = data.items || [];
    renderTree(currentTree);

    const urlRunPath = getRunPathFromUrl();
    if (urlRunPath) {
      loadRun(urlRunPath, 'none');
    } else if (selectedRunPath) {
      loadRun(selectedRunPath, 'none');
    } else if (currentTree.length > 0) {
      // Auto-select first run if on root, using replaceState to avoid history trap
      const firstRun = findFirstRun(currentTree);
      if (firstRun) {
        loadRun(firstRun.path, 'replace');
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
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--text-muted);">
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
        loadRun(node.path, 'push');
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

async function loadRun(path, historyMode = 'push') {
  selectedRunPath = path;

  // Update browser URL
  const targetUrl = `/runs/${encodeURI(path)}`;
  if (historyMode === 'push') {
    if (window.location.pathname !== targetUrl) {
      history.pushState({ runPath: path }, '', targetUrl);
    }
  } else if (historyMode === 'replace') {
    history.replaceState({ runPath: path }, '', targetUrl);
  }

  // Update active state in sidebar and expand parent folders
  document.querySelectorAll('.tree-run-item').forEach(item => {
    const isActive = item.dataset.path === path;
    item.classList.toggle('active', isActive);
    if (isActive) {
      let parent = item.closest('.tree-folder-children');
      while (parent) {
        parent.classList.remove('hidden');
        const parentRow = parent.previousElementSibling;
        if (parentRow) {
          const chev = parentRow.querySelector('.tree-chevron');
          if (chev) chev.classList.add('expanded');
        }
        parent = parent.parentElement ? parent.parentElement.closest('.tree-folder-children') : null;
      }
      item.scrollIntoView({ block: 'nearest' });
    }
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

function parseTokenUsage(tu) {
  if (!tu || typeof tu !== 'object') return null;
  const input = Number(tu.input_tokens || tu.input || 0);
  const output = Number(tu.output_tokens || tu.output || 0);
  const cacheRead = Number(tu.cache_read_tokens || tu.cache_read || 0);
  const cacheWrite = Number(tu.cache_write_tokens || tu.cache_write || 0);
  const reasoning = Number(tu.reasoning_tokens || tu.reasoning || 0);
  const total = Number(tu.total_tokens || (input + output));
  const model = tu.model || '';
  return {
    input,
    output,
    cacheRead,
    cacheWrite,
    reasoning,
    total,
    model,
    hasTokens: (input + output + cacheRead + cacheWrite + reasoning) > 0,
  };
}

function renderUsageBanner(costUsd, tokenUsage, title) {
  const tu = parseTokenUsage(tokenUsage);
  const hasCost = costUsd !== null && costUsd !== undefined;
  const hasTokens = tu && tu.hasTokens;

  if (!hasCost && !hasTokens) return '';

  return `
    <div class="usage-banner">
      ${hasCost ? `
        <div class="usage-item">
          <span class="usage-label">${title ? 'Total Cost' : 'Cost'}</span>
          <span class="usage-value usage-cost">$${Number(costUsd).toFixed(4)}</span>
        </div>
      ` : ''}
      ${tu && tu.total > 0 ? `
        <div class="usage-item">
          <span class="usage-label">Total Tokens</span>
          <span class="usage-value">${tu.total.toLocaleString()}</span>
        </div>
      ` : ''}
      ${tu && tu.input > 0 ? `
        <div class="usage-item">
          <span class="usage-label">Input Tokens</span>
          <span class="usage-value">${tu.input.toLocaleString()}</span>
        </div>
      ` : ''}
      ${tu && tu.output > 0 ? `
        <div class="usage-item">
          <span class="usage-label">Output Tokens</span>
          <span class="usage-value">${tu.output.toLocaleString()}</span>
        </div>
      ` : ''}
      ${tu && tu.cacheRead > 0 ? `
        <div class="usage-item">
          <span class="usage-label">Cache Read</span>
          <span class="usage-value">${tu.cacheRead.toLocaleString()}</span>
        </div>
      ` : ''}
      ${tu && tu.cacheWrite > 0 ? `
        <div class="usage-item">
          <span class="usage-label">Cache Write</span>
          <span class="usage-value">${tu.cacheWrite.toLocaleString()}</span>
        </div>
      ` : ''}
      ${tu && tu.reasoning > 0 ? `
        <div class="usage-item">
          <span class="usage-label">Reasoning</span>
          <span class="usage-value">${tu.reasoning.toLocaleString()}</span>
        </div>
      ` : ''}
      ${tu && tu.model ? `
        <div class="usage-item">
          <span class="usage-label">Model</span>
          <span class="usage-value" style="font-family:var(--font-mono);font-size:11.5px;color:var(--text-muted);">${escapeHtml(tu.model)}</span>
        </div>
      ` : ''}
    </div>
  `;
}

function renderRunDetail(run) {
  document.getElementById('emptyView').style.display = 'none';
  const content = document.getElementById('runContent');
  content.style.display = 'flex';
  document.title = `${run.display_name || run.folder_name} - android-bench Results`;
  document.getElementById('toolbarTitle').textContent = run.display_name || run.folder_name;
  const status = document.getElementById('toolbarStatus');
  status.textContent = run.status || 'pending';
  status.className = `pill toolbar-status pill-${run.status || 'pending'}`;

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
          <span>Run notes</span>
          <button class="btn btn-sm" onclick="copyText(currentRunDetail.notes, 'Notes copied')">Copy Raw Notes</button>
        </div>
        <div class="notes-body">${renderMarkdown(run.notes)}</div>
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

  // Overview Table
  const hasStandard = (run.challenges || []).some(ch => {
    const chCaps = [
      ...(ch.enabled_capabilities || []),
      ...Object.keys(ch.axes || {}),
    ];
    return chCaps.some(c => STANDARD_CAPABILITIES.includes(c));
  });

  const tableCaps = [];
  if (hasStandard || !run.challenges || run.challenges.length === 0) {
    tableCaps.push(...STANDARD_CAPABILITIES);
  }

  // Include any extra non-standard capabilities
  for (const ch of (run.challenges || [])) {
    const chCaps = [
      ...(ch.enabled_capabilities || []),
      ...Object.keys(ch.axes || {}),
      ...(ch.attempts || []).flatMap(att => Object.keys(att.capabilities || {}))
    ];
    for (const c of chCaps) {
      if (!tableCaps.includes(c)) {
        tableCaps.push(c);
      }
    }
  }

  let overviewRowsHtml = '';
  if (!run.challenges || run.challenges.length === 0) {
    overviewRowsHtml = `
      <tr>
        <td colspan="${tableCaps.length + 3}" style="text-align:center;padding:24px;color:var(--text-muted);">
          No challenges found in this run.
        </td>
      </tr>
    `;
  } else {
    for (const ch of run.challenges) {
      const chScore = ch.score || 0.0;
      let chScoreClass = chScore >= 0.99 ? 'pill-completed' : (chScore > 0 ? 'pill-partial' : 'pill-failed');

      const latestAtt = (ch.attempts && ch.attempts.length > 0) ? ch.attempts[ch.attempts.length - 1] : null;

      const isConfiguredCap = (capName) => {
        if (Array.isArray(ch.enabled_capabilities) && ch.enabled_capabilities.length > 0) {
          return ch.enabled_capabilities.includes(capName);
        }
        if (ch.axes && capName in ch.axes) return true;
        if (latestAtt && latestAtt.capabilities && capName in latestAtt.capabilities) return true;
        return false;
      };

      let cellsHtml = '';
      for (const capName of tableCaps) {
        if (!isConfiguredCap(capName)) {
          cellsHtml += `<td style="text-align:center;color:var(--text-dim);font-weight:500;">-</td>`;
          continue;
        }

        const capDetail = (latestAtt && latestAtt.capabilities) ? latestAtt.capabilities[capName] : null;
        const isAttempted = capDetail ? (capDetail.attempted !== false) : (ch.axes && (ch.axes[capName] !== undefined && ch.axes[capName] > 0));

        if (!isAttempted) {
          cellsHtml += `
            <td style="text-align:center;">
              <span class="pill pill-unattempted pill-sm">UNATTEMPTED</span>
            </td>
          `;
        } else {
          const capScore = capDetail ? capDetail.score : ((ch.axes && ch.axes[capName] !== undefined) ? ch.axes[capName] : 0.0);
          const meta = CAPABILITY_META[capName];
          const capWeight = (capDetail && capDetail.weight > 0) ? capDetail.weight : (meta ? meta.weight : 0.0);

          let capClass = 'pill-failed';
          if (capScore > 0) {
            capClass = (capWeight > 0 && capScore >= capWeight * 0.99) ? 'pill-completed' : 'pill-partial';
          }
          cellsHtml += `
            <td style="text-align:center;">
              <span class="pill pill-score ${capClass} pill-sm">${capScore.toFixed(2)}${capWeight > 0 ? ` / ${capWeight.toFixed(2)}` : ''}</span>
            </td>
          `;
        }
      }

      overviewRowsHtml += `
        <tr data-challenge="${escapeHtml(ch.name)}" onclick="jumpToChallenge(this.dataset.challenge)" style="cursor:pointer;" title="Click to view details for ${escapeHtml(ch.name)}">
          <td>
            <div style="font-weight:600;font-size:13px;color:var(--text);display:flex;align-items:center;gap:8px;">
              <span>${escapeHtml(ch.name)}</span>
              <span class="pill pill-${ch.status} pill-sm">${ch.status}</span>
            </div>
            ${ch.package ? `<div style="font-size:11px;color:var(--text-muted);font-family:var(--font-mono);">${escapeHtml(ch.package)}</div>` : ''}
          </td>
          <td style="text-align:center;">
            <span class="pill pill-score ${chScoreClass} pill-sm">${chScore.toFixed(3)}</span>
            <div style="font-size:10.5px;color:var(--text-dim);margin-top:2px;">${formatDuration(ch.runtime)}</div>
          </td>
          <td style="text-align:center;">
            ${ch.cost_usd != null ? `<span class="pill pill-cost pill-sm">$${ch.cost_usd.toFixed(4)}</span>` : '<span style="color:var(--text-dim);font-size:12px;">-</span>'}
          </td>
          ${cellsHtml}
          <td style="text-align:right;">
            <button class="btn btn-sm" data-challenge="${escapeHtml(ch.name)}" onclick="event.stopPropagation(); jumpToChallenge(this.dataset.challenge)" style="padding:2px 8px;font-size:11px;">
              View ▾
            </button>
          </td>
        </tr>
      `;
    }
  }

  const overviewTableHtml = `
    <div class="overview-table-card">
      <div class="overview-table-header">
        <h2 class="section-title">
          <span>Challenges Overview (${(run.challenges || []).length})</span>
        </h2>
        <span style="font-size:11.5px;color:var(--text-dim);">Click a row or "View ▾" to view attempt details</span>
      </div>
      <div style="overflow-x:auto;">
        <table class="main-overview-table">
          <thead>
            <tr>
              <th style="min-width:180px;">Challenge</th>
              <th style="text-align:center;min-width:100px;">Total Score</th>
              <th style="text-align:center;min-width:90px;">Cost</th>
              ${tableCaps.map(c => {
                const meta = CAPABILITY_META[c] || { title: c, weight: null };
                return `
                  <th style="text-align:center;min-width:120px;">
                    <div>${escapeHtml(meta.title)}</div>
                    ${meta.weight !== null ? `<div class="th-sub">Weight ${meta.weight.toFixed(2)}</div>` : ''}
                  </th>
                `;
              }).join('')}
              <th style="text-align:right;min-width:70px;">Action</th>
            </tr>
          </thead>
          <tbody>
            ${overviewRowsHtml}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Challenges HTML (collapsed by default)
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
          <div class="attempt-tabs" id="tabs-${escapeHtml(ch.name)}">
            ${ch.attempts.map((att, idx) => `
              <button class="tab-btn ${idx === ch.attempts.length - 1 ? 'active' : ''}" data-challenge="${escapeHtml(ch.name)}" data-attempt="${att.attempt}" onclick="switchAttemptTab(this.dataset.challenge, parseInt(this.dataset.attempt))">
                Attempt ${att.attempt}${idx === ch.attempts.length - 1 ? ' (Latest)' : ''}
              </button>
            `).join('')}
          </div>
          ${ch.attempts.map((att, idx) => renderAttemptView(ch.name, att, idx === ch.attempts.length - 1)).join('')}
        </div>
      `;
    }

    challengesHtml += `
      <div class="challenge-card" id="card-${escapeHtml(ch.name)}">
        <div class="challenge-header" data-challenge="${escapeHtml(ch.name)}" onclick="toggleChallengeBody(this.dataset.challenge)">
          <div class="challenge-info">
            <span class="collapse-arrow" id="arrow-${escapeHtml(ch.name)}">▸</span>
            <span class="challenge-name">${escapeHtml(ch.name)}</span>
            ${ch.package ? `<span class="challenge-pkg">${escapeHtml(ch.package)}</span>` : ''}
            <span class="pill pill-${ch.status} pill-sm">${ch.status}</span>
          </div>
          <div class="challenge-right">
            <span class="pill pill-score ${chScoreClass}">Score: ${chScore.toFixed(3)}</span>
            ${ch.cost_usd != null ? `<span class="pill pill-cost pill-sm">$${ch.cost_usd.toFixed(4)}</span>` : ''}
            <span style="color:var(--text-dim);font-size:11px;">${formatDuration(ch.runtime)}</span>
            <span class="btn btn-sm" id="btn-toggle-${escapeHtml(ch.name)}" style="padding:2px 8px;font-size:11px;">Details ▾</span>
          </div>
        </div>
        <div class="challenge-body hidden" id="body-${escapeHtml(ch.name)}">
          ${renderUsageBanner(ch.cost_usd, ch.token_usage)}
          ${traceHtml}
          ${attemptsHtml}
        </div>
      </div>
    `;
  }

  document.getElementById('toolbarActions').innerHTML = `
    <button class="btn btn-primary" onclick="openResumeModal()" title="Resume benchmark or generate resume command">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5 3 19 12 5 21 5 3"></polygon>
      </svg>
      Resume
    </button>
    <button class="btn" onclick="openExportModal()" title="Export results as Markdown">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
        <polyline points="10 9 9 9 8 9"></polyline>
      </svg>
      Export Markdown
    </button>
    <button class="btn" onclick="copyCurrentLink()">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
      </svg>
      Copy Link
    </button>
    <button class="btn" onclick="copyText(currentRunDetail.full_path, 'Results path copied')">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
      Copy Results Path
    </button>
  `;

  content.innerHTML = `
    <!-- Run overview -->
    <div class="run-header-card">
      <div class="run-header-top">
        <div class="run-title-group">
          <div class="eyebrow">Benchmark results</div>
          <h1 class="run-title">
            ${escapeHtml(run.display_name)}
          </h1>
          <div class="run-meta-row">
            <span>Started: <strong>${escapeHtml(run.started_at)}</strong></span>
            <span>Total Runtime: <strong>${formatDuration(run.total_runtime)}</strong></span>
            ${run.cost_usd != null ? `<span>Cost: <strong style="color:var(--accent);">$${run.cost_usd.toFixed(4)}</strong></span>` : ''}
            <span>Path: <code style="font-size:11px;color:var(--accent);">${escapeHtml(run.full_path)}</code></span>
          </div>
        </div>
        <div class="run-header-actions">
          <span class="pill pill-score ${scoreClass}" style="font-size:14px;padding:4px 10px;">
            Score: ${scoreNum.toFixed(4)} (${scorePct}%)
          </span>
          ${run.cost_usd != null ? `
          <span class="pill pill-score pill-cost" style="font-size:14px;padding:4px 10px;">
            Total Cost: $${run.cost_usd.toFixed(4)}
          </span>
          ` : ''}
        </div>
      </div>

      ${tags.length > 0 ? `<div class="run-tags">${tags.join('')}</div>` : ''}
      ${renderUsageBanner(run.cost_usd, run.token_usage, true)}
    </div>

    <!-- Notes Section -->
    ${notesHtml}

    <!-- Challenges Overview Table -->
    ${overviewTableHtml}

    <!-- Challenge Drill-Down Section -->
    <div class="challenges-section">
      <h2 class="section-title">
        <span>Challenge Drill-Down (${run.challenges.length})</span>
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
    const isAttempted = cap.attempted !== false;

    let resultBadge;
    let scorePill;
    let labelColorStyle;
    let detailColorStyle;

    if (!isAttempted) {
      resultBadge = `<span class="pill pill-unattempted pill-sm">UNATTEMPTED</span>`;
      scorePill = `<span class="pill pill-score unattempted-score pill-sm">${cap.score.toFixed(2)} / ${cap.weight.toFixed(2)}</span>`;
      labelColorStyle = `color: var(--text-dim);`;
      detailColorStyle = `color: var(--text-dim); opacity: 0.75;`;
    } else {
      resultBadge = cap.passed
        ? `<span class="pill pill-completed pill-sm">PASSED</span>`
        : `<span class="pill pill-failed pill-sm">FAILED</span>`;
      if (cap.exit_code !== null) {
        resultBadge += ` <span style="font-size:10.5px;color:var(--text-dim);">(exit ${cap.exit_code})</span>`;
      }

      let capScoreClass = 'pill-failed';
      if (cap.score > 0) {
        capScoreClass = (cap.weight > 0 && cap.score >= cap.weight * 0.99) ? 'pill-completed' : 'pill-partial';
      } else {
        capScoreClass = 'pill-failed';
      }
      scorePill = `<span class="pill pill-score ${capScoreClass} pill-sm">${cap.score.toFixed(2)} / ${cap.weight.toFixed(2)}</span>`;
      labelColorStyle = `color: var(--text);`;
      detailColorStyle = `color: var(--text-muted);`;
    }

    // Local app
    let localAppHtml = '<span style="color:var(--text-dim);">-</span>';
    if (isAttempted) {
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
    if (isAttempted) {
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
    if (isAttempted) {
      if (cap.cheating === true) {
        cheatingHtml = `<span class="pill pill-failed pill-sm">⚠️ Cheating</span>`;
      } else if (cap.cheating === false) {
        cheatingHtml = `<span class="tag-clean">No</span>`;
      }
    }

    rowsHtml += `
      <tr>
        <td>
          <div style="font-weight:600;font-size:12.5px;${labelColorStyle}">${escapeHtml(capName)}</div>
          <div style="font-size:11px;${detailColorStyle}">${escapeHtml(cap.detail || (!isAttempted ? 'Not attempted' : ''))}</div>
        </td>
        <td>${resultBadge}</td>
        <td>${scorePill}</td>
        <td>${localAppHtml}</td>
        <td>${clickHtml}</td>
        <td>${cheatingHtml}</td>
        <td>
          ${cap.reasoning ? `<div style="font-size:11px;color:${isAttempted ? 'var(--text-muted)' : 'var(--text-dim)'};max-width:320px;white-space:normal;overflow-wrap:anywhere;">${escapeHtml(cap.reasoning.substring(0, 180))}${cap.reasoning.length > 180 ? '...' : ''}</div>` : '<span style="color:var(--text-dim);">-</span>'}
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
  const arrow = document.getElementById(`arrow-${chName}`);
  const btn = document.getElementById(`btn-toggle-${chName}`);
  if (body) {
    const isHidden = body.classList.toggle('hidden');
    document.getElementById(`card-${chName}`).classList.toggle('expanded', !isHidden);
    if (arrow) arrow.textContent = isHidden ? '▸' : '▾';
    if (btn) btn.textContent = isHidden ? 'Details ▾' : 'Details ▴';
  }
}

function jumpToChallenge(chName) {
  const card = document.getElementById(`card-${chName}`);
  const body = document.getElementById(`body-${chName}`);
  const arrow = document.getElementById(`arrow-${chName}`);
  const btn = document.getElementById(`btn-toggle-${chName}`);
  if (body && body.classList.contains('hidden')) {
    body.classList.remove('hidden');
    card.classList.add('expanded');
    if (arrow) arrow.textContent = '▾';
    if (btn) btn.textContent = 'Details ▴';
  }
  if (card) {
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    card.style.borderColor = 'var(--accent)';
    setTimeout(() => { card.style.borderColor = ''; }, 1500);
  }
}

function toggleCollapse(headerEl) {
  const body = headerEl.nextElementSibling;
  if (body) {
    const isHidden = body.classList.toggle('hidden');
    headerEl.parentElement.classList.toggle('expanded', !isHidden);
  }
}

function copyCurrentLink() {
  copyText(window.location.href, 'Run URL copied to clipboard');
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

function renderMarkdown(mdText) {
  if (!mdText) return '';
  if (window.marked && typeof window.marked.parse === 'function') {
    try {
      const rawHtml = window.marked.parse(mdText, { gfm: true, breaks: true });
      if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
        return window.DOMPurify.sanitize(rawHtml);
      }
      return rawHtml;
    } catch (e) {
      console.warn('Failed to parse markdown with marked:', e);
    }
  }
  return fallbackMarkdown(mdText);
}

function fallbackMarkdown(text) {
  if (!text) return '';
  const lines = text.split('\n');
  const html = [];
  let inCode = false;
  let codeLines = [];
  let inList = false;
  let inOList = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Fenced code block toggle
    if (line.trim().startsWith('```')) {
      if (inCode) {
        html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
        codeLines = [];
        inCode = false;
      } else {
        if (inList) { html.push('</ul>'); inList = false; }
        if (inOList) { html.push('</ol>'); inOList = false; }
        codeLines = [];
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    // Unordered list item
    const uListMatch = line.match(/^(\s*)[-*+]\s+(.*)$/);
    if (uListMatch) {
      if (inOList) { html.push('</ol>'); inOList = false; }
      if (!inList) { html.push('<ul>'); inList = true; }
      html.push(`<li>${inlineMarkdown(uListMatch[2])}</li>`);
      continue;
    } else if (inList) {
      html.push('</ul>');
      inList = false;
    }

    // Ordered list item
    const oListMatch = line.match(/^(\s*)\d+\.\s+(.*)$/);
    if (oListMatch) {
      if (inList) { html.push('</ul>'); inList = false; }
      if (!inOList) { html.push('<ol>'); inOList = true; }
      html.push(`<li>${inlineMarkdown(oListMatch[2])}</li>`);
      continue;
    } else if (inOList) {
      html.push('</ol>');
      inOList = false;
    }

    // Headings
    if (line.startsWith('#### ')) {
      html.push(`<h4>${inlineMarkdown(line.slice(5))}</h4>`);
    } else if (line.startsWith('### ')) {
      html.push(`<h3>${inlineMarkdown(line.slice(4))}</h3>`);
    } else if (line.startsWith('## ')) {
      html.push(`<h2>${inlineMarkdown(line.slice(3))}</h2>`);
    } else if (line.startsWith('# ')) {
      html.push(`<h1>${inlineMarkdown(line.slice(2))}</h1>`);
    } else if (line.trim() === '---' || line.trim() === '***') {
      html.push('<hr>');
    } else if (line.startsWith('> ')) {
      html.push(`<blockquote><p>${inlineMarkdown(line.slice(2))}</p></blockquote>`);
    } else if (line.trim() === '') {
      // Empty line - ignore or paragraph break
    } else {
      html.push(`<p>${inlineMarkdown(line)}</p>`);
    }
  }

  if (inCode) {
    html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
  }
  if (inList) {
    html.push('</ul>');
  }
  if (inOList) {
    html.push('</ol>');
  }

  return html.join('\n');
}

function inlineMarkdown(text) {
  let s = escapeHtml(text);
  // Bold: **text** or __text__
  s = s.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__(.*?)__/g, '<strong>$1</strong>');
  // Italic: *text* or _text_
  s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  s = s.replace(/_([^_]+)_/g, '<em>$1</em>');
  // Strikethrough: ~~text~~
  s = s.replace(/~~(.*?)~~/g, '<del>$1</del>');
  // Inline code: `text`
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Markdown links: [text](url)
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return s;
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

// ==========================================
// Markdown Export Modal Logic
// ==========================================
let exportConfig = {
  sections: {
    header: true,
    notes: true,
    table: true,
    tokens: true,
  },
  columns: {
    status: true,
    score: true,
    cost: true,
    runtime: true,
    trace: false,
  },
  capabilities: {},
  activeTab: 'markdown',
};

function initExportConfigForRun(run) {
  if (!run) return;
  exportConfig.sections.header = true;
  exportConfig.sections.notes = Boolean(run.notes && run.notes.trim());
  exportConfig.sections.table = Boolean(run.challenges && run.challenges.length > 0);
  exportConfig.sections.tokens = Boolean(run.token_usage && Object.keys(run.token_usage).length > 0);

  const anyCost = (run.challenges || []).some(ch => ch.cost_usd != null) || run.cost_usd != null;
  exportConfig.columns.status = true;
  exportConfig.columns.score = true;
  exportConfig.columns.cost = anyCost;
  exportConfig.columns.runtime = true;
  exportConfig.columns.trace = false;

  const caps = getRunCapabilities(run);
  exportConfig.capabilities = {};
  for (const c of caps) {
    exportConfig.capabilities[c] = true;
  }
}

function getRunCapabilities(run) {
  if (!run || !run.challenges) return [];
  const capsSet = new Set();
  for (const ch of run.challenges) {
    if (ch.enabled_capabilities) {
      for (const c of ch.enabled_capabilities) capsSet.add(c);
    }
    if (ch.axes) {
      for (const k of Object.keys(ch.axes)) capsSet.add(k);
    }
  }
  const ordered = [];
  for (const c of STANDARD_CAPABILITIES) {
    if (capsSet.has(c)) ordered.push(c);
  }
  for (const c of Array.from(capsSet).sort()) {
    if (!ordered.includes(c)) ordered.push(c);
  }
  return ordered;
}

function getCapTitle(c) {
  return (CAPABILITY_META[c] && CAPABILITY_META[c].title) || c.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function openExportModal() {
  if (!currentRunDetail) {
    showToast('No run selected to export');
    return;
  }
  initExportConfigForRun(currentRunDetail);
  const subtitle = document.getElementById('exportModalSubtitle');
  if (subtitle) {
    subtitle.textContent = `${currentRunDetail.display_name || currentRunDetail.folder_name}`;
  }
  renderExportConfigBar();
  switchExportTab(exportConfig.activeTab || 'markdown');
  updateExportPreview();

  const modal = document.getElementById('exportModal');
  if (modal) modal.classList.remove('hidden');
}

function closeExportModal() {
  const modal = document.getElementById('exportModal');
  if (modal) modal.classList.add('hidden');
}

function handleModalOverlayClick(e) {
  if (e.target && e.target.id === 'exportModal') {
    closeExportModal();
  }
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const exportModal = document.getElementById('exportModal');
    if (exportModal && !exportModal.classList.contains('hidden')) {
      closeExportModal();
    }
    const resumeModal = document.getElementById('resumeModal');
    if (resumeModal && !resumeModal.classList.contains('hidden')) {
      closeResumeModal();
    }
  }
});

function toggleExportSection(secKey) {
  exportConfig.sections[secKey] = !exportConfig.sections[secKey];
  renderExportConfigBar();
  updateExportPreview();
}

function toggleExportColumn(colKey) {
  exportConfig.columns[colKey] = !exportConfig.columns[colKey];
  renderExportConfigBar();
  updateExportPreview();
}

function toggleExportCap(capKey) {
  exportConfig.capabilities[capKey] = !exportConfig.capabilities[capKey];
  renderExportConfigBar();
  updateExportPreview();
}

function renderExportConfigBar() {
  const bar = document.getElementById('modalConfigBar');
  if (!bar || !currentRunDetail) return;

  const run = currentRunDetail;
  const hasNotes = Boolean(run.notes && run.notes.trim());
  const hasTokens = Boolean(run.token_usage && Object.keys(run.token_usage).length > 0);
  const runCaps = getRunCapabilities(run);

  let html = `
    <div class="config-group">
      <span class="config-group-label">Sections:</span>
      <button class="toggle-chip ${exportConfig.sections.header ? 'active' : ''}" onclick="toggleExportSection('header')">
        ${exportConfig.sections.header ? '✓ ' : ''}Header &amp; Summary
      </button>
      ${hasNotes ? `
        <button class="toggle-chip ${exportConfig.sections.notes ? 'active' : ''}" onclick="toggleExportSection('notes')">
          ${exportConfig.sections.notes ? '✓ ' : ''}Notes
        </button>
      ` : ''}
      <button class="toggle-chip ${exportConfig.sections.table ? 'active' : ''}" onclick="toggleExportSection('table')">
        ${exportConfig.sections.table ? '✓ ' : ''}Results Table
      </button>
      ${hasTokens ? `
        <button class="toggle-chip ${exportConfig.sections.tokens ? 'active' : ''}" onclick="toggleExportSection('tokens')">
          ${exportConfig.sections.tokens ? '✓ ' : ''}Token Metrics
        </button>
      ` : ''}
    </div>
  `;

  if (exportConfig.sections.table) {
    html += `
      <div class="config-group" style="padding-top:4px;border-top:1px solid rgba(255,255,255,0.05);">
        <span class="config-group-label">Columns:</span>
        <button class="toggle-chip ${exportConfig.columns.status ? 'active' : ''}" onclick="toggleExportColumn('status')">
          ${exportConfig.columns.status ? '✓ ' : ''}Status
        </button>
        <button class="toggle-chip ${exportConfig.columns.score ? 'active' : ''}" onclick="toggleExportColumn('score')">
          ${exportConfig.columns.score ? '✓ ' : ''}Score
        </button>
        <button class="toggle-chip ${exportConfig.columns.cost ? 'active' : ''}" onclick="toggleExportColumn('cost')">
          ${exportConfig.columns.cost ? '✓ ' : ''}Cost
        </button>
        <button class="toggle-chip ${exportConfig.columns.runtime ? 'active' : ''}" onclick="toggleExportColumn('runtime')">
          ${exportConfig.columns.runtime ? '✓ ' : ''}Runtime
        </button>
        <button class="toggle-chip ${exportConfig.columns.trace ? 'active' : ''}" onclick="toggleExportColumn('trace')">
          ${exportConfig.columns.trace ? '✓ ' : ''}Trace Link
        </button>
      </div>
    `;

    if (runCaps.length > 0) {
      html += `
        <div class="config-group" style="padding-top:4px;border-top:1px solid rgba(255,255,255,0.05);">
          <span class="config-group-label">Capabilities:</span>
          ${runCaps.map(c => `
            <button class="toggle-chip ${exportConfig.capabilities[c] ? 'active' : ''}" onclick="toggleExportCap(${JSON.stringify(c)})">
              ${exportConfig.capabilities[c] ? '✓ ' : ''}${escapeHtml(getCapTitle(c))}
            </button>
          `).join('')}
        </div>
      `;
    }
  }

  bar.innerHTML = html;
}

function switchExportTab(tabName) {
  exportConfig.activeTab = tabName;
  const btnMd = document.getElementById('tabBtnMarkdown');
  const btnRendered = document.getElementById('tabBtnRendered');
  const textarea = document.getElementById('exportMarkdownSource');
  const rendered = document.getElementById('exportRenderedPreview');

  if (tabName === 'markdown') {
    if (btnMd) btnMd.classList.add('active');
    if (btnRendered) btnRendered.classList.remove('active');
    if (textarea) textarea.style.display = 'block';
    if (rendered) rendered.style.display = 'none';
  } else {
    if (btnMd) btnMd.classList.remove('active');
    if (btnRendered) btnRendered.classList.add('active');
    if (textarea) textarea.style.display = 'none';
    if (rendered) rendered.style.display = 'block';
  }
}

function generateMarkdownReport(run, config) {
  if (!run) return '';
  const lines = [];

  // 1. Header Section
  if (config.sections.header) {
    const title = run.display_name || run.folder_name;
    lines.push(`# Benchmark Results: ${title}`);
    lines.push('');
    if (run.started_at) lines.push(`- **Started:** ${run.started_at}`);
    const scoreNum = run.score || 0.0;
    const scorePct = Math.round(scoreNum * 100);
    lines.push(`- **Score:** ${scoreNum.toFixed(4)} (${scorePct}%)`);
    if (run.cost_usd != null) lines.push(`- **Total Cost:** $${run.cost_usd.toFixed(4)}`);
    if (run.total_runtime) lines.push(`- **Total Runtime:** ${formatDuration(run.total_runtime)}`);
    if (run.config) {
      const cfg = run.config;
      if (cfg.model) lines.push(`- **Model:** ${cfg.model}${cfg.model_effort ? ' (' + cfg.model_effort + ')' : ''}`);
      if (cfg.harness) lines.push(`- **Harness:** ${cfg.harness}`);
      if (cfg.num_instances) lines.push(`- **Instances:** ${cfg.num_instances}`);
      if (cfg.max_reprompts !== undefined && cfg.max_reprompts !== null) lines.push(`- **Max Reprompts:** ${cfg.max_reprompts}`);
      if (cfg.internet_enabled) lines.push(`- **Internet:** Enabled`);
      if (cfg.time_limit) lines.push(`- **Timeout:** ${formatDuration(cfg.time_limit)}`);
    }
    if (run.full_path) lines.push(`- **Path:** \`${run.full_path}\``);
    lines.push('');
  }

  // 2. Notes Section
  if (config.sections.notes && run.notes && run.notes.trim()) {
    lines.push('## Notes');
    lines.push('');
    lines.push(run.notes.trim());
    lines.push('');
  }

  // 3. Results Table Section
  if (config.sections.table && run.challenges && run.challenges.length > 0) {
    lines.push('## Results Summary');
    lines.push('');

    // Table Headers
    const headers = ['Challenge'];
    const aligns = [':---'];

    if (config.columns.status) {
      headers.push('Status');
      aligns.push(':---:');
    }
    if (config.columns.score) {
      headers.push('Score');
      aligns.push(':---:');
    }
    if (config.columns.cost) {
      headers.push('Cost');
      aligns.push(':---:');
    }
    if (config.columns.runtime) {
      headers.push('Runtime');
      aligns.push(':---:');
    }

    const runCaps = getRunCapabilities(run);
    const activeCaps = runCaps.filter(c => config.capabilities[c]);
    for (const c of activeCaps) {
      headers.push(getCapTitle(c));
      aligns.push(':---:');
    }

    if (config.columns.trace) {
      headers.push('Trace');
      aligns.push(':---:');
    }

    lines.push(`| ${headers.join(' | ')} |`);
    lines.push(`| ${aligns.join(' | ')} |`);

    for (const ch of run.challenges) {
      const row = [];
      let nameCell = ch.name;
      if (ch.package) nameCell += ` (\`${ch.package}\`)`;
      row.push(nameCell);

      if (config.columns.status) {
        row.push(ch.status || 'completed');
      }
      if (config.columns.score) {
        const sc = ch.score || 0.0;
        row.push(sc.toFixed(3));
      }
      if (config.columns.cost) {
        row.push(ch.cost_usd != null ? `$${ch.cost_usd.toFixed(4)}` : '-');
      }
      if (config.columns.runtime) {
        row.push(formatDuration(ch.runtime));
      }

      const latestAtt = (ch.attempts && ch.attempts.length > 0) ? ch.attempts[ch.attempts.length - 1] : null;
      for (const capName of activeCaps) {
        const isConfigured = (ch.enabled_capabilities && ch.enabled_capabilities.includes(capName))
          || (ch.axes && ch.axes[capName] !== undefined);
        const capDetail = (latestAtt && latestAtt.capabilities) ? latestAtt.capabilities[capName] : null;
        const isAttempted = capDetail ? (capDetail.attempted !== false) : (ch.axes && (ch.axes[capName] !== undefined && ch.axes[capName] > 0));

        if (!isConfigured) {
          row.push('-');
        } else if (!isAttempted) {
          row.push('UNATTEMPTED');
        } else {
          const capScore = capDetail ? capDetail.score : ((ch.axes && ch.axes[capName] !== undefined) ? ch.axes[capName] : 0.0);
          const meta = (typeof CAPABILITY_META !== 'undefined' && CAPABILITY_META[capName]) ? CAPABILITY_META[capName] : null;
          const capWeight = (capDetail && capDetail.weight > 0) ? capDetail.weight : (meta ? meta.weight : 0.0);
          if (capWeight > 0) {
            row.push(`${capScore.toFixed(2)} / ${capWeight.toFixed(2)}`);
          } else {
            row.push(`${capScore.toFixed(2)}`);
          }
        }
      }

      if (config.columns.trace) {
        if (ch.trace_url) {
          row.push(`[Trace](${ch.trace_url})`);
        } else if (ch.session_id) {
          row.push(`\`${ch.session_id.substring(0, 8)}...\``);
        } else {
          row.push('-');
        }
      }

      lines.push(`| ${row.join(' | ')} |`);
    }
    lines.push('');
  }

  // 4. Token Usage Section
  if (config.sections.tokens) {
    const tu = parseTokenUsage(run.token_usage);
    if (tu && tu.hasTokens) {
      lines.push('## Token Usage Summary');
      lines.push('');
      if (tu.total > 0) lines.push(`- **Total Tokens:** ${tu.total.toLocaleString()}`);
      if (tu.input > 0) lines.push(`- **Input Tokens:** ${tu.input.toLocaleString()}`);
      if (tu.output > 0) lines.push(`- **Output Tokens:** ${tu.output.toLocaleString()}`);
      if (tu.cacheRead > 0) lines.push(`- **Cache Read Tokens:** ${tu.cacheRead.toLocaleString()}`);
      if (tu.cacheWrite > 0) lines.push(`- **Cache Write Tokens:** ${tu.cacheWrite.toLocaleString()}`);
      if (tu.reasoning > 0) lines.push(`- **Reasoning Tokens:** ${tu.reasoning.toLocaleString()}`);
      if (tu.model) lines.push(`- **Model:** \`${tu.model}\``);
      lines.push('');
    }
  }

  return lines.join('\n');
}

function updateExportPreview() {
  if (!currentRunDetail) return;
  const md = generateMarkdownReport(currentRunDetail, exportConfig);

  const textarea = document.getElementById('exportMarkdownSource');
  if (textarea) textarea.value = md;

  const rendered = document.getElementById('exportRenderedPreview');
  if (rendered) {
    rendered.innerHTML = renderMarkdown(md);
  }

  const stats = document.getElementById('exportStatsText');
  if (stats) {
    const chCount = (currentRunDetail.challenges || []).length;
    const activeCaps = Object.values(exportConfig.capabilities).filter(Boolean).length;
    stats.textContent = `${chCount} challenge${chCount === 1 ? '' : 's'} • ${activeCaps} capability column${activeCaps === 1 ? '' : 's'} active`;
  }
}

function copyExportMarkdown() {
  const textarea = document.getElementById('exportMarkdownSource');
  if (!textarea || !textarea.value) {
    showToast('Nothing to copy');
    return;
  }
  copyText(textarea.value, 'Markdown report copied to clipboard');
}

// -------------------------------------------------------------
// Resume Benchmark Modal Logic
// -------------------------------------------------------------
let resumeState = {
  run: null,
  useRelative: true,
  includeUv: true,
  challenges: {} // name -> { name, package, status, score, pastAttempts, mode, attempts }
};

function openResumeModal() {
  if (!currentRunDetail) {
    showToast('No run selected to resume');
    return;
  }
  initResumeStateForRun(currentRunDetail);
  const subtitle = document.getElementById('resumeModalSubtitle');
  if (subtitle) {
    subtitle.textContent = `${currentRunDetail.display_name || currentRunDetail.folder_name}`;
  }
  renderResumeBulkBar();
  renderResumeChallengesList();
  updateResumeCommand();

  const modal = document.getElementById('resumeModal');
  if (modal) modal.classList.remove('hidden');
}

function closeResumeModal() {
  const modal = document.getElementById('resumeModal');
  if (modal) modal.classList.add('hidden');
}

function handleResumeModalOverlayClick(e) {
  if (e.target && e.target.id === 'resumeModal') {
    closeResumeModal();
  }
}

function initResumeStateForRun(run) {
  resumeState.run = run;
  resumeState.challenges = {};
  const defaultAttempts = (run.config && run.config.max_reprompts != null) ? run.config.max_reprompts : 1;

  (run.challenges || []).forEach(ch => {
    const isCompleted = ch.status === 'completed' && ch.score >= 1.0;
    // Default mode: if already completed with score >= 1.0, default to 'none' so user doesn't re-run solved challenges unintentionally;
    // otherwise default to 'auto'
    const initialMode = isCompleted ? 'none' : 'auto';
    resumeState.challenges[ch.name] = {
      name: ch.name,
      package: ch.package || '',
      status: ch.status || 'unknown',
      score: ch.score != null ? ch.score : 0.0,
      pastAttempts: (ch.attempts && ch.attempts.length) || 0,
      mode: initialMode,
      attempts: defaultAttempts,
    };
  });
}

function renderResumeBulkBar() {
  const bar = document.getElementById('resumeBulkBar');
  if (!bar || !resumeState.run) return;

  const defaultAttempts = (resumeState.run.config && resumeState.run.config.max_reprompts != null)
    ? resumeState.run.config.max_reprompts
    : 1;

  bar.innerHTML = `
    <div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;">
      <span class="config-group-label" style="min-width:auto;margin-right:4px;">Quick Actions:</span>
      <button class="toggle-chip" onclick="applyResumeBulkMode('auto', ${defaultAttempts})" title="Set all challenges to auto mode">All Auto</button>
      <button class="toggle-chip" onclick="applyResumeBulkMode('regrade', 0)" title="Regrade and persist existing solutions with 0 additional attempts">All Regrade (0 attempts)</button>
      <button class="toggle-chip" onclick="applyResumeIncompleteOnly(${defaultAttempts})" title="Set incomplete/failed to auto, completed to none">Incomplete Only</button>
      <button class="toggle-chip" onclick="applyResumeAllNone()" title="Disable all challenges">Deselect All</button>
    </div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="font-size:11px;color:var(--text-muted);">Set All Mode:</span>
        <select class="resume-select" onchange="applyResumeBulkMode(this.value); this.selectedIndex=0;">
          <option value="" disabled selected>Select...</option>
          <option value="auto">auto</option>
          <option value="regrade">regrade</option>
          <option value="last-attempt">last-attempt</option>
          <option value="keep-going">keep-going</option>
          <option value="none">none</option>
        </select>
      </div>
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="font-size:11px;color:var(--text-muted);">Set All Attempts:</span>
        <div class="resume-input-group">
          <input type="number" min="0" max="99" class="resume-input" id="bulkAttemptsInput" value="${defaultAttempts}" style="width:48px;">
          <button class="btn btn-sm" onclick="applyResumeBulkAttempts()" style="padding:3px 8px;font-size:11px;">Apply</button>
        </div>
      </div>
    </div>
  `;
}

function renderResumeChallengesList() {
  const container = document.getElementById('resumeChallengesList');
  if (!container || !resumeState.run) return;

  const chs = Object.values(resumeState.challenges);
  if (chs.length === 0) {
    container.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted);">No challenges found in this run.</div>`;
    return;
  }

  container.innerHTML = chs.map(ch => {
    const isNone = ch.mode === 'none';
    const isRegrade = ch.mode === 'regrade';
    const minAttempts = isRegrade ? 0 : 1;
    const scorePct = Math.round(ch.score * 100);
    const scoreColor = ch.score >= 1.0 ? 'var(--green)' : (ch.score > 0 ? 'var(--yellow)' : 'var(--text-muted)');

    return `
      <div class="resume-row ${isNone ? 'disabled' : ''}" id="resume-row-${escapeHtml(ch.name)}">
        <div class="resume-row-left">
          <input type="checkbox" ${!isNone ? 'checked' : ''} onchange="toggleResumeChallengeEnabled('${escapeHtml(ch.name)}', this.checked)" title="Enable or disable this challenge" style="cursor:pointer;accent-color:var(--accent);">
          <div style="display:flex;flex-direction:column;gap:1px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-weight:600;font-size:13px;color:var(--text);">${escapeHtml(ch.name)}</span>
              <span class="pill pill-${escapeHtml(ch.status)} pill-sm">${escapeHtml(ch.status)}</span>
              <span style="font-size:11px;font-weight:600;color:${scoreColor};">${ch.score.toFixed(2)} (${scorePct}%)</span>
              <span style="font-size:11px;color:var(--text-dim);">${ch.pastAttempts} ${ch.pastAttempts === 1 ? 'attempt' : 'attempts'}</span>
            </div>
            ${ch.package ? `<span class="challenge-pkg" style="font-size:11px;">${escapeHtml(ch.package)}</span>` : ''}
          </div>
        </div>
        <div class="resume-row-right">
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:11px;color:var(--text-dim);">Mode:</span>
            <select class="resume-select" onchange="setResumeChallengeMode('${escapeHtml(ch.name)}', this.value)">
              <option value="auto" ${ch.mode === 'auto' ? 'selected' : ''}>auto</option>
              <option value="regrade" ${ch.mode === 'regrade' ? 'selected' : ''}>regrade</option>
              <option value="last-attempt" ${ch.mode === 'last-attempt' ? 'selected' : ''}>last-attempt</option>
              <option value="keep-going" ${ch.mode === 'keep-going' ? 'selected' : ''}>keep-going</option>
              <option value="none" ${ch.mode === 'none' ? 'selected' : ''}>none</option>
            </select>
          </div>
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:11px;color:var(--text-dim);">Attempts:</span>
            <div class="resume-input-group">
              <button class="resume-stepper-btn" ${isNone ? 'disabled' : ''} onclick="stepResumeAttempts('${escapeHtml(ch.name)}', -1)">−</button>
              <input type="number" class="resume-input" min="${minAttempts}" max="99" ${isNone ? 'disabled' : ''} value="${ch.attempts}" onchange="setResumeChallengeAttempts('${escapeHtml(ch.name)}', this.value)">
              <button class="resume-stepper-btn" ${isNone ? 'disabled' : ''} onclick="stepResumeAttempts('${escapeHtml(ch.name)}', 1)">+</button>
            </div>
            ${isRegrade && ch.attempts === 0 ? `<span style="font-size:10px;color:var(--yellow);margin-left:2px;">(regrade only)</span>` : ''}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function toggleResumeChallengeEnabled(name, enabled) {
  const ch = resumeState.challenges[name];
  if (!ch) return;
  if (!enabled) {
    ch.mode = 'none';
  } else {
    ch.mode = 'auto';
    if (ch.attempts === 0) ch.attempts = 1;
  }
  renderResumeChallengesList();
  updateResumeCommand();
}

function setResumeChallengeMode(name, mode) {
  const ch = resumeState.challenges[name];
  if (!ch) return;
  ch.mode = mode;
  if (mode !== 'regrade' && ch.attempts === 0) {
    ch.attempts = 1;
  }
  renderResumeChallengesList();
  updateResumeCommand();
}

function setResumeChallengeAttempts(name, val) {
  const ch = resumeState.challenges[name];
  if (!ch) return;
  let num = parseInt(val, 10);
  const min = ch.mode === 'regrade' ? 0 : 1;
  if (isNaN(num) || num < min) num = min;
  ch.attempts = num;
  renderResumeChallengesList();
  updateResumeCommand();
}

function stepResumeAttempts(name, delta) {
  const ch = resumeState.challenges[name];
  if (!ch || ch.mode === 'none') return;
  const min = ch.mode === 'regrade' ? 0 : 1;
  ch.attempts = Math.max(min, ch.attempts + delta);
  renderResumeChallengesList();
  updateResumeCommand();
}

function applyResumeBulkMode(mode, attempts) {
  if (!mode) return;
  Object.values(resumeState.challenges).forEach(ch => {
    ch.mode = mode;
    if (attempts != null) {
      ch.attempts = attempts;
    } else if (mode !== 'regrade' && ch.attempts === 0) {
      ch.attempts = 1;
    }
  });
  renderResumeChallengesList();
  updateResumeCommand();
}

function applyResumeIncompleteOnly(defaultAttempts) {
  Object.values(resumeState.challenges).forEach(ch => {
    const isCompleted = ch.status === 'completed' && ch.score >= 1.0;
    if (isCompleted) {
      ch.mode = 'none';
    } else {
      ch.mode = 'auto';
      ch.attempts = defaultAttempts;
    }
  });
  renderResumeChallengesList();
  updateResumeCommand();
}

function applyResumeAllNone() {
  Object.values(resumeState.challenges).forEach(ch => {
    ch.mode = 'none';
  });
  renderResumeChallengesList();
  updateResumeCommand();
}

function applyResumeBulkAttempts() {
  const input = document.getElementById('bulkAttemptsInput');
  if (!input) return;
  const val = parseInt(input.value, 10);
  if (isNaN(val) || val < 0) return;
  Object.values(resumeState.challenges).forEach(ch => {
    if (ch.mode !== 'none') {
      const min = ch.mode === 'regrade' ? 0 : 1;
      ch.attempts = Math.max(min, val);
    }
  });
  renderResumeChallengesList();
  updateResumeCommand();
}

function toggleResumeRelativePath() {
  resumeState.useRelative = !resumeState.useRelative;
  const chip = document.getElementById('chipResumeRel');
  if (chip) chip.classList.toggle('active', resumeState.useRelative);
  updateResumeCommand();
}

function toggleResumeUvPrefix() {
  resumeState.includeUv = !resumeState.includeUv;
  const chip = document.getElementById('chipResumeUv');
  if (chip) chip.classList.toggle('active', resumeState.includeUv);
  updateResumeCommand();
}

function updateResumeCommand() {
  const textarea = document.getElementById('resumeCommandText');
  const stats = document.getElementById('resumeStatsText');
  if (!textarea || !resumeState.run) return;

  const run = resumeState.run;
  let targetPath = '';
  if (resumeState.useRelative && run.path) {
    if (run.path.startsWith('results/')) {
      targetPath = run.path;
    } else {
      targetPath = 'results/' + run.path.replace(/^\/+/, '');
    }
  } else {
    targetPath = run.full_path || run.path || '';
  }

  if (targetPath.includes(' ')) {
    targetPath = `"${targetPath}"`;
  }

  const prefix = resumeState.includeUv ? 'uv run android-bench resume' : 'android-bench resume';
  const allChs = Object.values(resumeState.challenges);
  const activeChs = allChs.filter(ch => ch.mode !== 'none');
  const defaultAttempts = (run.config && run.config.max_reprompts != null) ? run.config.max_reprompts : 1;

  if (stats) {
    stats.textContent = `${activeChs.length} of ${allChs.length} challenge${allChs.length === 1 ? '' : 's'} selected to resume`;
  }

  if (activeChs.length === 0) {
    textarea.value = '# No challenges selected to resume\n# Use quick actions or checkboxes above to enable challenges.';
    return;
  }

  let cmd = '';
  const firstMode = activeChs[0].mode;
  const firstAttempts = activeChs[0].attempts;
  const allSameMode = activeChs.every(c => c.mode === firstMode);
  const allSameAttempts = activeChs.every(c => c.attempts === firstAttempts);

  if (activeChs.length === allChs.length && allSameMode && allSameAttempts) {
    // All challenges in the run are active with identical settings
    if (firstMode === 'auto' && firstAttempts === defaultAttempts) {
      cmd = `${prefix} ${targetPath} --all`;
    } else if (firstMode === 'auto') {
      cmd = `${prefix} ${targetPath} --all --attempts ${firstAttempts}`;
    } else {
      cmd = `${prefix} ${targetPath} --mode ${firstMode} --attempts ${firstAttempts}`;
    }
  } else {
    // Subset of challenges or differing settings: emit explicit per-challenge specs
    const challengeFlags = activeChs.map(ch => {
      if (ch.mode === 'auto' && ch.attempts === defaultAttempts) {
        return `--challenge "${ch.name}"`;
      }
      return `--challenge "${ch.name},mode=${ch.mode},attempts=${ch.attempts}"`;
    }).join(' ');
    cmd = `${prefix} ${targetPath} ${challengeFlags}`;
  }

  textarea.value = cmd;
}

function copyResumeCommand() {
  const textarea = document.getElementById('resumeCommandText');
  if (!textarea || !textarea.value || textarea.value.startsWith('# No challenges')) {
    showToast('No active challenges to copy');
    return;
  }
  const cmd = textarea.value;
  copyText(cmd, 'Resume command copied to clipboard');

  const btn = document.getElementById('btnCopyResumeCommand');
  if (btn) {
    const origHtml = btn.innerHTML;
    btn.innerHTML = `
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
      Copied!
    `;
    setTimeout(() => {
      btn.innerHTML = origHtml;
    }, 2000);
  }
}
</script>
</body>
</html>
"""
