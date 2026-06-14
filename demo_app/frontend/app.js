const state = {
  schema: null,
  evaluations: [],
  manualFilters: [],
  manualDisplayColumns: [],
  manualPage: 1,
  aiPage: 1,
  manualSort: { column: null, dir: "asc" },
  aiSort: { column: null, dir: "asc" },
  manualPageSort: { column: null, dir: "asc" },
  aiPageSort: { column: null, dir: "asc" },
  lastManualResult: null,
  lastAiResult: null,
  aiMethod: "rag",
  lastManualPayload: null,
  lastAiPayload: null,
  activeView: "sql",
  manualSqlExpanded: false,
  progressStartedAt: null,
  progressStepIndex: 0,
  progressSteps: [],
  progressStatusText: null,
  progressStepTimer: null,
  progressElapsedTimer: null,
};

const $ = (id) => document.getElementById(id);

const SPAN_COLORS = [
  { bg: "#e5f0ff", border: "#6b9ee8", text: "#173f73" },
  { bg: "#fff0c7", border: "#d49b16", text: "#5c3c00" },
  { bg: "#e4f7ec", border: "#55b77a", text: "#195b35" },
  { bg: "#f3e8ff", border: "#a978dd", text: "#4d2478" },
  { bg: "#ffe4dc", border: "#e07d5f", text: "#762d1c" },
  { bg: "#dff7f6", border: "#4eb6b2", text: "#125451" },
  { bg: "#fde6f1", border: "#dc6fa5", text: "#722447" },
  { bg: "#e9edd4", border: "#93a947", text: "#3f4d14" },
  { bg: "#ece7df", border: "#a68b6d", text: "#4d3c2a" },
  { bg: "#e3e8f6", border: "#7389c4", text: "#283965" },
  { bg: "#f4e4d7", border: "#c2824a", text: "#653918" },
  { bg: "#e6e6e6", border: "#8a8f96", text: "#30343a" },
];

function spanColor(spanId) {
  const match = String(spanId || "").match(/\d+/);
  const index = match ? (Number(match[0]) - 1) % SPAN_COLORS.length : SPAN_COLORS.length - 1;
  return SPAN_COLORS[index];
}

function spanStyle(spanId, { leftBorder = false } = {}) {
  if (!spanId) return "";
  const color = spanColor(spanId);
  const borderProp = leftBorder ? "border-left-color" : "border-color";
  return `background:${color.bg};${borderProp}:${color.border};color:${color.text};`;
}

function aiProgressSteps(method) {
  const steps = [
    "Extracting potential entity spans",
    "Embedding spans and finding database candidates",
    "Selecting extracted database entities",
  ];
  if (isKgMethod(method)) {
    steps.push("Expanding related KG entities");
  }
  steps.push("Generating SQL from resolved scope", "Running SQL and rendering results");
  return steps;
}

function isKgMethod(method) {
  return method === "full_kg_rag";
}

function elapsedSeconds() {
  if (!state.progressStartedAt) return "0.0";
  return ((performance.now() - state.progressStartedAt) / 1000).toFixed(1);
}

function renderAiProgress(statusText) {
  const progress = $("aiProgress");
  const status = $("aiProgressStatus");
  const elapsed = $("aiElapsed");
  const list = $("aiProgressSteps");
  progress.classList.remove("hidden");
  status.textContent = statusText || state.progressStatusText || state.progressSteps[state.progressStepIndex] || "Working";
  elapsed.textContent = `${elapsedSeconds()}s`;
  list.innerHTML = state.progressSteps
    .map((step, index) => {
      const cls =
        index < state.progressStepIndex
          ? "done"
          : index === state.progressStepIndex
            ? "active"
            : "pending";
      return `<li class="${cls}"><span class="step-dot"></span><span>${escapeHtml(step)}</span></li>`;
    })
    .join("");
}

function stopAiProgressTimers() {
  if (state.progressStepTimer) {
    clearInterval(state.progressStepTimer);
    state.progressStepTimer = null;
  }
  if (state.progressElapsedTimer) {
    clearInterval(state.progressElapsedTimer);
    state.progressElapsedTimer = null;
  }
}

function startAiProgress(method, { autoAdvance = true } = {}) {
  stopAiProgressTimers();
  state.progressStartedAt = performance.now();
  state.progressStepIndex = 0;
  state.progressSteps = aiProgressSteps(method);
  state.progressStatusText = null;
  $("aiProgress").classList.remove("failed", "complete");
  renderAiProgress();
  state.progressElapsedTimer = setInterval(() => renderAiProgress(), 100);
  if (autoAdvance) {
    state.progressStepTimer = setInterval(() => {
      state.progressStepIndex = Math.min(state.progressStepIndex + 1, state.progressSteps.length - 1);
      renderAiProgress();
    }, 2300);
  }
}

