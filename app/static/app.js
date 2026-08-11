const STEPS = {
  1: ["Paste a collective bargaining agreement", "Paste machine-readable contract text. The app does not perform OCR."],
  2: ["Remove non-core contract material", "Conservatively remove appendices, exhibits, signatures and wage or salary schedules."],
  3: ["Split the contract into sections", "Detect article and section headings while preserving the heading attached to every text block."],
  4: ["Split sections into sentences", "Tokenize every section while retaining section and sentence identifiers."],
  5: ["Parse sentences grammatically", "Extract subjects, verbs, objects and dependency information."],
  6: ["Keep Subject–Verb–Object clauses", "Retain auditable clauses and explain why other sentences were rejected."],
  7: ["Classify the subject or agent", "Map the extracted subject to worker, firm, union, manager or unknown."],
  8: ["Identify modal and verb structure", "Detect restrictive/permissive modals, negation, voice and special legal verbs."],
  9: ["Classify each legal clause", "Assign right, obligation, permission, prohibition or other and expose the applied rule."],
  10: ["Build contract-level measures", "Aggregate agent and legal-type counts and shares."],
  11: ["Group worker rights into topics", "Assign worker rights to seven broad topics and produce final exports."],
};

let currentStep = 1;
let completedStep = 0;
let latestResult = null;
const textArea = document.querySelector("#contractText");
const output = document.querySelector("#output");
const summary = document.querySelector("#summaryStrip");
const statusText = document.querySelector("#statusText");
const runButton = document.querySelector("#runButton");

textArea.addEventListener("input", () => {
  document.querySelector("#charCount").textContent = `${textArea.value.length.toLocaleString()} characters`;
});

document.querySelectorAll(".step").forEach(button => button.addEventListener("click", () => {
  const step = Number(button.dataset.step);
  if (step <= completedStep + 1) selectStep(step);
}));

document.querySelector("#resetButton").addEventListener("click", () => {
  if (!confirm("Clear the contract and all processing results?")) return;
  textArea.value = "";
  latestResult = null;
  completedStep = 0;
  output.innerHTML = "";
  summary.classList.add("hidden");
  document.querySelector("#downloadJson").disabled = true;
  document.querySelector("#downloadCsv").disabled = true;
  selectStep(1);
  textArea.dispatchEvent(new Event("input"));
});

runButton.addEventListener("click", async () => {
  if (!textArea.value.trim()) {
    statusText.textContent = "Paste contract text first.";
    textArea.focus();
    return;
  }
  const target = currentStep === 1 ? 2 : currentStep;
  runButton.disabled = true;
  runButton.textContent = `Running Step ${target}…`;
  statusText.textContent = "Processing in memory; the text is not retained on the server.";
  try {
    const response = await fetch("/api/process", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text: textArea.value, step: target}),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Processing failed");
    latestResult = body;
    completedStep = Math.max(completedStep, target);
    document.querySelector("#engineBadge").textContent = body.engine;
    document.querySelector("#downloadJson").disabled = false;
    document.querySelector("#downloadCsv").disabled = !body.clauses;
    selectStep(target);
    render(body, target);
    statusText.textContent = `Step ${target} completed.`;
  } catch (error) {
    statusText.textContent = error.message;
  } finally {
    runButton.disabled = false;
    updateRunButton();
  }
});

document.querySelector("#downloadJson").addEventListener("click", () => download("/api/export/json", latestResult));
document.querySelector("#downloadCsv").addEventListener("click", () => download("/api/export/clauses", latestResult));

async function download(url, result) {
  const response = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({result})});
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const name = disposition.match(/filename="?([^";]+)"?/)?.[1] || "download";
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob); link.download = name; link.click();
  URL.revokeObjectURL(link.href);
}

function selectStep(step) {
  currentStep = step;
  document.querySelectorAll(".step").forEach(button => {
    const n = Number(button.dataset.step);
    button.classList.toggle("active", n === step);
    button.classList.toggle("done", n <= completedStep && n !== step);
  });
  document.querySelector("#stepKicker").textContent = `STEP ${step} OF 11`;
  document.querySelector("#stepHeading").textContent = STEPS[step][0];
  document.querySelector("#stepDescription").textContent = STEPS[step][1];
  document.querySelector("#inputPanel").classList.toggle("hidden", step !== 1);
  if (latestResult && step <= completedStep) render(latestResult, step);
  updateRunButton();
}

function updateRunButton() {
  if (currentStep === 1) runButton.textContent = "Save text and run Step 2 →";
  else if (currentStep === 11) runButton.textContent = "Run Step 11";
  else runButton.textContent = `Run Step ${currentStep}`;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
}

function metric(value, label) { return `<div class="metric"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`; }
function detail(title, body, tags="") { return `<details><summary>${esc(title)}</summary><div class="record-meta">${tags}</div><div class="codebox">${esc(body)}</div></details>`; }
function tag(value, cls="") { return value === null || value === undefined ? "" : `<span class="tag ${cls}">${esc(value)}</span>`; }

