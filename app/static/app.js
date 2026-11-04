/* TrustOps AI dashboard.
   Data layer: DEMO mode (preview) uses window.TRUSTOPS_DEMO_DATA and computes
   everything locally; otherwise every call goes to the real FastAPI backend
   with the business API key. Same UI code in both modes. */
"use strict";
const DEMO = typeof window.TRUSTOPS_DEMO_DATA !== "undefined";
const state = { key: DEMO ? "demo" : (localStorage.getItem("trustops_key") || ""),
  overview: null, issues: null, trends: [], conversations: [], evaluations: [], queue: [], policies: [], settings: null, charts: {} };
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const trunc = (s, n) => (s && s.length > n ? s.slice(0, n) + "…" : s || "");

function toast(msg) { const t = $("toast"); t.textContent = msg; t.hidden = false; setTimeout(() => t.hidden = true, 3400); }

/* ---------------- demo data layer ---------------- */
function demoOverview(d) {
  const evs = d.evaluations;
  const avg = evs.length ? Math.round(evs.reduce((a, e) => a + e.overall_score, 0) / evs.length * 10) / 10 : null;
  const reviewed = new Set(d.reviews.map(r => r.evaluation_id));
  return { total_conversations: d.conversations.length, total_evaluations: evs.length,
    passed: evs.filter(e => e.status === "passed").length, flagged: evs.filter(e => e.status === "flagged").length,
    needs_review: evs.filter(e => e.status === "needs_review").length,
    high_risk: evs.filter(e => ["high", "critical"].includes(e.risk_level)).length,
    average_score: avg, pending_reviews: evs.filter(e => e.human_review_required && !reviewed.has(e.id)).length,
    total_issues: evs.reduce((a, e) => a + e.issues.length, 0),
    average_latency_ms: 12, total_estimated_cost: 0 };
}
function demoApi(path, opts = {}) {
  const d = window.TRUSTOPS_DEMO_DATA;
  const method = (opts.method || "GET").toUpperCase();
  const body = opts.body ? JSON.parse(opts.body) : {};
  return new Promise((resolve) => setTimeout(() => {
    if (path === "/api/v1/analytics/overview") return resolve(demoOverview(d));
    if (path === "/api/v1/analytics/issues") {
      const byCat = {}, bySev = {};
      d.evaluations.forEach(e => e.issues.forEach(i => { byCat[i.category] = (byCat[i.category] || 0) + 1; bySev[i.severity] = (bySev[i.severity] || 0) + 1; }));
      return resolve({ by_category: Object.entries(byCat).map(([category, count]) => ({ category, count })).sort((a, b) => b.count - a.count),
                       by_severity: Object.entries(bySev).map(([severity, count]) => ({ severity, count })) });
    }
    if (path.startsWith("/api/v1/analytics/trends")) {
      const days = [...Array(14)].map((_, i) => { const dt = new Date(); dt.setDate(dt.getDate() - (13 - i)); return dt.toISOString().slice(0, 10); });
      return resolve(days.map((date, i) => ({ date, evaluations: i === 13 ? d.evaluations.length : 0, average_score: i === 13 && d.evaluations.length ? demoOverview(d).average_score : null })));
    }
    if (path === "/api/v1/conversations") return resolve(d.conversations);
    if (path === "/api/v1/evaluations" && method === "GET") return resolve(d.evaluations);
    if (path === "/api/v1/evaluations/bulk") return resolve(d.evaluations);
    if (path === "/api/v1/reviews/queue") {
      const reviewed = new Set(d.reviews.map(r => r.evaluation_id));
      return resolve(d.evaluations.filter(e => e.human_review_required && !reviewed.has(e.id)));
    }
    if (path === "/api/v1/reviews" && method === "GET") return resolve(d.reviews);
    const reviewMatch = path.match(/^\/api\/v1\/reviews\/(\d+)$/);
    if (reviewMatch && method === "POST") {
      const r = { id: d.reviews.length + 1, evaluation_id: Number(reviewMatch[1]), reviewer_name: body.reviewer_name, decision: body.decision, notes: body.notes || null, reviewed_at: new Date().toISOString() };
      d.reviews.push(r); return resolve(r);
    }
    if (reviewMatch) return resolve(d.reviews.filter(r => r.evaluation_id === Number(reviewMatch[1])));
    if (path === "/api/v1/policies" && method === "GET") return resolve(d.policies);
    if (path === "/api/v1/policies/presets/apply") { const n = d.presetPolicies.filter(p => !d.policies.some(x => x.title === p.title)); n.forEach(p => d.policies.push({ ...p, id: d.policies.length + 101, enabled: true })); return resolve({ created: n.length, skipped_existing: d.presetPolicies.length - n.length }); }
    if (path === "/api/v1/policies" && method === "POST") { const p = { id: d.policies.length + 1, title: body.title, description: null, rule_text: body.rule_text, enabled: true }; d.policies.push(p); return resolve(p); }
    const polMatch = path.match(/^\/api\/v1\/policies\/(\d+)$/);
    if (polMatch && method === "PUT") { const p = d.policies.find(x => x.id === Number(polMatch[1])); Object.assign(p, body); return resolve(p); }
    if (polMatch && method === "DELETE") { d.policies = d.policies.filter(x => x.id !== Number(polMatch[1])); return resolve({ deleted: true }); }
    if (path === "/api/v1/settings") return resolve({ business_name: "Demo Business (preview)", llm_provider: "mock", llm_model: "mock-evaluator-v1", llm_api_key_configured: false, prompt_version: "eval-v1", database: "sqlite", max_upload_size_mb: 10 });
    if (path === "/api/v1/demo/seed") return resolve({ policies_created: 0, imported: 0, duplicates_skipped: 8, evaluated: 0 });
    return resolve({});
  }, 60));
}