function setAiProgressStep(stepIndex, statusText) {
  if (Number.isInteger(stepIndex)) {
    state.progressStepIndex = Math.max(0, Math.min(stepIndex, state.progressSteps.length - 1));
  }
  if (statusText) {
    state.progressStatusText = statusText;
  }
  renderAiProgress();
}

function finishAiProgress(success) {
  stopAiProgressTimers();
  state.progressStepIndex = success ? state.progressSteps.length : state.progressStepIndex;
  state.progressStatusText = null;
  renderAiProgress(success ? `Complete in ${elapsedSeconds()}s` : `Stopped after ${elapsedSeconds()}s`);
  $("aiProgress").classList.toggle("failed", !success);
  $("aiProgress").classList.toggle("complete", success);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 3200);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function sortLabel(column, sortState) {
  if (!sortState || sortState.column !== column) return "";
  return sortState.dir === "desc" ? "↓" : "↑";
}

function applySort(sortState, column) {
  if (sortState.column === column) {
    sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
  } else {
    sortState.column = column;
    sortState.dir = "asc";
  }
}

function compareCellValues(a, b) {
  if (a === b) return 0;
  if (a === null || a === undefined) return 1;
  if (b === null || b === undefined) return -1;
  const aNum = Number(a);
  const bNum = Number(b);
  if (Number.isFinite(aNum) && Number.isFinite(bNum) && String(a).trim() !== "" && String(b).trim() !== "") {
    return aNum - bNum;
  }
  return String(a).localeCompare(String(b), "cs", { numeric: true, sensitivity: "base" });
}

function sortedPageRows(rows, pageSortState) {
  if (!pageSortState?.column) return rows;
  const direction = pageSortState.dir === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => direction * compareCellValues(a[pageSortState.column], b[pageSortState.column]));
}

function optionValue(option) {
  if (option && typeof option === "object" && Object.prototype.hasOwnProperty.call(option, "value")) {
    return String(option.value);
  }
  return String(option);
}

function optionLabel(option) {
  if (option && typeof option === "object" && Object.prototype.hasOwnProperty.call(option, "label")) {
    return String(option.label);
  }
  return optionValue(option);
}

