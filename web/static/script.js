/**
 * Topic Radar — Frontend v2
 *
 * SSE event types received from /api/stream:
 *   {type:"token",      text:"..."}      → append to live stream box
 *   {type:"source",     data:{...}}      → add chip to sources card
 *   {type:"structured", data:{...}}      → populate all summary cards
 *   {type:"history_id", id:123}          → refresh history sidebar
 *   {type:"error",      message:"..."}   → show error
 *   "[DONE]"                             → close stream
 */

"use strict";

// ── DOM refs ────────────────────────────────────────────────────────────────
const searchForm     = document.getElementById("search-form");
const topicInput     = document.getElementById("topic-input");
const searchBtn      = document.getElementById("search-btn");
const statusBar      = document.getElementById("status-bar");
const dashboard      = document.getElementById("dashboard");
const streamBox      = document.getElementById("stream-box");
const streamSpinner  = document.getElementById("stream-spinner");
const overviewText   = document.getElementById("overview-text");
const keypointsList  = document.getElementById("keypoints-list");
const trendsText     = document.getElementById("trends-text");
const gapsText       = document.getElementById("gaps-text");
const sourceList     = document.getElementById("source-list");
const historyList    = document.getElementById("history-list");
const refreshBtn     = document.getElementById("refresh-history");

let activeES = null;   // current EventSource

// ── Search submit ────────────────────────────────────────────────────────────
searchForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const topic = topicInput.value.trim();
  if (!topic) return;
  startResearch(topic);
});

function startResearch(topic) {
  if (activeES) { activeES.close(); activeES = null; }

  resetDashboard();
  dashboard.hidden = false;
  setStatus(`Researching "${topic}"…`, "spinner");
  setLoading(true);

  const url = `/api/stream?topic=${encodeURIComponent(topic)}`;
  activeES = new EventSource(url);

  activeES.onmessage = (e) => {
    if (e.data === "[DONE]") {
      activeES.close();
      activeES = null;
      streamSpinner.style.display = "none";
      setStatus("Done.", "success");
      setLoading(false);
      return;
    }

    let msg;
    try { msg = JSON.parse(e.data); }
    catch { return; }

    switch (msg.type) {
      case "token":
        streamBox.textContent += msg.text;
        streamBox.scrollTop = streamBox.scrollHeight;
        break;

      case "source":
        appendSource(msg.data);
        break;

      case "structured":
        populateCards(msg.data);
        // Hide live stream box now that cards are filled
        document.getElementById("card-stream").style.opacity = "0.4";
        break;

      case "history_id":
        loadHistory();
        break;

      case "error":
        setStatus(`Error: ${msg.message}`, "error");
        activeES.close();
        activeES = null;
        streamSpinner.style.display = "none";
        setLoading(false);
        break;
    }
  };

  activeES.onerror = () => {
    setStatus("Connection lost. Please try again.", "error");
    activeES.close();
    activeES = null;
    streamSpinner.style.display = "none";
    setLoading(false);
  };
}

// ── Card population ──────────────────────────────────────────────────────────
function populateCards(summary) {
  overviewText.textContent = summary.overview || "";

  keypointsList.innerHTML = "";
  (summary.key_points || []).forEach((pt) => {
    const li = document.createElement("li");
    li.textContent = pt;
    keypointsList.appendChild(li);
  });

  trendsText.textContent = summary.trends || "";
  gapsText.textContent   = summary.gaps_and_caveats || "";

  // If sources came via structured output (in case SSE sources were missed)
  if (summary.sources && summary.sources.length) {
    sourceList.innerHTML = "";
    summary.sources.forEach(appendSource);
  }
}

function appendSource(src) {
  // Avoid duplicate chips
  if (document.querySelector(`[data-url="${CSS.escape(src.url)}"]`)) return;

  const li = document.createElement("li");
  li.dataset.url = src.url;
  li.innerHTML = `
    <a href="${esc(src.url)}" target="_blank" rel="noopener"
       title="${esc(src.title)}">${esc(src.title || src.url)}</a>
    ${src.snippet ? `<div class="src-snippet">${esc(src.snippet)}</div>` : ""}
  `;
  sourceList.appendChild(li);
}

// ── History sidebar ──────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    const entries = await res.json();

    historyList.innerHTML = "";

    if (!entries.length) {
      historyList.innerHTML = '<li class="history-empty">No searches yet.</li>';
      return;
    }

    entries.forEach((entry) => {
      const li = document.createElement("li");
      li.className = "history-item";
      li.innerHTML = `
        <div class="h-topic" title="${esc(entry.topic)}">${esc(entry.topic)}</div>
        <div class="h-date">${formatDate(entry.created_at)}</div>
      `;
      li.addEventListener("click", () => loadHistoryEntry(entry.id, li));
      historyList.appendChild(li);
    });
  } catch (err) {
    console.error("Failed to load history:", err);
  }
}

async function loadHistoryEntry(id, itemEl) {
  // Mark active
  document.querySelectorAll(".history-item").forEach((el) => el.classList.remove("active"));
  if (itemEl) itemEl.classList.add("active");

  try {
    const res = await fetch(`/api/history/${id}`);
    if (!res.ok) throw new Error("Not found");
    const entry = await res.json();

    topicInput.value = entry.topic;
    resetDashboard();
    dashboard.hidden = false;
    document.getElementById("card-stream").style.opacity = "1";
    streamBox.textContent = "(loaded from history)";
    populateCards(entry.summary);
    setStatus(`Loaded: "${entry.topic}"`, "success");
  } catch (err) {
    setStatus("Failed to load history entry.", "error");
  }
}

// Load history on page boot
loadHistory();
refreshBtn.addEventListener("click", loadHistory);

// ── Helpers ──────────────────────────────────────────────────────────────────
function resetDashboard() {
  overviewText.textContent  = "";
  keypointsList.innerHTML   = "";
  trendsText.textContent    = "";
  gapsText.textContent      = "";
  sourceList.innerHTML      = "";
  streamBox.textContent     = "";
  statusBar.textContent     = "";
  statusBar.className       = "status-bar";
  streamSpinner.style.display = "inline-block";
  document.getElementById("card-stream").style.opacity = "1";
}

function setStatus(msg, type = "") {
  statusBar.innerHTML = type === "spinner"
    ? `<span class="spinner" style="margin-right:6px"></span>${esc(msg)}`
    : esc(msg);
  statusBar.className = `status-bar ${type === "spinner" ? "" : type}`;
}

function setLoading(on) {
  searchBtn.disabled   = on;
  topicInput.disabled  = on;
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

function esc(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