/* ---------------- real API layer ---------------- */
async function api(path, opts = {}) {
  if (DEMO) return demoApi(path, opts);
  const headers = { "X-API-Key": state.key, ...(opts.headers || {}) };
  if (opts.body && typeof opts.body === "string") headers["Content-Type"] = "application/json";
  const res = await fetch(path, { ...opts, headers });
  if (!res.ok) { let msg = res.status + " error"; try { msg = (await res.json()).detail || msg; } catch (e) {} throw new Error(msg); }
  return res.json();
}
async function apiUpload(path, file) {
  if (DEMO) { toast("Uploads are disabled in the preview — run the real backend to ingest files."); return { imported: 0, duplicates_skipped: 0, failed: 0, errors: [] }; }
  const fd = new FormData(); fd.append("file", file);
  const res = await fetch(path, { method: "POST", headers: { "X-API-Key": state.key }, body: fd });
  if (!res.ok) { let msg = res.status + " error"; try { msg = (await res.json()).detail || msg; } catch (e) {} throw new Error(msg); }
  return res.json();
}

/* ---------------- loading + rendering ---------------- */
async function loadAll() {
  [state.overview, state.issues, state.trends, state.conversations, state.evaluations, state.queue, state.policies, state.settings] =
    await Promise.all([api("/api/v1/analytics/overview"), api("/api/v1/analytics/issues"), api("/api/v1/analytics/trends?days=14"),
      api("/api/v1/conversations?limit=200"), api("/api/v1/evaluations?limit=200"), api("/api/v1/reviews/queue"),
      api("/api/v1/policies"), api("/api/v1/settings")]);
  $("bizName").textContent = "🏢 " + (state.settings.business_name || "Business");
  $("queueBadge").textContent = state.queue.length || "";
  renderOverview(); renderConversations(); renderQueue(); renderPolicies(); renderSettings();
}
const latestEval = (cid) => state.evaluations.filter(e => e.conversation_id === cid).sort((a, b) => b.id - a.id)[0];