function foldSearchText(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function optionSearchText(option) {
  return foldSearchText(`${optionValue(option)} ${optionLabel(option)}`);
}

function applyValueSearch(rowEl, query) {
  const terms = foldSearchText(query).split(/\s+/).filter(Boolean);
  let visibleCount = 0;
  rowEl.querySelectorAll(".value-option").forEach((optionEl) => {
    const haystack = optionEl.dataset.searchText || "";
    const matches = terms.every((term) => haystack.includes(term));
    optionEl.classList.toggle("hidden", !matches);
    if (matches) visibleCount += 1;
  });
  const empty = rowEl.querySelector(".value-options-empty");
  if (empty) empty.classList.toggle("hidden", visibleCount > 0);
}

function schemaColumn(columnName) {
  return state.schema?.columns?.find((column) => column.name === columnName);
}

function displayValueForColumn(columnName, value) {
  const column = schemaColumn(columnName);
  const match = (column?.values || []).find((option) => optionValue(option) === String(value));
  return match ? optionLabel(match) : String(value);
}

function renderTable(targetId, result, options = {}) {
  const { pageSortState = null, tableSortState = null, onPageSort = null, onTableSort = null } = options;
  const target = $(targetId);
  if (!result || !result.rows) {
    target.innerHTML = "";
    return;
  }
  if (!result.rows.length) {
    target.innerHTML = `<div class="muted">No rows returned.</div>`;
    return;
  }
  const headers = result.columns;
  const rows = sortedPageRows(result.rows, pageSortState);
  const html = `
    <div class="table-wrap">
      <table>
        <thead><tr>${headers
          .map((h) => {
            if (!onPageSort && !onTableSort) return `<th>${escapeHtml(h)}</th>`;
            const pageActive = pageSortState?.column === h ? " active" : "";
            const tableActive = tableSortState?.column === h ? " active" : "";
            return `
              <th>
                <div class="table-header-controls">
                  <button class="sort-header${pageActive}" data-column="${escapeHtml(h)}" title="Sort visible page">${escapeHtml(h)}<span>${sortLabel(h, pageSortState)}</span></button>
                  <button class="whole-sort-header${tableActive}" data-column="${escapeHtml(h)}" title="Sort all rows before pagination">${sortLabel(h, tableSortState) || "↕"}</button>
                </div>
              </th>`;
          })
          .join("")}</tr></thead>
        <tbody>
          ${rows
            .map(
              (row) =>
                `<tr>${headers.map((h) => `<td>${escapeHtml(row[h])}</td>`).join("")}</tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>`;
  target.innerHTML = html;
  if (onPageSort) {
    target.querySelectorAll(".sort-header").forEach((button) => {
      button.addEventListener("click", () => onPageSort(button.dataset.column));
    });
  }
  if (onTableSort) {
    target.querySelectorAll(".whole-sort-header").forEach((button) => {
      button.addEventListener("click", () => onTableSort(button.dataset.column));
    });
  }
}

function renderPager(targetId, result, onPage) {
  const target = $(targetId);
  if (!result) {
    target.innerHTML = "";
    return;
  }
  target.innerHTML = `
    <div>Page ${result.page} of ${result.total_pages} · ${result.total_rows} rows</div>
    <div class="pager-buttons">
      <button ${result.page <= 1 ? "disabled" : ""} data-dir="-1">Previous</button>
      <button ${result.page >= result.total_pages ? "disabled" : ""} data-dir="1">Next</button>
    </div>`;
  target.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => onPage(result.page + Number(btn.dataset.dir)));
  });
}

function renderChips(targetId, items) {
  const target = $(targetId);
  if (!items || !items.length) {
    target.classList.add("muted");
    target.textContent = "None.";
    return;
  }
  target.classList.remove("muted");
  target.innerHTML = items
    .map((item) => {
      const text =
        typeof item === "string"
          ? item
          : `${item.kind || item.column}: ${item.label || item.value || item.values?.join(", ")}`;
      const spanId = item.source_span_id || item.span_id;
      const spanBadge = spanId ? `<span class="span-badge">${escapeHtml(spanId)}</span>` : "";
      const title = item.source_span ? ` title="From span: ${escapeHtml(item.source_span)}"` : "";
      return `<span class="chip linked-chip" style="${spanStyle(spanId)}"${title}>${spanBadge}${escapeHtml(text)}</span>`;
    })
    .join("");
}

function highlightQuery(question, spans) {
  const ranges = [];
  for (const span of spans || []) {
    let start = Number.isInteger(span.start) ? span.start : -1;
    let end = Number.isInteger(span.end) ? span.end : -1;
    const text = String(span.text || "");
    if ((start < 0 || end <= start || question.slice(start, end) !== text) && text) {
      const idx = question.toLowerCase().indexOf(text.toLowerCase());
      if (idx >= 0) {
        start = idx;
        end = idx + text.length;
      }
    }
    if (start >= 0 && end > start && end <= question.length) {
      ranges.push({ start, end, kind: span.kind || "entity", id: span.id });
    }
  }
  const cleanRanges = ranges
    .sort((a, b) => a.start - b.start || b.end - a.end)
    .filter((range, index, all) => !all.slice(0, index).some((prev) => range.start < prev.end));
  if (!cleanRanges.length) return escapeHtml(question);
  let html = "";
  let cursor = 0;
  for (const range of cleanRanges) {
    html += escapeHtml(question.slice(cursor, range.start));
    const title = `${range.id ? `${range.id} · ` : ""}${range.kind}`;
    html += `<mark class="span-mark" style="${spanStyle(range.id)}" title="${escapeHtml(title)}">${escapeHtml(question.slice(range.start, range.end))}</mark>`;
    cursor = range.end;
  }
  html += escapeHtml(question.slice(cursor));
  return html;
}

function renderArtifacts(groups) {
  const target = $("retrievalArtifacts");
  if (!groups || !groups.length) {
    target.innerHTML = "No evidence.";
    return;
  }
  const byScoreDesc = (a, b) => Number(b.score ?? -Infinity) - Number(a.score ?? -Infinity);
  target.innerHTML = groups
    .map(
      (group) => `
      <div>
        <h3>${escapeHtml(group.title)}</h3>
        ${(group.items || [])
          .slice()
          .sort(byScoreDesc)
          .map(
            (item) => `
            <div class="evidence-item" style="${spanStyle(item.source_span_id, { leftBorder: true })}">
              <strong>${escapeHtml(item.doc_type || item.node_type || item.label || "evidence")}</strong>
              ${item.score !== undefined ? `<span> · score ${item.score}</span>` : ""}
              <div>${escapeHtml(item.text || item.label || "")}</div>
            </div>`
          )
          .join("")}
      </div>`
    )
    .join("");
}

function drawKgGraph(graph) {
  const svg = $("kgGraph");
  const details = $("kgDetails");
  svg.innerHTML = "";
  if (!graph || !graph.nodes || !graph.nodes.length) {
    svg.innerHTML = `<text x="24" y="42" fill="#68727f">No KG subgraph for this method.</text>`;
    if (details) {
      details.classList.add("muted");
      details.textContent = "No KG relation selected.";
    }
    return;
  }
  const width = svg.clientWidth || 720;
  const height = svg.clientHeight || 420;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const nodes = graph.nodes.slice(0, 80).map((node, i) => ({ ...node, i, vx: 0, vy: 0 }));
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const edges = (graph.edges || [])
    .filter((edge) => nodeMap.has(edge.source) && nodeMap.has(edge.target))
    .slice(0, 120)
    .map((edge, i) => ({ ...edge, i }));
  const adjacency = new Map(nodes.map((node) => [node.id, []]));
  edges.forEach((edge) => {
    adjacency.get(edge.source)?.push({ edge, other: edge.target });
    adjacency.get(edge.target)?.push({ edge, other: edge.source });
  });
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) * 0.34;
  const cols = Math.max(1, Math.ceil(Math.sqrt(nodes.length)));
  nodes.forEach((node, i) => {
    const row = Math.floor(i / cols);
    const col = i % cols;
    const gridX = (col - (cols - 1) / 2) * Math.min(110, width / (cols + 1));
    const gridY = (row - (Math.ceil(nodes.length / cols) - 1) / 2) * 76;
    const angle = (2 * Math.PI * i) / Math.max(1, nodes.length);
    node.x = centerX + gridX * 0.65 + Math.cos(angle) * radius * 0.2;
    node.y = centerY + gridY * 0.65 + Math.sin(angle) * radius * 0.2;
    node.r = node.highlight ? 13 : 9;
    node.collision = node.highlight ? 42 : 34;
  });
  for (let iteration = 0; iteration < 260; iteration += 1) {
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i];
        const b = nodes[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let dist = Math.hypot(dx, dy) || 0.01;
        const force = Math.min(2.4, 1800 / (dist * dist));
        dx /= dist;
        dy /= dist;
        a.vx -= dx * force;
        a.vy -= dy * force;
        b.vx += dx * force;
        b.vy += dy * force;
      }
    }
    for (const edge of edges) {
      const source = nodeMap.get(edge.source);
      const target = nodeMap.get(edge.target);
      let dx = target.x - source.x;
      let dy = target.y - source.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const desired = source.highlight || target.highlight ? 86 : 112;
      const pull = (dist - desired) * 0.018;
      dx /= dist;
      dy /= dist;
      source.vx += dx * pull;
      source.vy += dy * pull;
      target.vx -= dx * pull;
      target.vy -= dy * pull;
    }
    for (const node of nodes) {
      node.vx += (centerX - node.x) * 0.004;
      node.vy += (centerY - node.y) * 0.004;
      node.x += node.vx;
      node.y += node.vy;
      node.vx *= 0.72;
      node.vy *= 0.72;
      node.x = Math.max(32, Math.min(width - 32, node.x));
      node.y = Math.max(32, Math.min(height - 42, node.y));
    }
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i];
        const b = nodes[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 0.01;
        const minDist = a.collision + b.collision;
        if (dist < minDist) {
          const push = (minDist - dist) / 2;
          dx /= dist;
          dy /= dist;
          a.x -= dx * push;
          a.y -= dy * push;
          b.x += dx * push;
          b.y += dy * push;
        }
      }
    }
  }
  const edgeMetric = (edge) => {
    const props = edge.properties || {};
    for (const key of ["profile_similarity", "cosine_similarity", "lift", "weighted_support"]) {
      if (props[key] !== undefined) return `${key}: ${props[key]}`;
    }
    return "";
  };
  const nodeName = (id) => nodeMap.get(id)?.label || id;
  const relationLine = (edge) => {
    const metric = edgeMetric(edge);
    return `${nodeName(edge.source)} — ${edge.type} — ${nodeName(edge.target)}${metric ? ` (${metric})` : ""}`;
  };
  const renderDetails = (html) => {
    if (!details) return;
    details.classList.remove("muted");
    details.innerHTML = html;
  };
  const clearDetails = () => {
    if (!details) return;
    details.classList.add("muted");
    details.textContent = "No KG relation selected.";
  };
  const edgeLines = new Map();
  const nodeGroups = new Map();
  const setHighlight = (nodeIds, edgeIds) => {
    nodeGroups.forEach((group, id) => {
      const active = nodeIds.has(id);
      group.classList.toggle("related", active);
      group.classList.toggle("dimmed", !active);
    });
    edgeLines.forEach((line, id) => {
      const active = edgeIds.has(id);
      line.classList.toggle("related", active);
      line.classList.toggle("dimmed", !active);
    });
  };
  const clearHighlight = () => {
    nodeGroups.forEach((group) => group.classList.remove("related", "dimmed"));
    edgeLines.forEach((line) => line.classList.remove("related", "dimmed"));
    clearDetails();
  };
  for (const edge of edges) {
    const s = nodeMap.get(edge.source);
    const t = nodeMap.get(edge.target);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", s.x);
    line.setAttribute("y1", s.y);
    line.setAttribute("x2", t.x);
    line.setAttribute("y2", t.y);
    line.setAttribute("class", "kg-edge");
    edgeLines.set(edge.i, line);
    svg.appendChild(line);
  }
  for (const node of nodes) {
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", "kg-node");
    group.setAttribute("tabindex", "0");
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", node.r);
    circle.setAttribute("class", node.highlight ? "seed" : node.expanded ? "expanded" : "");
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${node.label} (${node.type})`;
    circle.appendChild(title);
    group.appendChild(circle);
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", node.x);
    text.setAttribute("y", node.y + node.r + 14);
    text.setAttribute("text-anchor", "middle");
    text.textContent = String(node.code || node.label).slice(0, 18);
    group.appendChild(text);
    group.addEventListener("mouseenter", () => {
      const relatedEdges = adjacency.get(node.id) || [];
      const edgeIds = new Set(relatedEdges.map((item) => item.edge.i));
      const nodeIds = new Set([node.id, ...relatedEdges.map((item) => item.other)]);
      setHighlight(nodeIds, edgeIds);
      renderDetails(`
        <div class="kg-detail-title">${escapeHtml(node.label)}</div>
        <div class="kg-detail-meta">${escapeHtml(node.type)}${node.code ? ` · ${escapeHtml(node.code)}` : ""}</div>
        <ul class="kg-relation-list">
          ${relatedEdges
            .slice(0, 14)
            .map((item) => `<li>${escapeHtml(relationLine(item.edge))}</li>`)
            .join("")}
          ${relatedEdges.length > 14 ? `<li>${relatedEdges.length - 14} more relations</li>` : ""}
        </ul>
      `);
    });
    group.addEventListener("mouseleave", clearHighlight);
    group.addEventListener("focus", () => group.dispatchEvent(new Event("mouseenter")));
    group.addEventListener("blur", clearHighlight);
    nodeGroups.set(node.id, group);
    svg.appendChild(group);
  }
  clearDetails();
}