function render(result, step) {
  summary.classList.remove("hidden");
  output.innerHTML = "";
  if (step === 1) {
    summary.innerHTML = metric(result.source_text.length.toLocaleString(), "characters");
    return;
  }
  if (step === 2) {
    summary.innerHTML = metric(result.cleaning.cleaned_text.length.toLocaleString(), "kept characters") + metric(result.cleaning.removed_line_count, "removed lines");
    output.innerHTML = `<div class="card"><h3>Cleaned contract</h3><div class="codebox">${esc(result.cleaning.cleaned_text)}</div></div>` +
      `<div class="card"><h3>Removed material</h3><p class="muted">${esc(result.cleaning.method_note)}</p><div class="codebox">${esc(result.cleaning.removed_text || "Nothing removed.")}</div></div>`;
  } else if (step === 3) {
    summary.innerHTML = metric(result.sections.length, "sections");
    output.innerHTML = `<div class="card"><h3>Detected sections</h3>${result.sections.map(x => detail(`${x.section_id}. ${x.heading}`, x.text)).join("")}</div>`;
  } else if (step === 4) {
    summary.innerHTML = metric(result.sentences.length, "sentences") + metric(result.sections.length, "sections");
    output.innerHTML = `<div class="card"><h3>Sentences</h3>${result.sentences.map(x => detail(`#${x.sentence_id} · ${x.section_heading}`, x.text, tag(x.tokenizer))).join("")}</div>`;
  } else if (step === 5) {
    summary.innerHTML = metric(result.parsed_sentences.length, "parsed sentences");
    output.innerHTML = `<div class="card"><h3>Grammar parse</h3>${result.parsed_sentences.map(x => detail(`#${x.sentence_id} · ${x.text}`, `SUBJECT: ${x.subject || "—"}\nVERB: ${x.verb || "—"}\nOBJECT: ${x.object || "—"}`, tag(x.parser))).join("")}</div>`;
  } else if (step === 6) {
    summary.innerHTML = metric(result.clauses.length, "accepted clauses") + metric(result.rejected_sentences.length, "rejected sentences");
    output.innerHTML = `<div class="card"><h3>Accepted SVO clauses</h3>${result.clauses.map(x => detail(`#${x.sentence_id} · ${x.text}`, `SUBJECT: ${x.subject}\nVERB: ${x.verb}\nOBJECT: ${x.object}`, tag("accepted", "right"))).join("")}</div>` +
      `<div class="card"><h3>Rejected sentences</h3>${result.rejected_sentences.map(x => detail(`#${x.sentence_id} · ${x.text}`, x.rejection_reason, tag("rejected", "rejected"))).join("")}</div>`;
  } else if (step === 7) {
    const counts = result.clauses.reduce((acc, row) => { acc[row.agent] = (acc[row.agent] || 0) + 1; return acc; }, {});
    summary.innerHTML = metric(result.clauses.length, "clauses") + Object.entries(counts).map(([k,v]) => metric(v, k)).join("");
    output.innerHTML = clauseCards(result.clauses, ["agent", "agent_rule"]);
  } else if (step === 8) {
    summary.innerHTML = metric(result.clauses.length, "clauses");
    output.innerHTML = clauseCards(result.clauses, ["agent", "modal", "modal_type", "negated", "voice", "special_verb"]);
  } else if (step === 9) {
    summary.innerHTML = metric(result.clauses.length, "classified clauses");
    output.innerHTML = clauseCards(result.clauses, ["agent", "clause_type", "classification_rule"]);
  } else if (step === 10 || step === 11) {
    const m = result.measures.contract_level_measures;
    summary.innerHTML = metric(m.number_of_clauses, "clauses") + metric(m.number_of_worker_rights, "worker rights") + metric((100*m.share_of_worker_rights).toFixed(1)+"%", "worker-right share");
    output.innerHTML = measuresTable(result) + metadataTable(result.metadata);
    if (step === 11) output.innerHTML += `<div class="card"><h3>Topic methodology</h3><p>${esc(result.methodology_note)}</p></div>` + clauseCards(result.clauses.filter(x => x.worker_right_topic), ["agent", "clause_type", "worker_right_topic", "topic_rule"]);
  }
}

function clauseCards(clauses, fields) {
  return `<div class="card"><h3>Clause audit</h3>${clauses.map(x => detail(`#${x.sentence_id} · ${x.text}`, fields.map(f => `${f.toUpperCase()}: ${typeof x[f] === "object" ? JSON.stringify(x[f]) : x[f] ?? "—"}`).join("\n"), tag(x.agent) + tag(x.clause_type, x.clause_type === "right" ? "right" : "") + tag(x.worker_right_topic))).join("")}</div>`;
}

function measuresTable(result) {
  const groups = {
    "Contract-level measures": result.measures.contract_level_measures,
    "Agent variables": result.measures.agent_variables,
    "Worker-right topic variables": result.measures.worker_right_topic_variables,
  };
  return Object.entries(groups).map(([title, values]) => `<div class="card"><h3>${title}</h3><div class="table-wrap"><table><tbody>${Object.entries(values).map(([k,v]) => `<tr><th>${esc(k)}</th><td><div class="codebox">${esc(typeof v === "object" ? JSON.stringify(v, null, 2) : v)}</div></td></tr>`).join("")}</tbody></table></div></div>`).join("");
}

function metadataTable(metadata) {
  const rows = Object.entries(metadata).filter(([k]) => !["evidence", "warning"].includes(k));
  return `<div class="card"><h3>Provisional metadata</h3><p class="muted">${esc(metadata.warning)}</p><div class="table-wrap"><table><thead><tr><th>Variable</th><th>Value</th><th>Evidence</th></tr></thead><tbody>${rows.map(([k,v]) => `<tr><td>${esc(k)}</td><td>${esc(v ?? "—")}</td><td>${esc(metadata.evidence?.[k] || "—")}</td></tr>`).join("")}</tbody></table></div></div>`;
}

selectStep(1);
