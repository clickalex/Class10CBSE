/* Mock-test engine for the Class 10 CBSE study hub.
 *
 * One file, three jobs:
 *   1. the test screen (set-N.html): timer, palette, answers, submit, the
 *      one-page score report, answer review, print / text download;
 *   2. attempt history on the centre and exam pages (localStorage only —
 *      nothing leaves the browser);
 *   3. the printable paper page: show / hide the answer key.
 *
 * The scoring helpers live in `core` and are exported for Node so the
 * repository tests can check them without a browser.
 */
(function (root) {
  "use strict";

  var core = {};

  /* ---------------- pure helpers ---------------- */

  core.score = function (questions, answers, marking) {
    var mc = Number(marking.marksCorrect) || 0;
    var mw = Number(marking.marksWrong) || 0;
    var res = {
      correct: 0, wrong: 0, skipped: 0, marks: 0, negative: 0,
      max: questions.length * mc, sections: [], topics: {}, per: []
    };
    var secs = {};
    for (var i = 0; i < questions.length; i++) {
      var q = questions[i];
      var a = answers[i];
      var status;
      if (a === null || a === undefined || a === "") status = "skipped";
      else if (Number(a) === Number(q.ans)) status = "correct";
      else status = "wrong";
      res[status] += 1;
      if (status === "correct") res.marks += mc;
      if (status === "wrong") { res.marks -= mw; res.negative += mw; }
      res.per.push(status);

      var s = secs[q.sec] || (secs[q.sec] = { sec: q.sec, total: 0, correct: 0, wrong: 0, skipped: 0, marks: 0 });
      s.total += 1; s[status] += 1;
      if (status === "correct") s.marks += mc;
      if (status === "wrong") s.marks -= mw;

      var tk = q.topicKey || q.topic || ("q" + i);
      var t = res.topics[tk] || (res.topics[tk] = {
        key: tk, topic: q.topic || tk, src: q.src || "", url: q.url || null,
        practice: q.practice || null, total: 0, correct: 0, wrong: 0, skipped: 0
      });
      t.total += 1; t[status] += 1;
    }
    var keys = Object.keys(secs).map(Number).sort(function (a, b) { return a - b; });
    for (var k = 0; k < keys.length; k++) {
      var sec = secs[keys[k]];
      sec.max = sec.total * mc;
      sec.pct = sec.max ? Math.round(Math.max(0, sec.marks) / sec.max * 100) : 0;
      res.sections.push(sec);
    }
    res.attempted = res.correct + res.wrong;
    res.pct = res.max ? Math.round(Math.max(0, res.marks) / res.max * 100) : 0;
    res.accuracy = res.attempted ? Math.round(res.correct / res.attempted * 100) : 0;
    return res;
  };

  core.grade = function (pct) {
    if (pct >= 90) return "Outstanding";
    if (pct >= 75) return "Very good";
    if (pct >= 60) return "Good";
    if (pct >= 40) return "Needs practice";
    return "Revise the basics";
  };

  core.fmtTime = function (sec) {
    sec = Math.max(0, Math.floor(Number(sec) || 0));
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    var mm = (m < 10 ? "0" : "") + m, ss = (s < 10 ? "0" : "") + s;
    return h ? h + ":" + mm + ":" + ss : mm + ":" + ss;
  };

  /* Topics to revise first: accuracy under 60% with at least two questions
   * asked; if nothing qualifies, the lowest-accuracy topics that had a miss. */
  core.weakTopics = function (topics, limit) {
    limit = limit || 5;
    var all = Object.keys(topics).map(function (k) { return topics[k]; });
    all.forEach(function (t) { t.pct = t.total ? Math.round(t.correct / t.total * 100) : 0; });
    var weak = all.filter(function (t) { return t.total >= 2 && t.pct < 60; });
    if (!weak.length) weak = all.filter(function (t) { return t.correct < t.total; });
    weak.sort(function (a, b) { return a.pct - b.pct || b.total - a.total || (a.topic > b.topic ? 1 : -1); });
    return weak.slice(0, limit);
  };

  core.reportText = function (data, result, attempt, siteUrl) {
    var ex = data.exam;
    var lines = [];
    var rule = "=".repeat(64);
    lines.push("SCORE REPORT - " + ex.title + " - Set " + ex.set);
    lines.push(rule);
    if (attempt.name) lines.push("Name    : " + attempt.name);
    lines.push("Date    : " + new Date(attempt.at).toLocaleString());
    lines.push("Score   : " + result.marks + " / " + result.max + " (" + result.pct + "%) - " + core.grade(result.pct));
    lines.push("Correct " + result.correct + " | Wrong " + result.wrong + " | Unattempted " + result.skipped +
      " | Accuracy " + result.accuracy + "%" + (result.negative ? " | Lost to negatives -" + result.negative : ""));
    lines.push("Time    : " + core.fmtTime(attempt.timeSec) + " of " + core.fmtTime(ex.minutes * 60) +
      (attempt.auto ? " (auto-submitted at time-out)" : ""));
    lines.push("");
    lines.push("Section-wise");
    result.sections.forEach(function (s) {
      var name = data.sections[s.sec] ? data.sections[s.sec].name : ("Section " + (s.sec + 1));
      lines.push("  " + pad(name, 34) + pad(s.correct + "/" + s.total, 8) + pad(s.marks + "/" + s.max, 10) + s.pct + "%");
    });
    var weak = core.weakTopics(result.topics);
    if (weak.length) {
      lines.push("");
      lines.push("Revise first");
      weak.forEach(function (t) {
        lines.push("  " + t.topic + " (" + t.src + "): " + t.correct + "/" + t.total + " correct" +
          (t.url ? "  -> " + absolute(t.url, siteUrl, ex) : ""));
      });
    }
    lines.push("");
    lines.push("Question map (" + "\u2713 correct, \u2717 wrong, - skipped)");
    var row = [];
    result.per.forEach(function (st, i) {
      var mark = st === "correct" ? "\u2713" : st === "wrong" ? "\u2717" : "-";
      row.push(pad((i + 1) + mark, 6));
      if (row.length === 10) { lines.push("  " + row.join("")); row = []; }
    });
    if (row.length) lines.push("  " + row.join(""));
    lines.push("");
    lines.push(rule);
    lines.push("Class 10 CBSE study hub - original practice material, not an official paper.");
    lines.push(siteUrl + "/mock-test/" + ex.id + "/set-" + ex.set + ".html");
    return lines.join("\n");

    function pad(s, n) { s = String(s); while (s.length < n) s += " "; return s; }
    function absolute(url, base, exam) {
      /* links in the payload are relative to mock-test/<exam>/ */
      return base + "/" + String(url).replace(/^(\.\.\/)+/, "");
    }
  };

  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  root.MockCore = core;

  /* ---------------- browser part ---------------- */

  var SITE_URL = "https://clickalex.github.io/Class10CBSE";
  var ATT_KEY = "c10cbse-mock-attempts";

  function loadJSON(store, key, fallback) {
    try { return JSON.parse(store.getItem(key)) || fallback; } catch (e) { return fallback; }
  }
  function saveJSON(store, key, value) {
    try { store.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ }
  }
  function attempts() { return loadJSON(localStorage, ATT_KEY, []); }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function fmtDate(iso) {
    var d = new Date(iso);
    return isNaN(d) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) +
      " " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  function bestOf(list) {
    var best = null;
    list.forEach(function (a) { if (!best || a.pct > best.pct || (a.pct === best.pct && a.marks > best.marks)) best = a; });
    return best;
  }
  function download(name, text) {
    var blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }
  function each(sel, fn, scope) {
    Array.prototype.forEach.call((scope || document).querySelectorAll(sel), fn);
  }

  if (document.querySelector(".mock-app, .paper, [data-mock-best], [data-mock-attempts]")) {
    document.body.className += " mock-page";
  }

  /* ---- centre page: best score per exam, recent attempts ---- */
  var all = attempts();
  each("[data-mock-best]", function (el) {
    var id = el.getAttribute("data-mock-best");
    var mine = all.filter(function (a) { return a.exam === id; });
    if (!mine.length) return;
    var b = bestOf(mine);
    el.innerHTML = "Best on this device: <strong>" + b.marks + " / " + b.max + "</strong> (" + b.pct + "%, Set " +
      b.set + ") · " + mine.length + " attempt" + (mine.length === 1 ? "" : "s");
    el.className += " has-score";
  });
  var recent = document.querySelector("[data-mock-recent]");
  if (recent && all.length) {
    var rows = document.querySelector("[data-mock-recent-rows]");
    all.slice(0, 12).forEach(function (a) {
      var tr = document.createElement("tr");
      tr.innerHTML = "<td>" + esc(fmtDate(a.at)) + "</td><td>" + esc(a.title) + "</td><td>" + a.set + "</td>" +
        "<td>" + a.marks + " / " + a.max + "</td><td>" + a.pct + "%</td><td>" + core.fmtTime(a.timeSec) + "</td>" +
        '<td><a href="' + esc(a.exam) + "/set-" + a.set + '.html#report">Report</a></td>';
      rows.appendChild(tr);
    });
    recent.hidden = false;
  }
  each("[data-mock-clear]", function (btn) {
    btn.addEventListener("click", function () {
      if (!confirm("Delete all saved mock-test attempts on this device?")) return;
      var keys = [];
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && k.indexOf("c10cbse-mock") === 0) keys.push(k);
      }
      keys.forEach(function (k) { localStorage.removeItem(k); });
      location.reload();
    });
  });

  /* ---- exam page: attempts table + best per set ---- */
  each("[data-mock-attempts]", function (el) {
    var id = el.getAttribute("data-mock-attempts");
    var mine = all.filter(function (a) { return a.exam === id; });
    if (!mine.length) return;
    var b = bestOf(mine);
    var html = '<p><strong>Best: ' + b.marks + " / " + b.max + " (" + b.pct + "%)</strong> on Set " + b.set +
      " · " + mine.length + " attempt" + (mine.length === 1 ? "" : "s") + "</p>" +
      '<div class="tablewrap"><table><thead><tr><th>When</th><th>Set</th><th>Score</th><th>%</th>' +
      "<th>Correct / wrong / skipped</th><th>Time</th><th></th></tr></thead><tbody>";
    mine.slice(0, 20).forEach(function (a) {
      html += "<tr><td>" + esc(fmtDate(a.at)) + "</td><td>" + a.set + "</td><td>" + a.marks + " / " + a.max +
        "</td><td>" + a.pct + "%</td><td>" + a.correct + " / " + a.wrong + " / " + a.skipped + "</td><td>" +
        core.fmtTime(a.timeSec) + '</td><td><a href="set-' + a.set + '.html#report">Report</a></td></tr>';
    });
    html += "</tbody></table></div>";
    el.innerHTML = html;
  });
  each("[data-mock-set-best]", function (el) {
    var parts = el.getAttribute("data-mock-set-best").split("/");
    var mine = all.filter(function (a) { return a.exam === parts[0] && String(a.set) === parts[1]; });
    if (!mine.length) return;
    var b = bestOf(mine);
    el.innerHTML = "<strong>" + b.marks + " / " + b.max + "</strong> (" + b.pct + "%)";
  });

  /* ---- printable paper: key toggles ---- */
  var paper = document.querySelector("[data-paper]");
  if (paper) {
    var printKey = paper.querySelector("[data-paper-key]");
    var showKey = paper.querySelector("[data-paper-show-key]");
    function syncPaper() {
      paper.classList.toggle("paper-print-key", !printKey || printKey.checked);
      paper.classList.toggle("paper-show-key", !!(showKey && showKey.checked));
    }
    if (printKey) printKey.addEventListener("change", syncPaper);
    if (showKey) showKey.addEventListener("change", syncPaper);
    syncPaper();
  }

  /* ---- the test screen ---- */
  var app = document.getElementById("mock");
  var dataEl = document.getElementById("mock-data");
  if (!app || !dataEl) return;

  var data = JSON.parse(dataEl.textContent);
  var exam = data.exam;
  var Q = data.questions;
  var N = Q.length;
  var KEY = app.getAttribute("data-mock-key");
  var PROG_KEY = "c10cbse-mock-progress:" + KEY;
  var LAST_KEY = "c10cbse-mock-last:" + KEY;
  var TOTAL_SEC = exam.minutes * 60;

  var views = {};
  each("[data-view]", function (v) { views[v.getAttribute("data-view")] = v; }, app);
  var $ = function (sel) { return app.querySelector(sel); };
  var nameInput = $("[data-mock-name]");
  var timerEl = $("[data-mock-timer]");
  var progressEl = $("[data-mock-progress]");
  var sectionEl = $("[data-mock-section]");
  var qEl = $("[data-mock-question]");
  var palEl = $("[data-mock-palette]");

  var state = { answers: [], marked: [], current: 0, startedAt: null, name: "" };
  for (var i0 = 0; i0 < N; i0++) { state.answers.push(null); state.marked.push(false); }
  var ticker = null;
  var lastResult = null, lastAttempt = null;

  function show(name) {
    Object.keys(views).forEach(function (k) { views[k].hidden = k !== name; });
    document.body.classList.toggle("mock-print-report", name === "report");
    document.body.classList.toggle("mock-in-test", name === "test");
    if (name !== "intro") {
      var top = app.getBoundingClientRect().top + window.pageYOffset - 8;
      try { window.scrollTo({ top: top, behavior: "smooth" }); } catch (e) { window.scrollTo(0, top); }
    }
  }
  function saveProgress() { saveJSON(sessionStorage, PROG_KEY, state); }
  function elapsed() { return Math.floor((Date.now() - state.startedAt) / 1000); }
  function remaining() { return Math.max(0, TOTAL_SEC - elapsed()); }

  function sectionName(i) { return data.sections[Q[i].sec] ? data.sections[Q[i].sec].name : ""; }
  function answered() { return state.answers.filter(function (a) { return a !== null && a !== undefined; }).length; }

  /* --- rendering --- */
  function renderQuestion() {
    var i = state.current, q = Q[i];
    var html = '<div class="mock-q-head"><span class="mock-q-num">Question ' + (i + 1) + " of " + N + "</span>" +
      '<span class="mock-q-sec">' + esc(sectionName(i)) + "</span>" +
      '<span class="marks">' + exam.marksCorrect + " mark" + (exam.marksCorrect === 1 ? "" : "s") +
      (exam.marksWrong ? " · −" + exam.marksWrong : "") + "</span></div>" +
      (q.ctx ? '<p class="mock-ctx">' + q.ctx + "</p>" : "") +
      '<p class="qtext">' + q.stem + "</p><div class=\"mock-opts\" role=\"radiogroup\">";
    for (var k = 0; k < q.opts.length; k++) {
      var on = state.answers[i] === k;
      html += '<label class="mock-opt' + (on ? " is-picked" : "") + '"><input type="radio" name="q' + i + '" value="' + k + '"' +
        (on ? " checked" : "") + '><span class="mock-lab">(' + esc(q.labels[k]) + ")</span><span>" + q.opts[k] + "</span></label>";
    }
    html += "</div>" +
      '<div class="mock-q-actions">' +
      '<button type="button" class="btn" data-act="prev"' + (i === 0 ? " disabled" : "") + ">← Previous</button>" +
      '<button type="button" class="btn" data-act="clear">Clear response</button>' +
      '<button type="button" class="btn' + (state.marked[i] ? " is-marked" : "") + '" data-act="mark">' +
      (state.marked[i] ? "Unmark review" : "Mark for review") + "</button>" +
      '<button type="button" class="btn primary" data-act="next">' + (i === N - 1 ? "Go to first unanswered" : "Save & next →") + "</button>" +
      "</div>";
    qEl.innerHTML = html;
    progressEl.textContent = answered() + " / " + N + " answered";
    sectionEl.textContent = "Section " + String.fromCharCode(65 + q.sec) + " · " + sectionName(i);
  }

  function renderPalette() {
    var html = "";
    var lastSec = -1;
    for (var i = 0; i < N; i++) {
      if (Q[i].sec !== lastSec) {
        lastSec = Q[i].sec;
        html += '<span class="pal-sec">' + String.fromCharCode(65 + lastSec) + "</span>";
      }
      var cls = "pal-btn";
      if (state.answers[i] !== null && state.answers[i] !== undefined) cls += " is-answered";
      if (state.marked[i]) cls += " is-marked";
      if (i === state.current) cls += " is-current";
      html += '<button type="button" class="' + cls + '" data-go="' + i + '" aria-label="Question ' + (i + 1) + '">' + (i + 1) + "</button>";
    }
    palEl.innerHTML = html;
  }

  function render() { renderQuestion(); renderPalette(); }

  function go(i) {
    if (i < 0 || i >= N) return;
    state.current = i;
    saveProgress();
    render();
    var cur = palEl.querySelector(".is-current");
    if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest" });
  }

  /* --- timer --- */
  function tick() {
    var r = remaining();
    timerEl.textContent = core.fmtTime(r);
    timerEl.classList.toggle("is-low", r <= 120);
    if (r <= 0) submit(true);
  }
  function startTimer() {
    if (ticker) clearInterval(ticker);
    tick();
    ticker = setInterval(tick, 1000);
  }

  /* --- flow --- */
  function start() {
    state.name = nameInput ? nameInput.value.trim() : "";
    state.startedAt = Date.now();
    state.current = 0;
    saveProgress();
    show("test");
    render();
    startTimer();
  }

  function submit(auto) {
    if (!state.startedAt) return;
    if (!auto) {
      var un = N - answered();
      var msg = un > 0 ? "You have " + un + " unanswered question" + (un === 1 ? "" : "s") + ". Submit anyway?" : "Submit the test now?";
      if (!confirm(msg)) return;
    }
    if (ticker) { clearInterval(ticker); ticker = null; }
    var timeSec = Math.min(TOTAL_SEC, elapsed());
    var result = core.score(Q, state.answers, exam);
    var attempt = {
      exam: exam.id, title: exam.title, set: exam.set, name: state.name, at: new Date().toISOString(),
      marks: result.marks, max: result.max, pct: result.pct, correct: result.correct, wrong: result.wrong,
      skipped: result.skipped, timeSec: timeSec, auto: !!auto
    };
    var list = attempts();
    list.unshift(attempt);
    saveJSON(localStorage, ATT_KEY, list.slice(0, 100));
    saveJSON(localStorage, LAST_KEY, { attempt: attempt, answers: state.answers });
    try { sessionStorage.removeItem(PROG_KEY); } catch (e) { /* ignore */ }
    state.startedAt = null;
    renderReport(attempt, result);
    show("report");
  }

  function renderReport(attempt, result) {
    lastResult = result; lastAttempt = attempt;
    var pct = result.pct, grade = core.grade(pct);
    var secRows = result.sections.map(function (s) {
      var name = data.sections[s.sec] ? data.sections[s.sec].name : "Section " + (s.sec + 1);
      return "<tr><td>" + esc(name) + "</td><td>" + s.correct + " / " + s.total + "</td><td>" + s.wrong + "</td><td>" + s.skipped +
        "</td><td>" + s.marks + " / " + s.max + "</td><td><span class=\"rep-mini\"><i style=\"width:" + s.pct + "%\"></i></span> " + s.pct + "%</td></tr>";
    }).join("");
    var weak = core.weakTopics(result.topics);
    var weakHtml = weak.length ? "<ol class=\"rep-weak\">" + weak.map(function (t) {
      var links = "";
      if (t.url) links += ' <a href="' + esc(t.url) + '">Revise →</a>';
      if (t.practice) links += ' <a href="' + esc(t.practice) + '">Practise →</a>';
      return "<li><strong>" + esc(t.topic) + "</strong> <span class=\"hint\">" + esc(t.src) + " · " + t.correct + "/" + t.total +
        " correct</span>" + links + "</li>";
    }).join("") + "</ol>" : '<p class="hint">Nothing flagged — every topic scored 60% or better. Try the next set.</p>';
    var map = result.per.map(function (st, i) {
      var sym = st === "correct" ? "✓" : st === "wrong" ? "✗" : "–";
      return '<button type="button" class="qmap-c is-' + st + '" data-review="' + i + '" title="Q' + (i + 1) + " " + st + '">' + (i + 1) + "<i>" + sym + "</i></button>";
    }).join("");
    var avg = N ? Math.round(attempt.timeSec / N) : 0;
    var html =
      '<div class="rep">' +
      '<div class="rep-head"><div><p class="kicker">SCORE REPORT · MOCK TEST' + (attempt.auto ? " · AUTO-SUBMITTED AT TIME-OUT" : "") + "</p>" +
      "<h2>" + esc(exam.title) + " — Set " + exam.set + "</h2>" +
      '<p class="rep-meta">' + (attempt.name ? "<strong>" + esc(attempt.name) + "</strong> · " : "") + esc(fmtDate(attempt.at)) +
      " · " + N + " questions · " + core.fmtTime(TOTAL_SEC) + " · +" + exam.marksCorrect + (exam.marksWrong ? " / −" + exam.marksWrong : ", no negative") + "</p></div>" +
      '<div class="rep-score"><span class="rep-big">' + result.marks + '</span><span class="rep-of">/ ' + result.max + "</span>" +
      '<span class="rep-pct">' + pct + "%</span><span class=\"rep-grade\">" + esc(grade) + "</span></div></div>" +
      '<div class="bar rep-bar"><span class="fill" style="width:' + pct + '%"></span></div>' +
      '<div class="rep-stats">' +
      "<div><strong>" + result.correct + "</strong><span>Correct</span></div>" +
      "<div><strong>" + result.wrong + "</strong><span>Wrong</span></div>" +
      "<div><strong>" + result.skipped + "</strong><span>Unattempted</span></div>" +
      "<div><strong>" + result.accuracy + "%</strong><span>Accuracy</span></div>" +
      (exam.marksWrong ? "<div><strong>−" + result.negative + "</strong><span>Lost to negatives</span></div>" : "") +
      "<div><strong>" + core.fmtTime(attempt.timeSec) + "</strong><span>Time used</span></div>" +
      "<div><strong>" + avg + " s</strong><span>Per question</span></div>" +
      "</div>" +
      '<div class="rep-cols"><div><h3>Section-wise</h3><div class="tablewrap"><table class="rep-table"><thead><tr><th>Section</th><th>Correct</th><th>Wrong</th><th>Skipped</th><th>Marks</th><th>%</th></tr></thead><tbody>' +
      secRows + "</tbody></table></div></div>" +
      "<div><h3>Revise first</h3>" + weakHtml + "</div></div>" +
      '<h3>Question map <span class="hint">click a question to review it</span></h3><div class="qmap">' + map + "</div>" +
      '<p class="rep-foot">Generated on this device · Class 10 CBSE study hub · ' + SITE_URL + "/mock-test/" + esc(exam.id) + "/set-" + exam.set + ".html · original practice material, not an official paper.</p>" +
      '<p class="btnrow no-print">' +
      '<button type="button" class="btn primary" data-act="print">Download report (PDF / print)</button>' +
      '<button type="button" class="btn" data-act="txt">Download report (.txt)</button>' +
      '<button type="button" class="btn" data-act="review">Review answers</button>' +
      '<button type="button" class="btn" data-act="retake">Retake this set</button>' +
      '<a class="btn" href="index.html">Other sets</a>' +
      "</p></div>";
    views.report.innerHTML = html;
  }

  function renderReview(filter, focus) {
    var box = $("[data-mock-review]");
    var answers = lastAttemptAnswers();
    var html = "";
    for (var i = 0; i < N; i++) {
      var st = lastResult.per[i];
      if (filter !== "all" && st !== filter) continue;
      var q = Q[i], mine = answers[i];
      var opts = "";
      for (var k = 0; k < q.opts.length; k++) {
        var cls = "rev-opt";
        if (k === q.ans) cls += " is-right";
        if (mine === k && k !== q.ans) cls += " is-wrong";
        opts += '<li class="' + cls + '"><span class="mock-lab">(' + esc(q.labels[k]) + ")</span> " + q.opts[k] +
          (k === q.ans ? ' <em class="rev-tag">correct</em>' : "") + (mine === k && k !== q.ans ? ' <em class="rev-tag">your answer</em>' : "") + "</li>";
      }
      html += '<article class="qcard rev-card is-' + st + '" id="rev-' + i + '"><div class="qmeta"><span class="qbadge qbadge-' +
        (st === "correct" ? "a" : st === "wrong" ? "c" : "s") + '">' + st.toUpperCase() + "</span>" +
        '<span class="qcode">Q' + (i + 1) + " · " + esc(sectionName(i)) + "</span><span class=\"qcode\">" + esc(q.topic) + "</span></div>" +
        '<p class="qtext"><strong>' + (i + 1) + ".</strong> " + (q.ctx ? '<span class="mock-ctx-inline">[' + q.ctx + "]</span> " : "") + q.stem + "</p><ul class=\"rev-opts\">" + opts + "</ul>" +
        '<div class="ans"><p><strong>Explanation:</strong> ' + q.exp + "</p>" +
        (q.url ? '<p><a href="' + esc(q.url) + '">Read the chapter →</a> · <a href="' + esc(q.practice) + '">Practise it →</a></p>' : "") +
        "</div></article>";
    }
    box.innerHTML = html || '<p class="hint">No questions in this filter.</p>';
    each("[data-mock-filter]", function (b) { b.classList.toggle("is-on", b.getAttribute("data-mock-filter") === filter); }, app);
    show("review");
    if (focus !== undefined) {
      var target = document.getElementById("rev-" + focus);
      if (target) setTimeout(function () { target.scrollIntoView({ block: "start", behavior: "smooth" }); }, 50);
    }
  }
  function lastAttemptAnswers() {
    if (state.answers.some(function (a) { return a !== null; })) return state.answers;
    var last = loadJSON(localStorage, LAST_KEY, null);
    return last && last.answers ? last.answers : state.answers;
  }

  function retake() {
    for (var i = 0; i < N; i++) { state.answers[i] = null; state.marked[i] = false; }
    state.current = 0; state.startedAt = null;
    try { sessionStorage.removeItem(PROG_KEY); } catch (e) { /* ignore */ }
    show("intro");
    showLast();
  }

  function showLast() {
    var box = $("[data-mock-last]");
    var last = loadJSON(localStorage, LAST_KEY, null);
    if (!box || !last || !last.attempt) return;
    var a = last.attempt;
    box.innerHTML = '<div class="callout"><p><strong>Last attempt on this device:</strong> ' + a.marks + " / " + a.max + " (" + a.pct +
      "%) on " + esc(fmtDate(a.at)) + '. <button type="button" class="btn" data-act="last-report">View that report</button></p></div>';
    box.hidden = false;
  }

  function openLastReport() {
    var last = loadJSON(localStorage, LAST_KEY, null);
    if (!last || !last.answers) return false;
    for (var i = 0; i < N; i++) state.answers[i] = last.answers[i] === undefined ? null : last.answers[i];
    renderReport(last.attempt, core.score(Q, state.answers, exam));
    show("report");
    return true;
  }

  /* --- events (delegated) --- */
  app.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target.closest("[data-act], [data-go], [data-review], [data-mock-filter], [data-mock-start], [data-mock-submit], [data-mock-back-report]") : null;
    if (!t) return;
    if (t.hasAttribute("data-mock-start")) return start();
    if (t.hasAttribute("data-mock-submit")) return submit(false);
    if (t.hasAttribute("data-mock-back-report")) return show("report");
    if (t.hasAttribute("data-go")) return go(parseInt(t.getAttribute("data-go"), 10));
    if (t.hasAttribute("data-review")) return renderReview("all", parseInt(t.getAttribute("data-review"), 10));
    if (t.hasAttribute("data-mock-filter")) return renderReview(t.getAttribute("data-mock-filter"));
    var act = t.getAttribute("data-act"), i = state.current;
    if (act === "prev") go(i - 1);
    else if (act === "next") {
      if (i < N - 1) go(i + 1);
      else { var first = state.answers.indexOf(null); go(first === -1 ? 0 : first); }
    }
    else if (act === "clear") { state.answers[i] = null; saveProgress(); render(); }
    else if (act === "mark") { state.marked[i] = !state.marked[i]; saveProgress(); render(); }
    else if (act === "print") window.print();
    else if (act === "txt") download("mock-report-" + exam.id + "-set" + exam.set + ".txt", core.reportText(data, lastResult, lastAttempt, SITE_URL));
    else if (act === "review") renderReview("all");
    else if (act === "retake") retake();
    else if (act === "last-report") openLastReport();
  });
  app.addEventListener("change", function (e) {
    var input = e.target;
    if (input && input.type === "radio" && input.name === "q" + state.current) {
      state.answers[state.current] = parseInt(input.value, 10);
      saveProgress();
      render();
    }
  });
  document.addEventListener("keydown", function (e) {
    if (views.test.hidden || /INPUT|TEXTAREA|SELECT/.test((e.target && e.target.tagName) || "")) return;
    if (e.key === "ArrowRight") { go(state.current + 1); e.preventDefault(); }
    else if (e.key === "ArrowLeft") { go(state.current - 1); e.preventDefault(); }
    else if (/^[1-4]$/.test(e.key)) {
      var k = parseInt(e.key, 10) - 1;
      if (k < Q[state.current].opts.length) { state.answers[state.current] = k; saveProgress(); render(); }
    }
  });

  /* --- boot: resume, reopen last report, or show the intro --- */
  var saved = loadJSON(sessionStorage, PROG_KEY, null);
  if (saved && saved.startedAt && saved.answers && saved.answers.length === N) {
    state = saved;
    if (nameInput) nameInput.value = state.name || "";
    if (TOTAL_SEC - Math.floor((Date.now() - state.startedAt) / 1000) > 0) {
      show("test");
      render();
      startTimer();
    } else {
      submit(true);
    }
  } else if (location.hash === "#report" && openLastReport()) {
    /* reopened from the attempts table */
  } else {
    show("intro");
    showLast();
  }
})(this);