async function loadHealth() {
  const health = await api("/api/health");
  $("dbStatus").innerHTML = `${health.database}<br>${health.standard_vectors.join(" × ")} standard vectors<br>${health.kg_vectors.join(" × ")} KG vectors`;
}

async function loadSchema() {
  const [schema, evaluations] = await Promise.all([
    api("/api/schema"),
    api("/api/evaluation-questions"),
  ]);
  state.schema = schema;
  state.evaluations = evaluations.questions || [];
  state.manualDisplayColumns = defaultManualDisplayColumns();
  renderEvaluationSelect();
  renderManualDisplayColumns();
  addFilterRow();
}

function renderEvaluationSelect() {
  const select = $("evaluationSelect");
  select.innerHTML = `
    <option value="">Custom question</option>
    ${state.evaluations
      .map((item) => {
        const label = `${item.id}: ${item.query_cs || item.query_en}`;
        return `<option value="${escapeHtml(item.id)}">${escapeHtml(label)}</option>`;
      })
      .join("")}`;
  updateEvaluationTranslation(null);
}

function updateEvaluationTranslation(item) {
  const translation = $("evaluationTranslation");
  const text = (item?.query_en || "").trim();
  if (!text) {
    translation.textContent = "";
    translation.classList.add("hidden");
    return;
  }
  translation.textContent = `English: ${text}`;
  translation.classList.remove("hidden");
}