function kpi(num, lbl) { return `<div class="kpi"><div class="num">${num ?? "—"}</div><div class="lbl">${lbl}</div></div>`; }
function makeChart(id, cfg, fallbackId, fallbackText) {
  const el = $(id); if (!el) return;
  if (typeof Chart === "undefined") { el.style.display = "none"; $(fallbackId).textContent = fallbackText; return; }
  if (state.charts[id]) state.charts[id].destroy();
  state.charts[id] = new Chart(el, cfg);
}
function renderOverview() {
  const o = state.overview;
  $("kpis").innerHTML = [kpi(o.total_conversations, "Conversations"), kpi(o.total_evaluations, "Evaluations"),
    kpi(o.average_score, "Average score"), kpi(o.flagged, "Flagged"), kpi(o.high_risk, "High risk"),
    kpi(o.pending_reviews, "Pending reviews")].join("");
  makeChart("statusChart", { type: "doughnut", data: { labels: ["Passed", "Flagged", "Needs review"],
    datasets: [{ data: [o.passed, o.flagged, o.needs_review], backgroundColor: ["#22c55e", "#ef4444", "#f59e0b"] }] },
    options: { plugins: { legend: { position: "bottom" } } } }, "statusFallback", `Passed ${o.passed} · Flagged ${o.flagged} · Needs review ${o.needs_review}`);
  const cats = state.issues.by_category;
  makeChart("issuesChart", { type: "bar", data: { labels: cats.map(c => c.category),
    datasets: [{ label: "Issues", data: cats.map(c => c.count), backgroundColor: "#0e9488" }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } },
    "issuesFallback", cats.map(c => `${c.category}: ${c.count}`).join(" · ") || "No issues yet");
  makeChart("trendChart", { type: "line", data: { labels: state.trends.map(t => t.date.slice(5)),
    datasets: [{ label: "Evaluations", data: state.trends.map(t => t.evaluations), borderColor: "#0e9488", tension: .3, fill: false },
               { label: "Avg score", data: state.trends.map(t => t.average_score), borderColor: "#f59e0b", tension: .3, fill: false }] },
    options: { scales: { y: { beginAtZero: true } } } }, "trendFallback",
    state.trends.map(t => `${t.date}: ${t.evaluations}`).join(" · "));
}
function pill(v) { return `<span class="pill ${esc(v || "none")}">${esc(v || "not evaluated")}</span>`; }
function renderConversations() {
  const q = ($("searchInput").value || "").toLowerCase();
  const sf = $("statusFilter").value, rf = $("riskFilter").value;
  const rows = state.conversations.filter(c => {
    const ev = latestEval(c.id);
    if (q && !(c.user_message.toLowerCase().includes(q) || c.assistant_response.toLowerCase().includes(q))) return false;
    if (sf === "none" && ev) return false; if (sf && sf !== "none" && (!ev || ev.status !== sf)) return false;
    if (rf && (!ev || ev.risk_level !== rf)) return false;
    return true;
  });
  if (!rows.length) { $("convTable").innerHTML = `<p class="muted">No conversations match. Upload a CSV/JSON file from Settings, or load demo data.</p>`; return; }
  $("convTable").innerHTML = `<table><thead><tr><th>ID</th><th>Customer</th><th>Assistant</th><th>Score</th><th>Status</th><th>Risk</th><th>Source</th><th></th></tr></thead><tbody>` +
    rows.map(c => { const ev = latestEval(c.id); return `<tr><td>${esc(c.conversation_id)}</td><td>${esc(trunc(c.user_message, 60))}</td><td>${esc(trunc(c.assistant_response, 60))}</td>
      <td class="score">${ev ? ev.overall_score : "—"}</td><td>${pill(ev && ev.status)}</td><td>${ev ? pill(ev.risk_level) : "—"}</td><td>${esc(c.source)}</td>
      <td><button class="btn small" onclick="openDetail(${c.id})">View</button></td></tr>`; }).join("") + `</tbody></table>`;
}
function renderQueue() {
  if (!state.queue.length) { $("queueList").innerHTML = `<div class="card">🎉 Review queue is empty. Nothing is waiting for a human decision.</div>`; return; }
  $("queueList").innerHTML = state.queue.map(ev => {
    const c = state.conversations.find(x => x.id === ev.conversation_id) || {};
    return `<div class="card queue-card"><div><strong>${esc(ev.conversation_external_id)}</strong> · score <span class="score">${ev.overall_score}</span> ${pill(ev.status)} ${pill(ev.risk_level)}
      <div class="muted">${esc(trunc(c.user_message || "", 90))}</div>
      <div class="tiny muted">${ev.issues.length} issue(s) · top: ${esc(ev.issues[0] ? ev.issues[0].category : "—")}</div></div>
      <button class="btn primary" onclick="openDetail(${ev.conversation_id})">Review</button></div>`;
  }).join("");
}
function renderPolicies() {
  if (!state.policies.length) { $("policyList").innerHTML = `<div class="card muted">No policies yet. Apply the presets or add your first policy above.</div>`; return; }
  $("policyList").innerHTML = state.policies.map(p => `<div class="card">
    <div class="queue-card"><strong>${esc(p.title)}</strong>
    <span class="switch"><label class="tiny muted">${p.enabled ? "Enabled" : "Disabled"}</label>
    <input type="checkbox" style="width:auto" ${p.enabled ? "checked" : ""} onchange="togglePolicy(${p.id}, this.checked)">
    <button class="btn small" onclick="deletePolicy(${p.id})">Delete</button></span></div>
    <p class="muted" style="margin:6px 0 0">${esc(p.rule_text)}</p></div>`).join("");
}
function renderSettings() {
  const s = state.settings;
  const rows = [["Business", s.business_name], ["LLM provider", s.llm_provider], ["Evaluation model", s.llm_model],
    ["LLM API key configured", s.llm_api_key_configured ? "Yes (value never shown)" : "No — mock evaluator in use"],
    ["Prompt version", s.prompt_version], ["Database", s.database], ["Max upload (MB)", s.max_upload_size_mb]];
  $("settingsTable").innerHTML = `<table><tbody>` + rows.map(r => `<tr><th style="width:220px">${esc(r[0])}</th><td>${esc(r[1])}</td></tr>`).join("") + `</tbody></table>`;
}

/* ---------------- detail + review ---------------- */
window.openDetail = function (conversationId) {
  const c = state.conversations.find(x => x.id === conversationId); if (!c) return;
  const ev = latestEval(conversationId);
  let html = `<h2 style="margin-top:0">${esc(c.conversation_id)}</h2>
    <div class="tiny muted">Source: ${esc(c.source)} · ${esc(c.timestamp || "")}</div>
    <h3>Customer</h3><div class="msg">${esc(c.user_message)}</div>
    <h3>Chatbot response</h3><div class="msg">${esc(c.assistant_response)}</div>`;
  if (!ev) {
    html += `<p class="muted">Not evaluated yet.</p><button class="btn primary" onclick="evaluateOne(${c.id})">Evaluate now</button>`;
  } else {
    html += `<h3>Evaluation — score <span class="score">${ev.overall_score}</span> ${pill(ev.status)} ${pill(ev.risk_level)}</h3>
      <div class="tiny muted">Model: ${esc(ev.evaluation_model)} · Prompt: ${esc(ev.prompt_version)} · Latency: ${ev.latency_ms} ms · Est. cost: $${ev.estimated_cost} · Evidence: ${esc(ev.evidence_assessment)}${ev.prompt_injection_detected ? " · ⚠️ prompt-injection attempt in customer message" : ""}</div>`;
    html += ev.issues.length ? ev.issues.map(i => `<div class="issue ${esc(i.severity)}"><strong>${esc(i.category)}</strong> · ${esc(i.severity)} <span class="meta">(${esc(i.source)}${i.policy_title ? " · policy: " + esc(i.policy_title) : ""})</span>
      <div>${esc(i.reason)}</div>${i.evidence ? `<div class="meta">Evidence/policy: ${esc(i.evidence)}</div>` : ""}${i.suggested_action ? `<div class="meta">Suggested action: ${esc(i.suggested_action)}</div>` : ""}</div>`).join("")
      : `<p class="muted">No issues found.</p>`;
    if (ev.suggested_reply) html += `<h3>Suggested safer reply</h3><div class="msg">${esc(ev.suggested_reply)}</div>`;
    if (ev.human_review_required) {
      html += `<h3>Human review</h3>
        <input id="reviewerName" placeholder="Your name (reviewer)">
        <select id="reviewDecision"><option value="confirmed">Confirmed — the AI finding is correct</option><option value="false_positive">False positive — the response was acceptable</option></select>
        <textarea id="reviewNotes" rows="2" placeholder="Notes (optional)"></textarea>
        <button class="btn primary" onclick="submitReview(${ev.id})">Submit review</button>
        <div id="reviewHistory"></div>`;
      setTimeout(async () => { try { const rs = await api(`/api/v1/reviews/${ev.id}`);
        if (rs.length) $("reviewHistory").innerHTML = `<h4>Review history</h4>` + rs.map(r => `<div class="issue"><strong>${esc(r.decision)}</strong> by ${esc(r.reviewer_name)} <span class="meta">${esc(r.reviewed_at || "")}</span><div>${esc(r.notes || "")}</div></div>`).join("");
      } catch (e) {} }, 0);
    }
  }
  $("detailBody").innerHTML = html;
  $("detailModal").hidden = false;
};
window.evaluateOne = async function (cid) {
  try { await api("/api/v1/evaluations", { method: "POST", body: JSON.stringify({ conversation_id: cid }) }); toast("Evaluation complete"); await loadAll(); openDetail(cid); }
  catch (e) { toast("Error: " + e.message); }
};
window.submitReview = async function (evaluationId) {
  const name = $("reviewerName").value.trim(); if (!name) { toast("Please enter the reviewer name"); return; }
  try { await api(`/api/v1/reviews/${evaluationId}`, { method: "POST", body: JSON.stringify({ decision: $("reviewDecision").value, reviewer_name: name, notes: $("reviewNotes").value || null }) });
    toast("Review saved — the original evaluation is unchanged"); $("detailModal").hidden = true; await loadAll(); switchView("queue"); }
  catch (e) { toast("Error: " + e.message); }
};
window.togglePolicy = async function (id, enabled) {
  try { await api(`/api/v1/policies/${id}`, { method: "PUT", body: JSON.stringify({ enabled }) }); toast(enabled ? "Policy enabled" : "Policy disabled"); await loadAll(); }
  catch (e) { toast("Error: " + e.message); }
};
window.deletePolicy = async function (id) {
  try { await api(`/api/v1/policies/${id}`, { method: "DELETE" }); toast("Policy deleted"); await loadAll(); }
  catch (e) { toast("Error: " + e.message); }
};

/* ---------------- navigation + events ---------------- */
function switchView(name) {
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach(v => v.hidden = v.id !== "view-" + name);
}
document.querySelectorAll(".nav-btn").forEach(b => b.addEventListener("click", () => switchView(b.dataset.view)));
$("closeModal").addEventListener("click", () => $("detailModal").hidden = true);
$("detailModal").addEventListener("click", (e) => { if (e.target === $("detailModal")) $("detailModal").hidden = true; });
["searchInput", "statusFilter", "riskFilter"].forEach(id => $(id).addEventListener("input", renderConversations));
$("evalAllBtn").addEventListener("click", async () => { try { const r = await api("/api/v1/evaluations/bulk", { method: "POST", body: JSON.stringify({}) }); toast(`Evaluated ${r.length} conversation(s)`); await loadAll(); } catch (e) { toast("Error: " + e.message); } });
$("presetsBtn").addEventListener("click", async () => { try { const r = await api("/api/v1/policies/presets/apply", { method: "POST" }); toast(`Presets: ${r.created} created, ${r.skipped_existing} already existed`); await loadAll(); } catch (e) { toast("Error: " + e.message); } });
$("addPolicyBtn").addEventListener("click", async () => {
  const title = $("policyTitle").value.trim(), rule = $("policyRule").value.trim();
  if (title.length < 3 || rule.length < 5) { toast("Title (3+ chars) and rule text (5+ chars) are required"); return; }
  try { await api("/api/v1/policies", { method: "POST", body: JSON.stringify({ title, rule_text: rule }) }); $("policyTitle").value = ""; $("policyRule").value = ""; toast("Policy added"); await loadAll(); } catch (e) { toast("Error: " + e.message); }
});
$("seedBtn").addEventListener("click", async () => { try { const r = await api("/api/v1/demo/seed", { method: "POST" }); toast(`Demo data: ${r.imported} imported, ${r.evaluated} evaluated`); await loadAll(); switchView("overview"); } catch (e) { toast("Error: " + e.message); } });
$("csvFile").addEventListener("change", async (e) => { if (!e.target.files[0]) return; try { const r = await apiUpload("/api/v1/conversations/upload", e.target.files[0]); toast(`CSV: ${r.imported} imported, ${r.duplicates_skipped} duplicates, ${r.failed} failed`); await loadAll(); } catch (err) { toast("Error: " + err.message); } });
$("jsonFile").addEventListener("change", async (e) => { if (!e.target.files[0]) return; try { const r = await apiUpload("/api/v1/conversations/upload-json", e.target.files[0]); toast(`JSON: ${r.imported} imported, ${r.duplicates_skipped} duplicates, ${r.failed} failed`); await loadAll(); } catch (err) { toast("Error: " + err.message); } });
$("themeBtn").addEventListener("click", () => { const dark = document.documentElement.classList.toggle("dark"); $("themeBtn").textContent = dark ? "☀️ Light" : "🌙 Dark"; localStorage.setItem("trustops_theme", dark ? "dark" : "light"); });
if (localStorage.getItem("trustops_theme") === "dark") { document.documentElement.classList.add("dark"); $("themeBtn").textContent = "☀️ Light"; }
$("logoutBtn").addEventListener("click", () => { localStorage.removeItem("trustops_key"); location.reload(); });

/* ---------------- boot / login ---------------- */
async function enterApp() {
  $("loginView").hidden = true; $("appView").hidden = false;
  try { await loadAll(); } catch (e) { toast("Could not load data: " + e.message); }
}
$("connectBtn").addEventListener("click", async () => {
  const key = $("apiKeyInput").value.trim(); if (!key) { $("loginError").textContent = "Paste your API key, or create a demo workspace."; return; }
  state.key = key;
  try { await api("/api/v1/settings"); localStorage.setItem("trustops_key", key); enterApp(); }
  catch (e) { $("loginError").textContent = "That key did not work (" + e.message + "). Check the key and that the backend is running."; }
});
$("demoBtn").addEventListener("click", async () => {
  try {
    $("demoBtn").textContent = "Creating…";
    const res = await fetch("/api/v1/businesses", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "Demo Business" }) });
    if (!res.ok) throw new Error("business creation failed");
    const biz = await res.json(); state.key = biz.api_key; localStorage.setItem("trustops_key", state.key);
    await api("/api/v1/demo/seed", { method: "POST" });
    enterApp(); toast("Demo workspace ready — explore Overview, Conversations and the Review Queue");
  } catch (e) { $("loginError").textContent = "Demo setup failed: " + e.message; $("demoBtn").textContent = "Create demo workspace (1 click)"; }
});
if (DEMO) { $("loginView").hidden = true; $("appView").hidden = false; loadAll(); const foot = document.querySelector(".sidebar-foot"); if (foot) foot.insertAdjacentHTML("afterbegin", '<div class="badge" style="background:#b45309">Preview · demo data</div>'); }
else if (state.key) { enterApp(); }
else { $("loginView").hidden = false; }
