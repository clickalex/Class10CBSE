/* Mock Test Engine for Class 10 CBSE
 * Handles: listing, taking test, timer, scoring, one-page report, downloads
 * Works offline with mock-tests.json
 */
(function () {
  "use strict";

  const STORAGE_KEY = "c10cbse-mock-results";

  function qs(name) {
    const url = new URL(window.location.href);
    return url.searchParams.get(name);
  }

  function loadResults() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
  }
  function saveResults(r) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(r)); } catch {}
  }

  function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  // ---------- HUB PAGE ----------
  async function initHub() {
    const container = document.getElementById("mock-hub");
    if (!container) return;
    try {
      const res = await fetch(container.dataset.json || "../assets/mock-tests.json");
      const data = await res.json();
      renderHub(container, data);
    } catch (e) {
      container.innerHTML = `<div class="callout alt"><p>Failed to load mock tests: ${e.message}. Try rebuilding the site.</p></div>`;
    }
  }

  function renderHub(container, data) {
    const subjects = data.subjects || [];
    const allTests = data.tests || {};
    let totalQ = 0;
    let totalTests = 0;
    Object.values(allTests).forEach(arr => {
      totalTests += arr.length;
      arr.forEach(t => totalQ += t.questions.length);
    });

    const stats = document.getElementById("mock-stats");
    if (stats) {
      stats.innerHTML = `
        <div class="visual">
          <div class="vbox"><strong>${subjects.length} Subjects</strong><span>Maths, Science, SST, English, Hindi, IT, CA, Sanskrit</span></div>
          <div class="vbox"><strong>${totalTests} Mock Tests</strong><span>Full syllabus & quick practice</span></div>
          <div class="vbox"><strong>${totalQ} Questions</strong><span>MCQs from actual chapters</span></div>
          <div class="vbox"><strong>One-Page Report</strong><span>Score, time, breakdown & review</span></div>
        </div>`;
    }

    const grid = document.createElement("div");
    grid.className = "subjects";
    subjects.forEach(sub => {
      const tests = allTests[sub.slug] || [];
      const card = document.createElement("div");
      card.className = "subject-card";
      card.style.cursor = "default";
      const testList = tests.map((t, idx) => {
        const qCount = t.questions.length;
        const dur = t.duration;
        return `
          <div class="mock-test-row">
            <div class="mock-test-info">
              <strong>${t.title}</strong>
              <span>${qCount} Q · ${dur} min · ${t.type || "Full Syllabus"}</span>
            </div>
            <div class="mock-test-actions">
              <a class="btn primary small" href="take.html?subject=${sub.slug}&test=${idx}">Take Online</a>
              <a class="btn small" href="${sub.slug}/test-${idx+1}-print.html" target="_blank">Print / PDF</a>
              <button class="btn small" onclick="downloadTestJSON('${sub.slug}', ${idx})">JSON</button>
            </div>
          </div>`;
      }).join("");

      card.innerHTML = `
        <span class="sc-code">${sub.code}</span>
        <strong>${sub.title}</strong>
        <span class="sc-desc">${sub.short}</span>
        <div class="mock-test-list">${testList || '<p class="hint">No tests yet</p>'}</div>
        <span class="sc-meta">${tests.length} tests · <a href="${sub.slug}/index.html">View ${sub.title} mocks →</a></span>
      `;
      grid.appendChild(card);
    });
    container.innerHTML = "";
    container.appendChild(grid);
  }

  // global for hub buttons
  window.downloadTestJSON = async function (subject, idx) {
    try {
      const res = await fetch("../assets/mock-tests.json");
      const data = await res.json();
      const test = (data.tests[subject] || [])[idx];
      if (!test) return alert("Test not found");
      const blob = new Blob([JSON.stringify(test, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${subject}-mock-${idx+1}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { alert("Download failed: " + e.message); }
  };

  // ---------- SUBJECT PAGE ----------
  async function initSubjectPage() {
    const container = document.getElementById("mock-subject");
    if (!container) return;
    const subject = container.dataset.subject;
    if (!subject) return;
    try {
      const res = await fetch("../../assets/mock-tests.json");
      const data = await res.json();
      const tests = (data.tests[subject] || []);
      const subjMeta = (data.subjects || []).find(s => s.slug === subject);
      renderSubject(container, subjMeta, tests, subject);
    } catch (e) {
      container.innerHTML = `<div class="callout alt"><p>Failed: ${e.message}</p></div>`;
    }
  }

  function renderSubject(container, meta, tests, slug) {
    if (!meta) meta = { title: slug, code: "", short: "" };
    container.innerHTML = `
      <div class="callout"><p><strong>${tests.length} mock tests</strong> ready for ${meta.title}. Each test is timed, scores instantly, and gives a one-page report with download options.</p></div>
      <div class="mock-subject-actions">
        <a class="btn" href="../index.html">← All Mock Tests</a>
        <a class="btn" href="../../${slug}/index.html">Go to ${meta.title} Hub</a>
      </div>
      ${tests.map((t, idx) => `
        <div class="mock-detail-card">
          <div class="mock-detail-head">
            <h3>${t.title}</h3>
            <span class="unitmarks">${t.questions.length} Questions · ${t.duration} min</span>
          </div>
          <p class="unitdesc">${t.description || "Full syllabus mock based on chapter MCQs. Instant scoring, one-page report."}</p>
          <div class="btnrow">
            <a class="btn primary" href="../take.html?subject=${slug}&test=${idx}">▶ Start Online Test</a>
            <a class="btn" href="test-${idx+1}-print.html" target="_blank">🖨 Print / Save PDF</a>
            <button class="btn" onclick="downloadTestJSONSubject('${slug}', ${idx})">⬇ Download JSON</button>
            <button class="btn" onclick="downloadTestTXT('${slug}', ${idx})">⬇ Download TXT</button>
          </div>
          <details class="rev"><summary>Preview Questions</summary>
            <ol>${t.questions.slice(0,5).map(q => `<li>${escapeHtml(q.stem)}</li>`).join("")}</ol>
            <p class="hint">+ ${t.questions.length - 5} more questions in full test</p>
          </details>
        </div>
      `).join("")}
    `;
  }

  window.downloadTestJSONSubject = async function (subject, idx) {
    const res = await fetch("../../../assets/mock-tests.json".replace("../../../", "../../"));
    // handle both relative paths
    let url = "../../assets/mock-tests.json";
    if (window.location.pathname.includes("/mock-tests/")) {
      // we are in /mock-tests/<subject>/index.html -> ../../assets/
      url = "../../assets/mock-tests.json";
    }
    try {
      const r = await fetch(url);
      const data = await r.json();
      const test = (data.tests[subject] || [])[idx];
      const blob = new Blob([JSON.stringify(test, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${subject}-mock-${idx+1}.json`;
      a.click();
    } catch (e) { alert(e.message); }
  };
  window.downloadTestTXT = async function (subject, idx) {
    const url = "../../assets/mock-tests.json";
    try {
      const r = await fetch(url);
      const data = await r.json();
      const test = (data.tests[subject] || [])[idx];
      let txt = `${test.title}\nSubject: ${subject}\nDuration: ${test.duration} min\nQuestions: ${test.questions.length}\n\n`;
      test.questions.forEach((q, i) => {
        txt += `${i+1}. ${q.stem}\n`;
        Object.entries(q.options).forEach(([k,v]) => { txt += `   (${k}) ${v}\n`; });
        txt += `   Correct: (${q.correct}) ${q.options[q.correct]}\n`;
        txt += `   Explanation: ${q.explanation.replace(/\*\*/g, "")}\n\n`;
      });
      const blob = new Blob([txt], { type: "text/plain" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${subject}-mock-${idx+1}.txt`;
      a.click();
    } catch (e) { alert(e.message); }
  };

  function escapeHtml(s) {
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  // ---------- TAKE PAGE ----------
  async function initTake() {
    const app = document.getElementById("mock-take");
    if (!app) return;
    const subject = qs("subject");
    const testIdx = parseInt(qs("test") || "0", 10);
    if (!subject) {
      app.innerHTML = `<div class="callout alt"><p>No subject selected. <a href="index.html">Go to Mock Tests</a></p></div>`;
      return;
    }
    try {
      const res = await fetch("../assets/mock-tests.json");
      const data = await res.json();
      const tests = data.tests[subject] || [];
      const test = tests[testIdx];
      const subjMeta = (data.subjects || []).find(s => s.slug === subject);
      if (!test) {
        app.innerHTML = `<div class="callout alt"><p>Test not found for ${subject} #${testIdx}. <a href="${subject}/index.html">See ${subject} tests</a></p></div>`;
        return;
      }
      window.__CURRENT_TEST__ = test;
      window.__CURRENT_SUBJECT__ = subject;
      window.__CURRENT_SUBJ_META__ = subjMeta;
      renderStartScreen(app, test, subjMeta, subject, testIdx);
    } catch (e) {
      app.innerHTML = `<div class="callout alt"><p>Failed to load test: ${e.message}</p></div>`;
    }
  }

  function renderStartScreen(app, test, subjMeta, subject, idx) {
    app.innerHTML = `
      <p class="kicker">${subjMeta ? subjMeta.code : subject.toUpperCase()} · MOCK TEST</p>
      <h1>${escapeHtml(test.title)}</h1>
      <p class="lede">${escapeHtml(test.description || "")}</p>
      <div class="visual">
        <div class="vbox"><strong>${test.questions.length} Questions</strong><span>MCQs · 1 mark each</span></div>
        <div class="vbox"><strong>${test.duration} Minutes</strong><span>Timed test</span></div>
        <div class="vbox"><strong>Instant Score</strong><span>One-page report after submit</span></div>
        <div class="vbox"><strong>Negative: No</strong><span>No negative marking</span></div>
      </div>
      <div class="callout">
        <p><strong>Instructions:</strong></p>
        <ul>
          <li>All questions are MCQs with 4 options.</li>
          <li>Timer starts when you click Start. Auto-submit when time ends.</li>
          <li>You can navigate, mark for review, and change answers.</li>
          <li>After submit you get score, percentage, time taken, and detailed review — all in one page report.</li>
          <li>Download options: PDF (print), JSON, TXT report.</li>
        </ul>
      </div>
      <div class="btnrow">
        <button class="btn primary" id="start-btn">▶ Start Test Now</button>
        <a class="btn" href="${subject}/index.html">View All ${subjMeta ? subjMeta.title : subject} Tests</a>
        <a class="btn" href="index.html">All Subjects</a>
      </div>
      <div id="mock-start-preview" style="margin-top:18px;">
        <h3>Chapters Covered</h3>
        <p class="hint">${[...new Set(test.questions.map(q => q.chapterTitle))].slice(0,8).join(", ")}${test.questions.length>8 ? " ..." : ""}</p>
      </div>
    `;
    document.getElementById("start-btn").onclick = () => startTest(app, test, subject, idx);
  }

  function startTest(app, test, subject, idx) {
    const totalSec = test.duration * 60;
    let remaining = totalSec;
    let answers = {}; // qIndex -> chosen option
    let marked = new Set();
    let current = 0;
    let startTime = Date.now();
    let timerInterval = null;

    function renderTestUI() {
      app.innerHTML = `
        <div class="mock-layout">
          <div class="mock-main">
            <div class="mock-header">
              <div>
                <p class="kicker">${escapeHtml(test.title)}</p>
                <h2 id="mock-q-title">Q ${current+1} of ${test.questions.length}</h2>
              </div>
              <div class="mock-timer" id="mock-timer">${formatTime(remaining)}</div>
            </div>
            <div id="mock-question-area"></div>
            <div class="mock-nav">
              <button class="btn" id="prev-btn">← Previous</button>
              <button class="btn" id="mark-btn">⭐ Mark for Review</button>
              <button class="btn" id="clear-btn">Clear</button>
              <button class="btn primary" id="next-btn">Next →</button>
            </div>
            <div class="mock-footer">
              <span id="mock-progress">${Object.keys(answers).length} answered of ${test.questions.length}</span>
              <button class="btn primary" id="submit-btn" style="background:#0f9d76;border-color:#0f9d76;">Submit Test</button>
            </div>
          </div>
          <div class="mock-sidebar">
            <h3>Question Palette</h3>
            <div class="mock-palette" id="mock-palette"></div>
            <div class="mock-legend">
              <span><i class="dot answered"></i> Answered</span>
              <span><i class="dot unanswered"></i> Not Answered</span>
              <span><i class="dot marked"></i> Marked</span>
              <span><i class="dot current"></i> Current</span>
            </div>
            <div class="mock-actions">
              <button class="btn" onclick="if(confirm('Quit test? Progress will be lost')) location.reload()">Quit</button>
              <button class="btn" id="palette-submit">Submit</button>
            </div>
          </div>
        </div>
      `;
      bindTestEvents();
      renderQuestion();
      renderPalette();
    }

    function renderQuestion() {
      const q = test.questions[current];
      const area = document.getElementById("mock-question-area");
      if (!area) return;
      const chosen = answers[current];
      area.innerHTML = `
        <div class="mock-q-card">
          <p class="mock-q-stem"><strong>${current+1}.</strong> ${escapeHtml(q.stem)}</p>
          <p class="hint">Chapter: ${escapeHtml(q.chapterTitle)} · ${escapeHtml(q.chapterId)}</p>
          <div class="mock-options">
            ${Object.entries(q.options).map(([k,v]) => `
              <label class="mock-opt ${chosen===k ? 'selected' : ''}">
                <input type="radio" name="q${current}" value="${k}" ${chosen===k ? 'checked' : ''}>
                <span class="mock-opt-label">(${k})</span>
                <span class="mock-opt-text">${escapeHtml(v)}</span>
              </label>
            `).join("")}
          </div>
        </div>
      `;
      // bind option change
      area.querySelectorAll('input[type=radio]').forEach(inp => {
        inp.addEventListener('change', (e) => {
          answers[current] = e.target.value;
          renderPalette();
          document.getElementById("mock-progress").textContent = `${Object.keys(answers).length} answered of ${test.questions.length}`;
          // highlight selected
          area.querySelectorAll('.mock-opt').forEach(el => el.classList.remove('selected'));
          e.target.closest('.mock-opt').classList.add('selected');
        });
      });
      document.getElementById("mock-q-title").textContent = `Q ${current+1} of ${test.questions.length}`;
      const markBtn = document.getElementById("mark-btn");
      if (markBtn) {
        markBtn.textContent = marked.has(current) ? "★ Unmark" : "⭐ Mark for Review";
        markBtn.classList.toggle("primary", marked.has(current));
      }
    }

    function renderPalette() {
      const pal = document.getElementById("mock-palette");
      if (!pal) return;
      pal.innerHTML = test.questions.map((_, i) => {
        let cls = "unanswered";
        if (answers[i]) cls = "answered";
        if (marked.has(i)) cls = cls === "answered" ? "answered marked" : "marked";
        if (i === current) cls += " current";
        return `<button class="palette-btn ${cls}" data-idx="${i}">${i+1}</button>`;
      }).join("");
      pal.querySelectorAll(".palette-btn").forEach(btn => {
        btn.onclick = () => { current = parseInt(btn.dataset.idx,10); renderQuestion(); renderPalette(); };
      });
    }

    function bindTestEvents() {
      document.getElementById("prev-btn").onclick = () => { if (current>0){ current--; renderQuestion(); renderPalette(); } };
      document.getElementById("next-btn").onclick = () => { if (current<test.questions.length-1){ current++; renderQuestion(); renderPalette(); } else { /* last */ } };
      document.getElementById("mark-btn").onclick = () => {
        if (marked.has(current)) marked.delete(current); else marked.add(current);
        renderQuestion(); renderPalette();
      };
      document.getElementById("clear-btn").onclick = () => { delete answers[current]; renderQuestion(); renderPalette(); document.getElementById("mock-progress").textContent = `${Object.keys(answers).length} answered of ${test.questions.length}`; };
      const submit = () => {
        if (confirm(`Submit test? ${Object.keys(answers).length} of ${test.questions.length} answered.`)) {
          finishTest();
        }
      };
      document.getElementById("submit-btn").onclick = submit;
      const pSub = document.getElementById("palette-submit");
      if (pSub) pSub.onclick = submit;
    }

    function tick() {
      remaining--;
      const timerEl = document.getElementById("mock-timer");
      if (timerEl) timerEl.textContent = formatTime(remaining);
      if (remaining <= 60 && timerEl) timerEl.classList.add("danger");
      if (remaining <= 0) {
        clearInterval(timerInterval);
        alert("Time up! Submitting automatically.");
        finishTest();
      }
    }

    function finishTest() {
      clearInterval(timerInterval);
      const endTime = Date.now();
      const timeTakenSec = Math.floor((endTime - startTime)/1000);
      const result = calculateResult(test, answers, timeTakenSec, totalSec - remaining);
      showReport(app, test, result, subject, idx, answers);
    }

    // start
    renderTestUI();
    timerInterval = setInterval(tick, 1000);
  }

  function calculateResult(test, answers, timeTakenSec, timeUsed) {
    let correct = 0, wrong = 0, unattempted = 0;
    const details = test.questions.map((q, i) => {
      const chosen = answers[i] || null;
      let status = "unattempted";
      if (!chosen) { unattempted++; }
      else if (chosen === q.correct) { correct++; status = "correct"; }
      else { wrong++; status = "wrong"; }
      return { idx: i, q, chosen, correct: q.correct, status };
    });
    const total = test.questions.length;
    const score = correct; // 1 mark each
    const percentage = total ? Math.round((correct/total)*100) : 0;
    return { correct, wrong, unattempted, total, score, percentage, timeTakenSec, timeUsed, details };
  }

  function showReport(app, test, result, subject, idx, answers) {
    const subjMeta = window.__CURRENT_SUBJ_META__;
    const timeStr = formatTime(result.timeTakenSec);
    const grade = result.percentage >= 90 ? "Outstanding" : result.percentage >= 75 ? "Excellent" : result.percentage >= 60 ? "Good" : result.percentage >= 40 ? "Average" : "Needs Improvement";
    const color = result.percentage >= 75 ? "#0f9d76" : result.percentage >= 50 ? "#b45309" : "#dc2626";

    // save to localStorage
    try {
      const all = loadResults();
      const key = `${subject}-${idx}`;
      all[key] = { date: new Date().toISOString(), subject, testIdx: idx, title: test.title, result: { correct: result.correct, total: result.total, percentage: result.percentage, timeTaken: result.timeTakenSec } };
      saveResults(all);
    } catch {}

    app.innerHTML = `
      <div id="mock-report" class="mock-report">
        <p class="kicker">ONE-PAGE REPORT · ${subject.toUpperCase()} · ${escapeHtml(test.title)}</p>
        <h1>Test Report — ${result.score} / ${result.total}</h1>
        <div class="report-grid">
          <div class="report-card score" style="border-left:4px solid ${color}">
            <h3>Score</h3>
            <div class="report-big">${result.correct} / ${result.total}</div>
            <div class="report-sub">${result.percentage}% · ${grade}</div>
            <div class="bar" style="margin-top:10px;background:#e5e7eb;height:10px;border-radius:999px;overflow:hidden;"><span class="fill" style="width:${result.percentage}%;background:${color};display:block;height:100%;"></span></div>
          </div>
          <div class="report-card">
            <h3>Breakdown</h3>
            <ul>
              <li>✅ Correct: <strong>${result.correct}</strong></li>
              <li>❌ Wrong: <strong>${result.wrong}</strong></li>
              <li>⚪ Unattempted: <strong>${result.unattempted}</strong></li>
              <li>⏱ Time Taken: <strong>${timeStr}</strong> of ${test.duration} min</li>
              <li>📊 Accuracy: <strong>${result.total ? Math.round((result.correct/(result.correct+result.wrong||1))*100) : 0}%</strong></li>
            </ul>
          </div>
          <div class="report-card">
            <h3>Quick Actions</h3>
            <div class="btnrow">
              <button class="btn primary" onclick="window.print()">🖨 Print / Save as PDF</button>
              <button class="btn" onclick="downloadReportJSON()">⬇ JSON Report</button>
              <button class="btn" onclick="downloadReportTXT()">⬇ TXT Report</button>
              <a class="btn" href="take.html?subject=${subject}&test=${idx}">🔄 Retake Test</a>
              <a class="btn" href="${subject}/index.html">📚 More ${subject} Tests</a>
              <a class="btn" href="index.html">🏠 All Mock Tests</a>
            </div>
            <p class="hint" style="margin-top:10px;">Tip: Use Print → Save as PDF to download your one-page report.</p>
          </div>
        </div>

        <h2>Chapter-wise Performance</h2>
        <div id="chapter-breakdown"></div>

        <h2>Detailed Review — All Questions</h2>
        <p class="hint">Green = correct, Red = wrong, Grey = unattempted. Click question to see explanation.</p>
        <div class="qstack" id="review-stack"></div>

        <div class="callout" style="margin-top:24px;">
          <p><strong>What next?</strong> Review wrong answers, revise those chapters, then retake or try next mock. Your progress is saved in this browser.</p>
        </div>
      </div>
    `;

    // chapter breakdown
    const chapMap = {};
    result.details.forEach(d => {
      const ch = d.q.chapterTitle || "Unknown";
      if (!chapMap[ch]) chapMap[ch] = { correct:0, total:0 };
      chapMap[ch].total++;
      if (d.status==="correct") chapMap[ch].correct++;
    });
    const chapEl = document.getElementById("chapter-breakdown");
    chapEl.innerHTML = `<div class="tablewrap"><table><thead><tr><th>Chapter</th><th>Score</th><th>Accuracy</th></tr></thead><tbody>${
      Object.entries(chapMap).map(([ch, v]) => {
        const acc = Math.round((v.correct/v.total)*100);
        return `<tr><td>${escapeHtml(ch)}</td><td>${v.correct}/${v.total}</td><td>${acc}%</td></tr>`;
      }).join("")
    }</tbody></table></div>`;

    // review stack
    const review = document.getElementById("review-stack");
    review.innerHTML = result.details.map(d => {
      const q = d.q;
      const statusIcon = d.status==="correct" ? "✅" : d.status==="wrong" ? "❌" : "⚪";
      const statusClass = d.status;
      return `
        <article class="qcard review-${statusClass}">
          <div class="qmeta">
            <span class="qbadge ${statusClass==='correct'?'qbadge-a': statusClass==='wrong' ? 'qbadge-c' : 'qbadge-s'}">${statusIcon} ${d.status.toUpperCase()}</span>
            <span class="qcode">Q${d.idx+1} · ${escapeHtml(q.chapterTitle)}</span>
          </div>
          <p class="qtext"><strong>${d.idx+1}.</strong> ${escapeHtml(q.stem)}</p>
          <div class="mock-options" style="margin:8px 0;">
            ${Object.entries(q.options).map(([k,v]) => {
              let cls = "";
              if (k===q.correct) cls = "correct";
              if (d.chosen===k && k!==q.correct) cls = "wrong";
              if (d.chosen===k && k===q.correct) cls = "correct selected";
              return `<div class="mock-opt ${cls}" style="pointer-events:none;"><span class="mock-opt-label">(${k})</span> <span>${escapeHtml(v)}</span> ${k===q.correct ? '✅' : ''} ${d.chosen===k && k!==q.correct ? '❌ your answer' : d.chosen===k ? '(your answer)' : ''}</div>`;
            }).join("")}
          </div>
          ${d.chosen ? `<p class="hint">Your answer: (${d.chosen}) ${escapeHtml(q.options[d.chosen]||"")}</p>` : `<p class="hint">You did not attempt this question.</p>`}
          <p class="hint">Correct answer: <strong>(${q.correct}) ${escapeHtml(q.options[q.correct])}</strong></p>
          <details class="qans"><summary>Show Explanation</summary><div class="ans">${escapeHtml(q.explanation).replace(/\n/g,"<br>")}</div></details>
        </article>
      `;
    }).join("");

    window.__LAST_RESULT__ = result;
    window.__LAST_TEST__ = test;
    window.__LAST_SUBJECT__ = subject;
  }

  window.downloadReportJSON = function() {
    const result = window.__LAST_RESULT__;
    const test = window.__LAST_TEST__;
    if (!result) return;
    const data = { test: test.title, subject: window.__LAST_SUBJECT__, date: new Date().toISOString(), result };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type:"application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `report-${window.__LAST_SUBJECT__}-${Date.now()}.json`;
    a.click();
  };
  window.downloadReportTXT = function() {
    const result = window.__LAST_RESULT__;
    const test = window.__LAST_TEST__;
    if (!result) return;
    let txt = `CBSE Class 10 Mock Test Report\nSubject: ${window.__LAST_SUBJECT__}\nTest: ${test.title}\nDate: ${new Date().toLocaleString()}\n\nScore: ${result.correct}/${result.total} (${result.percentage}%)\nCorrect: ${result.correct}\nWrong: ${result.wrong}\nUnattempted: ${result.unattempted}\nTime Taken: ${formatTime(result.timeTakenSec)}\n\nDetailed Review:\n`;
    result.details.forEach(d => {
      txt += `\n${d.idx+1}. ${d.q.stem}\n`;
      Object.entries(d.q.options).forEach(([k,v]) => txt += `   (${k}) ${v}${k===d.q.correct ? ' [CORRECT]' : ''}${d.chosen===k ? ' [YOUR ANSWER]' : ''}\n`);
      txt += `   Status: ${d.status}\n   Explanation: ${d.q.explanation.replace(/\*\*/g,"")}\n`;
    });
    const blob = new Blob([txt], { type:"text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `report-${window.__LAST_SUBJECT__}-${Date.now()}.txt`;
    a.click();
  };

  // init on load
  document.addEventListener("DOMContentLoaded", () => {
    initHub();
    initSubjectPage();
    initTake();
  });

})();