function defaultManualDisplayColumns() {
  const defaults = state.schema?.default_result_columns || [];
  return defaults.length ? defaults : ["diagnosis"];
}

function renderManualDisplayColumns() {
  const container = $("manualDisplayColumns");
  const columns = state.schema?.result_columns || [];
  if (!columns.length) {
    container.innerHTML = "";
    return;
  }
  const selected = new Set(state.manualDisplayColumns);
  container.innerHTML = columns
    .map(
      (column) => `
        <label class="display-column-option">
          <input type="checkbox" value="${escapeHtml(column.name)}" ${selected.has(column.name) ? "checked" : ""} />
          <span>${escapeHtml(column.label || column.name)}</span>
        </label>`
    )
    .join("");
  container.querySelectorAll("input").forEach((input) => {
    input.addEventListener("change", () => {
      const values = [...container.querySelectorAll("input:checked")].map((item) => item.value);
      if (!values.length) {
        input.checked = true;
        toast("Select at least one shown column.");
        return;
      }
      state.manualDisplayColumns = values;
      state.manualSort = state.manualSort.column && values.includes(state.manualSort.column) ? state.manualSort : { column: null, dir: "asc" };
      state.manualPageSort = state.manualPageSort.column && values.includes(state.manualPageSort.column) ? state.manualPageSort : { column: null, dir: "asc" };
      clearManualResult();
    });
  });
}

function addFilterRow(columnName = state.schema?.columns?.[0]?.name) {
  const row = { column: columnName, values: [], search: "" };
  state.manualFilters.push(row);
  renderFilters();
  clearManualResult();
}

function renderFilters() {
  const container = $("manualFilters");
  const columns = state.schema?.columns || [];
  container.innerHTML = state.manualFilters
    .map((filter, index) => {
      const col = columns.find((c) => c.name === filter.column) || columns[0];
      return `
        <div class="filter-row" data-index="${index}">
          <select class="column-select">
            ${columns.map((c) => `<option value="${c.name}" ${c.name === filter.column ? "selected" : ""}>${escapeHtml(c.label)}</option>`).join("")}
          </select>
          <div class="value-picker">
            <input class="value-search" type="search" placeholder="Search values" value="${escapeHtml(filter.search || "")}" />
            <div class="value-options" role="group" aria-label="${escapeHtml(col?.label || "Values")} values">
              ${(col?.values || [])
                .map((option) => {
                  const value = optionValue(option);
                  const label = optionLabel(option);
                  return `
                    <label class="value-option" data-search-text="${escapeHtml(optionSearchText(option))}">
                      <input type="checkbox" value="${escapeHtml(value)}" ${filter.values.includes(value) ? "checked" : ""} />
                      <span>${escapeHtml(label)}</span>
                    </label>`;
                })
                .join("")}
              <div class="value-options-empty hidden">No matching values.</div>
            </div>
          </div>
          <button class="remove-filter" title="Remove filter">×</button>
        </div>`;
    })
    .join("");
  container.querySelectorAll(".filter-row").forEach((el) => {
    const index = Number(el.dataset.index);
    el.querySelector(".column-select").addEventListener("change", (event) => {
      state.manualFilters[index].column = event.target.value;
      state.manualFilters[index].values = [];
      state.manualFilters[index].search = "";
      clearManualResult();
      renderFilters();
    });
    el.querySelector(".value-search").addEventListener("input", (event) => {
      state.manualFilters[index].search = event.target.value;
      applyValueSearch(el, event.target.value);
    });
    el.querySelectorAll(".value-option input").forEach((input) => {
      input.addEventListener("change", () => {
        const values = new Set(state.manualFilters[index].values);
        if (input.checked) {
          values.add(input.value);
        } else {
          values.delete(input.value);
        }
        state.manualFilters[index].values = [...values];
        renderManualArtifacts();
        clearManualResult();
      });
    });
    el.querySelector(".remove-filter").addEventListener("click", () => {
      state.manualFilters.splice(index, 1);
      renderFilters();
      renderManualArtifacts();
      clearManualResult();
    });
    applyValueSearch(el, state.manualFilters[index].search || "");
  });
  renderManualArtifacts();
}

function renderManualArtifacts() {
  const artifacts = state.manualFilters
    .filter((filter) => filter.values.length)
    .map((filter) => ({
      kind: schemaColumn(filter.column)?.label || filter.column,
      label: filter.values.map((value) => displayValueForColumn(filter.column, value)).join(", "),
    }));
  renderChips("manualArtifacts", artifacts);
}

function clearManualResult() {
  state.lastManualResult = null;
  state.manualSqlExpanded = false;
  $("manualResultPanel").classList.add("hidden");
  updateManualSqlVisibility();
  $("manualSql").textContent = "";
  $("manualTable").innerHTML = "";
  $("manualPager").innerHTML = "";
}

function updateManualSqlVisibility() {
  const sqlBox = $("manualSql");
  const toggle = $("toggleManualSql");
  if (!sqlBox || !toggle) return;
  sqlBox.classList.toggle("hidden", !state.manualSqlExpanded);
  toggle.textContent = state.manualSqlExpanded ? "Hide SQL" : "Show SQL";
  toggle.setAttribute("aria-expanded", String(state.manualSqlExpanded));
}

function renderManualResult(result) {
  state.lastManualResult = result;
  if (result.sql) {
    $("manualResultPanel").classList.remove("hidden");
  }
  $("manualSql").textContent = result.sql;
  updateManualSqlVisibility();
  renderTable("manualTable", result, {
    pageSortState: state.manualPageSort,
    tableSortState: state.manualSort,
    onPageSort: (column) => {
      applySort(state.manualPageSort, column);
      renderManualResult(state.lastManualResult);
    },
    onTableSort: (column) => {
      applySort(state.manualSort, column);
      runManual(1).catch((e) => toast(e.message));
    },
  });
  renderPager("manualPager", result, (nextPage) => runManual(nextPage));
  renderChips(
    "manualArtifacts",
    (result.artifacts || []).map((a) => ({
      kind: a.label,
      label: (a.values || []).map((value) => displayValueForColumn(a.column, value)).join(", "),
    }))
  );
}

async function runManual(page = 1) {
  if (!state.manualDisplayColumns.length) {
    toast("Select at least one shown column.");
    return;
  }
  const filters = {};
  for (const filter of state.manualFilters) {
    if (filter.values.length) filters[filter.column] = filter.values;
  }
  state.lastManualPayload = { filters, display_columns: state.manualDisplayColumns, page, page_size: 100 };
  if (state.manualSort.column) {
    state.lastManualPayload.sort_by = state.manualSort.column;
    state.lastManualPayload.sort_dir = state.manualSort.dir;
  }
  const result = await api("/api/manual/query", {
    method: "POST",
    body: JSON.stringify(state.lastManualPayload),
  });
  state.manualSqlExpanded = false;
  renderManualResult(result);
}

function resetAiRunArtifacts(question) {
  state.lastAiResult = null;
  $("aiSql").textContent = "Generating SQL...";
  $("highlightedQuery").innerHTML = escapeHtml(question);
  $("entityChips").classList.add("muted");
  $("entityChips").textContent = "Extracting database entities...";
  $("normalizedQuery").textContent = "Resolving database scope...";
  $("retrievalArtifacts").textContent = "Waiting for retrieval evidence...";
  $("aiTable").innerHTML = "";
  $("aiPager").innerHTML = "";
  drawKgGraph({ nodes: [], edges: [] });
}

function renderAiStreamEvent(event, question) {
  setAiProgressStep(event.step_index, event.status);
  if (event.event === "spans") {
    $("highlightedQuery").innerHTML = highlightQuery(question, event.spans || []);
  } else if (event.event === "artifacts") {
    renderArtifacts(event.artifacts || []);
  } else if (event.event === "entities") {
    renderChips("entityChips", event.database_entities || []);
  } else if (event.event === "kg_entities") {
    renderArtifacts(event.artifacts || []);
    drawKgGraph(event.kg_subgraph || { nodes: [], edges: [] });
  } else if (event.event === "scope") {
    if (event.sql) $("aiSql").textContent = event.sql;
    $("normalizedQuery").innerHTML = escapeHtml(event.normalized_question || "").replace(
      /(diagnosis_code|mkn_block_code|reported_case_count)/g,
      "<mark>$1</mark>"
    );
    renderArtifacts(event.artifacts || []);
  } else if (event.event === "result" && event.result) {
    renderAiResult(event.result);
  } else if (event.event === "error") {
    throw new Error(event.message || event.status || "AI query failed.");
  }
}

async function streamAiQuery(payload, question) {
  const response = await fetch("/api/ai/query/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  if (!response.body) {
    const result = await api("/api/ai/query", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderAiResult(result);
    return result;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      renderAiStreamEvent(event, question);
      if (event.event === "result") finalResult = event.result;
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    const event = JSON.parse(buffer);
    renderAiStreamEvent(event, question);
    if (event.event === "result") finalResult = event.result;
  }
  if (!finalResult) throw new Error("AI query stream ended before returning results.");
  return finalResult;
}

function renderAiResult(result) {
  state.lastAiResult = result;
  $("aiSql").textContent = result.sql;
  renderChips("entityChips", result.database_entities || result.entities);
  $("highlightedQuery").innerHTML = highlightQuery(result.question, result.extracted_spans);
  $("normalizedQuery").innerHTML = escapeHtml(result.normalized_question).replace(/(diagnosis_code|mkn_block_code|reported_case_count)/g, "<mark>$1</mark>");
  renderArtifacts(result.artifacts);
  drawKgGraph(result.kg_subgraph);
  renderTable("aiTable", result, {
    pageSortState: state.aiPageSort,
    tableSortState: state.aiSort,
    onPageSort: (column) => {
      applySort(state.aiPageSort, column);
      renderAiResult(state.lastAiResult);
    },
    onTableSort: (column) => {
      applySort(state.aiSort, column);
      runAi(1).catch((e) => toast(e.message));
    },
  });
  renderPager("aiPager", result, (nextPage) => runAi(nextPage));
}

async function runAi(page = 1) {
  const question = $("questionInput").value.trim();
  if (!question) {
    toast("Enter a question first.");
    return;
  }
  state.lastAiPayload = { question, method: state.aiMethod, page, page_size: 100 };
  if (state.aiSort.column) {
    state.lastAiPayload.sort_by = state.aiSort.column;
    state.lastAiPayload.sort_dir = state.aiSort.dir;
  }
  $("runAi").disabled = true;
  $("runAi").textContent = "Running...";
  resetAiRunArtifacts(question);
  startAiProgress(state.aiMethod, { autoAdvance: false });
  let success = false;
  try {
    await streamAiQuery(state.lastAiPayload, question);
    success = true;
  } catch (error) {
    finishAiProgress(false);
    throw error;
  } finally {
    if (success) finishAiProgress(true);
    $("runAi").disabled = false;
    $("runAi").textContent = "Run AI scope builder";
  }
}

function setResultView(view) {
  state.activeView = view;
  document.querySelectorAll(".mini-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  $("sqlView").classList.toggle("hidden", view !== "sql");
  $("kgView").classList.toggle("hidden", view !== "kg");
}

function updateResultViewForMethod() {
  const kgButton = document.querySelector('[data-view="kg"]');
  const hasKg = isKgMethod(state.aiMethod);
  kgButton.classList.toggle("hidden", !hasKg);
  setResultView(hasKg ? "kg" : "sql");
}

function bindUi() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-button").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      button.classList.add("active");
      $(`${button.dataset.tab}Tab`).classList.add("active");
    });
  });
  document.querySelectorAll(".segment").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".segment").forEach((b) => b.classList.remove("active"));
      button.classList.add("active");
      state.aiMethod = button.dataset.method;
      updateResultViewForMethod();
    });
  });
  document.querySelectorAll(".mini-tab").forEach((button) => {
    button.addEventListener("click", () => {
      setResultView(button.dataset.view);
    });
  });
  $("addFilter").addEventListener("click", () => addFilterRow());
  $("runManual").addEventListener("click", () => runManual(1).catch((e) => toast(e.message)));
  $("toggleManualSql").addEventListener("click", () => {
    state.manualSqlExpanded = !state.manualSqlExpanded;
    updateManualSqlVisibility();
  });
  $("resetManualColumns").addEventListener("click", () => {
    state.manualDisplayColumns = defaultManualDisplayColumns();
    state.manualSort = { column: null, dir: "asc" };
    state.manualPageSort = { column: null, dir: "asc" };
    renderManualDisplayColumns();
    clearManualResult();
  });
  $("clearManual").addEventListener("click", () => {
    state.manualFilters = [];
    state.manualDisplayColumns = defaultManualDisplayColumns();
    state.manualSort = { column: null, dir: "asc" };
    state.manualPageSort = { column: null, dir: "asc" };
    renderManualDisplayColumns();
    renderFilters();
    clearManualResult();
  });
  $("runAi").addEventListener("click", () => runAi(1).catch((e) => toast(e.message)));
  $("refreshHealth").addEventListener("click", () => loadHealth().catch((e) => toast(e.message)));
  $("evaluationSelect").addEventListener("change", (event) => {
    const item = state.evaluations.find((question) => question.id === event.target.value);
    if (item) {
      $("questionInput").value = item.query_cs || item.query_en || "";
    }
    updateEvaluationTranslation(item);
  });
  document.querySelectorAll("[data-copy-target]").forEach((button) => {
    button.addEventListener("click", async () => {
      await navigator.clipboard.writeText($(button.dataset.copyTarget).textContent);
      toast("SQL copied.");
    });
  });
}

async function init() {
  bindUi();
  updateResultViewForMethod();
  await loadHealth();
  await loadSchema();
}

init().catch((error) => toast(error.message));
