/* Mock-test engine for the Class 10 CBSE study hub.
 *
 * One file, three jobs:
 *   1. the engine page (test.html): generates a fresh paper from the
 *      embedded pool on every attempt (avoiding questions already served on
 *      this device), runs the timed test, scores it, renders the one-page
 *      report, the answer review and the printable paper, and builds the
 *      .txt downloads — all in the browser;
 *   2. attempt history on the centre and exam pages (localStorage only —
 *      nothing leaves the browser);
 *   3. best-score lines per exam and per mock slot.
 *
 * The generator and scoring helpers live in `core` and are exported for
 * Node so the repository tests can check them without a browser.
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

  core.fmtMinutes = function (m) {
    m = Math.max(1, Math.floor(Number(m) || 0));
    var h = Math.floor(m / 60), r = m % 60;
    if (h && r) return h + " h " + r + " min";
    if (h) return h + " h";
    return r + " min";
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

  /* Strip the payload's inline HTML back to plain text for the .txt files. */
  core.plainText = function (s) {
    return String(s)
      .replace(/<[^>]*>/g, "")
      .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'").replace(/&amp;/g, "&")
      .replace(/\s+/g, " ")
      .trim();
  };

  /* ---------------- the question generator ---------------- */

  core.shuffle = function (arr, rand) {
    var r = rand || Math.random;
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(r() * (i + 1));
      var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }
    return arr;
  };

  function toSet(list) {
    var s = {};
    if (!list) return s;
    if (list.forEach) { list.forEach(function (x) { s[x] = true; }); return s; }
    Object.keys(list).forEach(function (k) { s[list[k]] = true; });
    return s;
  }

  /* Pick `count` ids from `ids`, preferring questions never served before
   * (not in `seenSet`), then old ones that were not in the immediately
   * previous batch (`lastSet`), and only then the previous batch itself.
   * `usedSet` holds ids already picked for this paper (kept out of other
   * sections). All three are uid -> true maps as built by toSet(). */
  core.pickIds = function (ids, count, seenSet, lastSet, usedSet, rand) {
    var fresh = [], mid = [], back = [];
    ids.forEach(function (id) {
      if (usedSet[id]) return;
      if (!seenSet[id]) fresh.push(id);
      else if (!lastSet[id]) mid.push(id);
      else back.push(id);
    });
    core.shuffle(fresh, rand); core.shuffle(mid, rand); core.shuffle(back, rand);
    return fresh.concat(mid, back).slice(0, count);
  };

  /* sections: [{name, count, ids: [uid…]}]; byId: {uid: question}.
   * Returns {questions: [...with sec + n], fresh: n} — the paper. */
  core.generate = function (sections, byId, seen, last, rand) {
    var seenSet = toSet(seen), lastSet = toSet(last), usedSet = {};
    var out = [], fresh = 0;
    sections.forEach(function (sec, si) {
      var ids = core.pickIds(sec.ids, sec.count, seenSet, lastSet, usedSet, rand);
      var qs = ids.map(function (id) { return byId[id]; }).filter(Boolean)
        .sort(function (a, b) { return (a.ord - b.ord) || (a.uid > b.uid ? 1 : a.uid < b.uid ? -1 : 0); });
      qs.forEach(function (q) {
        var item = copy(q);
        item.sec = si;
        if (!seenSet[q.uid]) fresh++;
        usedSet[q.uid] = true;
        out.push(item);
      });
    });
    out.forEach(function (q, i) { q.n = i + 1; });
    return { questions: out, fresh: fresh, total: out.length };
  };

  function copy(o) {
    var c = {};
    Object.keys(o).forEach(function (k) { c[k] = o[k]; });
    return c;
  }

  /* ---------------- text builders (report / paper / key) ---------------- */

  core.markingText = function (m) {
    return "+" + m.marksCorrect + " correct \u00b7 " +
      (m.marksWrong ? "\u2212" + m.marksWrong + " wrong" : "no negative marking");
  };

  core.reportText = function (meta, result, attempt, questions) {
    var lines = [];
    var rule = "=".repeat(64);
    lines.push("SCORE REPORT - " + meta.title + " - " + meta.label);
    lines.push(rule);
    if (attempt.name) lines.push("Name    : " + attempt.name);
    lines.push("Date    : " + new Date(attempt.at).toLocaleString());
    lines.push("Score   : " + result.marks + " / " + result.max + " (" + result.pct + "%) - " + core.grade(result.pct));
    lines.push("Correct " + result.correct + " | Wrong " + result.wrong + " | Unattempted " + result.skipped +
      " | Accuracy " + result.accuracy + "%" + (result.negative ? " | Lost to negatives -" + result.negative : ""));
    lines.push("Time    : " + core.fmtTime(attempt.timeSec) + " of " + core.fmtTime(meta.minutes * 60) +
      (attempt.auto ? " (auto-submitted at time-out)" : ""));
    lines.push("");
    lines.push("Section-wise");
    result.sections.forEach(function (s) {
      var name = meta.sections[s.sec] ? meta.sections[s.sec].name : ("Section " + (s.sec + 1));
      lines.push("  " + pad(name, 34) + pad(s.correct + "/" + s.total, 8) + pad(s.marks + "/" + s.max, 10) + s.pct + "%");
    });
    var weak = core.weakTopics(result.topics);
    if (weak.length) {
      lines.push("");
      lines.push("Revise first");
      weak.forEach(function (t) {
        lines.push("  " + t.topic + " (" + t.src + "): " + t.correct + "/" + t.total + " correct");
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
    lines.push(meta.onlineUrl);
    return lines.join("\n");

    function pad(s, n) { s = String(s); while (s.length < n) s += " "; return s; }
  };

  core.paperText = function (meta, questions) {
    var rule = "=".repeat(72);
    var lines = [
      "CLASS 10 CBSE STUDY HUB - MOCK TEST (GENERATED)",
      rule,
      "Exam    : " + meta.title + " (" + meta.code + ")",
      "Paper   : " + meta.label,
      "Time    : " + core.fmtMinutes(meta.minutes),
      "Marks   : " + meta.maxMarks + " (" + core.markingText(meta.marking) + ")",
      "Pattern : " + (meta.length || "Mock") + " - " + (meta.patternNote || ""),
      rule,
      "",
      "Instructions",
      "1. Each question has exactly one correct option.",
      "2. Write your answers in the answer grid at the end, then check the key file.",
      "3. " + core.markingText(meta.marking) + "; unattempted questions score 0.",
      "",
    ];
    var currentSec = null;
    questions.forEach(function (q) {
      if (q.sec !== currentSec) {
        currentSec = q.sec;
        var name = meta.sections[q.sec] ? meta.sections[q.sec].name : ("Section " + (q.sec + 1));
        var title = "SECTION " + String.fromCharCode(65 + q.sec) + " - " + name;
        lines.push("", title, "-".repeat(title.length), "");
      }
      var ctx = q.ctx ? "[" + core.plainText(q.ctx) + "] " : "";
      lines.push("Q" + q.n + ". " + ctx + core.plainText(q.stem));
      q.labels.forEach(function (l, i) {
        lines.push("    (" + l + ") " + core.plainText(q.opts[i]));
      });
      lines.push("");
    });
    lines.push("", "ANSWER GRID", "-".repeat(11));
    var row = [];
    questions.forEach(function (q) {
      row.push("Q" + ("   " + q.n).slice(-3) + " [   ]");
      if (row.length === 5) { lines.push(row.join("  ")); row = []; }
    });
    if (row.length) lines.push(row.join("  "));
    lines.push([
      "",
      rule,
      "Answer key : the key .txt file generated with this paper",
      "Score online: " + meta.onlineUrl,
      "Original practice material from the Class 10 CBSE study hub - not an official paper.",
      "Created by Mohammad Umair.",
      "",
    ].join("\n"));
    return lines.join("\n");
  };

  core.keyText = function (meta, questions) {
    var rule = "=".repeat(72);
    var lines = [
      "ANSWER KEY - " + meta.title + " (" + meta.code + ") - " + meta.label,
      rule,
      "Marking: " + core.markingText(meta.marking) + ". Score = correct x " + meta.marking.marksCorrect +
        (meta.marking.marksWrong ? " - wrong x " + meta.marking.marksWrong : "") +
        ". Maximum " + meta.maxMarks + ".",
      "",
      "Quick key",
    ];
    var row = [];
    questions.forEach(function (q) {
      row.push("Q" + ("   " + q.n).slice(-3) + " (" + q.labels[q.ans] + ")");
      if (row.length === 6) { lines.push(row.join("  ")); row = []; }
    });
    if (row.length) lines.push(row.join("  "));
    lines.push("", "Explanations", "-".repeat(12), "");
    questions.forEach(function (q) {
      lines.push("Q" + q.n + ". " + core.plainText(q.exp));
      lines.push("      Topic: " + q.topic + " (" + q.src + ")");
      lines.push("");
    });
    lines.push(rule, "Paper: the paper .txt file generated with this key  |  Online: " + meta.onlineUrl, "");
    return lines.join("\n");
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
    try {
      var blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
    } catch (e) { /* very old browsers / test runners */ }
  }
  function each(sel, fn, scope) {
    Array.prototype.forEach.call((scope || document).querySelectorAll(sel), fn);
  }
  function attemptLabel(a) {
    if (a.label) return a.label;
    return a.set ? "Set " + a.set : "—";
  }
  function attemptHref(a) {
    if (!a.mode) return null; /* attempts from the old fixed-set pages */
    if (a.mode === "chapter") return a.exam + "/test.html?chapter=" + encodeURIComponent(a.chapter) + "#report";
    return a.exam + "/test.html?n=" + a.slot + "#report";
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
    el.innerHTML = "Best on this device: <strong>" + b.marks + " / " + b.max + "</strong> (" + b.pct + "%, " +
      esc(attemptLabel(b)) + ") \u00b7 " + mine.length + " attempt" + (mine.length === 1 ? "" : "s");
    el.className += " has-score";
  });
  var recent = document.querySelector("[data-mock-recent]");
  if (recent && all.length) {
    var rows = document.querySelector("[data-mock-recent-rows]");
    all.slice(0, 12).forEach(function (a) {
      var tr = document.createElement("tr");
      var href = attemptHref(a);
      tr.innerHTML = "<td>" + esc(fmtDate(a.at)) + "</td><td>" + esc(a.title) + "</td><td>" + esc(attemptLabel(a)) + "</td>" +
        "<td>" + a.marks + " / " + a.max + "</td><td>" + a.pct + "%</td><td>" + core.fmtTime(a.timeSec) + "</td>" +
        "<td>" + (href ? '<a href="' + esc(href) + '">Report</a>' : "") + "</td>";
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

  /* ---- exam page: attempts table + best per mock slot ---- */
  each("[data-mock-attempts]", function (el) {
    var id = el.getAttribute("data-mock-attempts");
    var mine = all.filter(function (a) { return a.exam === id; });
    if (!mine.length) return;
    var b = bestOf(mine);
    var html = '<p><strong>Best: ' + b.marks + " / " + b.max + " (" + b.pct + "%)</strong> on " +
      esc(attemptLabel(b)) + " \u00b7 " + mine.length + " attempt" + (mine.length === 1 ? "" : "s") + "</p>" +
      '<div class="tablewrap"><table><thead><tr><th>When</th><th>Paper</th><th>Score</th><th>%</th>' +
      "<th>Correct / wrong / skipped</th><th>Time</th><th></th></tr></thead><tbody>";
    mine.slice(0, 20).forEach(function (a) {
      var href = attemptHref(a);
      var localHref = href ? href.replace(/^[^/]+\//, "") : null;
      html += "<tr><td>" + esc(fmtDate(a.at)) + "</td><td>" + esc(attemptLabel(a)) + "</td><td>" + a.marks + " / " + a.max +
        "</td><td>" + a.pct + "%</td><td>" + a.correct + " / " + a.wrong + " / " + a.skipped + "</td><td>" +
        core.fmtTime(a.timeSec) + "</td><td>" +
        (localHref ? '<a href="' + esc(localHref) + '">Report</a>' : "") + "</td></tr>";
    });
    html += "</tbody></table></div>";
    el.innerHTML = html;
  });
  each("[data-mock-slot-best]", function (el) {
    var parts = el.getAttribute("data-mock-slot-best").split("/");
    var mine = all.filter(function (a) {
      return a.exam === parts[0] && (a.mode === "exam" ? String(a.slot) === parts[1] : (!a.mode && String(a.set) === parts[1]));
    });
    if (!mine.length) return;
    var b = bestOf(mine);
    el.innerHTML = "<strong>" + b.marks + " / " + b.max + "</strong> (" + b.pct + "%)";
  });

  /* ---- the engine page ---- */
  var app = document.getElementById("mock");
  var dataEl = document.getElementById("mock-data");
  if (!app || !dataEl) return;

  var data = JSON.parse(dataEl.textContent);
  var exam = data.exam;

  /* pool: compact payload keys -> the full names the renderers expect */
  var POOL = {};
  data.pool.forEach(function (q) {
    POOL[q.uid] = {
      uid: q.uid, stem: q.s, opts: q.o, labels: q.l, ans: q.a, exp: q.e,
      topic: q.t, topicKey: q.k, ctx: q.c, src: q.src, url: q.u, practice: q.p,
      ord: q.ord, ch: q.ch
    };
  });

  /* mode: ?chapter=<id> for a chapter mock, else ?n=<slot> for a full mock */
  var params = (typeof URLSearchParams !== "undefined" && location.search)
    ? new URLSearchParams(location.search) : { get: function () { return null; } };
  var chapters = data.chapters || [];
  var chParam = params.get("chapter");
  var chapter = null;
  for (var ci = 0; ci < chapters.length; ci++) {
    if (chapters[ci].id === chParam) { chapter = chapters[ci]; break; }
  }
  var mode = chapter ? "chapter" : "exam";
  var slot = parseInt(params.get("n"), 10);
  if (!slot || slot < 1 || slot > exam.tests) slot = 1;

  var sections, marking, minutes, label, maxMarks, onlinePath;
  if (mode === "chapter") {
    var chIds = data.pool.filter(function (q) { return q.ch === chapter.id; }).map(function (q) { return q.uid; });
    sections = [{ name: "Ch " + chapter.num + " \u00b7 " + chapter.title, count: chIds.length, ids: chIds }];
    marking = { marksCorrect: 1, marksWrong: 0 };
    minutes = Math.max(5, chIds.length);
    label = "Ch " + chapter.num + " \u00b7 " + chapter.title;
    onlinePath = "test.html?chapter=" + encodeURIComponent(chapter.id);
  } else {
    sections = data.sections;
    marking = { marksCorrect: exam.marksCorrect, marksWrong: exam.marksWrong };
    minutes = exam.minutes;
    label = "Mock " + slot;
    onlinePath = "test.html?n=" + slot;
  }
  maxMarks = sections.reduce(function (m, s) { return m + s.count * marking.marksCorrect; }, 0);

  var meta = {
    title: exam.title, code: exam.code, label: label, minutes: minutes,
    marking: marking, maxMarks: maxMarks, length: exam.length,
    patternNote: exam.patternNote, sections: sections,
    onlineUrl: SITE_URL + "/mock-test/" + exam.id + "/" + onlinePath
  };
  var fileTag = mode === "chapter" ? "ch-" + chapter.id : "m" + slot;

  var KEY = exam.id + "/" + (mode === "chapter" ? "ch/" + chapter.id : "s/" + slot);
  var PROG_KEY = "c10cbse-mock-progress:" + KEY;
  var LAST_KEY = "c10cbse-mock-last:" + KEY;
  var SEEN_KEY = "c10cbse-mock-seen:" + exam.id;
  var TOTAL_SEC = minutes * 60;

  var views = {};
  each("[data-view]", function (v) { views[v.getAttribute("data-view")] = v; }, app);
  var $ = function (sel) { return app.querySelector(sel); };
  var nameInput = $("[data-mock-name]");
  var timerEl = $("[data-mock-timer]");
  var progressEl = $("[data-mock-progress]");
  var sectionEl = $("[data-mock-section]");
  var qEl = $("[data-mock-question]");
  var palEl = $("[data-mock-palette]");
  var freshEl = $("[data-mock-fresh]");
  var h1El = document.querySelector("[data-mock-h1]");
  var ledeEl = document.querySelector("[data-mock-lede]");
  var slotsEl = document.querySelector("[data-mock-slots]");

  var Q = [];
  var state = { ids: [], answers: [], marked: [], current: 0, startedAt: null, name: "" };
  var ticker = null;
  var lastResult = null, lastAttempt = null;
  var poolSize = data.pool.length;

  /* --- headers, slot chips --- */
  if (h1El) h1El.textContent = "\u2014 " + label;
  if (ledeEl) {
    ledeEl.innerHTML = mode === "chapter"
      ? "A chapter mock on <strong>" + esc(chapter.title) + "</strong> — every MCQ of the chapter (" +
        sections[0].count + "), " + core.fmtMinutes(minutes) + ", +1 per correct answer, no negative marking."
      : exam.questions + " questions \u00b7 " + core.fmtMinutes(minutes) + " \u00b7 " +
        esc(core.markingText(marking)) + ". Generated fresh from a pool of " + poolSize +
        " questions — answer on screen, submit, and get your score with a one-page report.";
  }
  if (slotsEl) {
    var chips = "";
    if (mode === "chapter") {
      var idx = chapters.indexOf(chapter);
      if (idx > 0) chips += '<a class="chip" href="test.html?chapter=' + esc(chapters[idx - 1].id) + '">\u2190 ' +
        "Ch " + chapters[idx - 1].num + "</a>";
      chips += '<span class="chip is-on">Ch ' + chapter.num + " \u00b7 " + esc(chapter.title) + "</span>";
      if (idx > -1 && idx < chapters.length - 1) chips += '<a class="chip" href="test.html?chapter=' +
        esc(chapters[idx + 1].id) + '">Ch ' + chapters[idx + 1].num + " \u2192</a>";
      chips += '<a class="chip" href="index.html#chapters">All chapter mocks</a>';
    } else {
      for (var s = 1; s <= exam.tests; s++) {
        chips += s === slot
          ? '<span class="chip is-on">Mock ' + s + "</span>"
          : '<a class="chip" href="test.html?n=' + s + '">Mock ' + s + "</a>";
      }
    }
    slotsEl.innerHTML = chips;
  }

  function show(name) {
    Object.keys(views).forEach(function (k) { views[k].hidden = k !== name; });
    document.body.classList.toggle("mock-print-report", name === "report");
    document.body.classList.toggle("mock-print-paper", name === "paper");
    document.body.classList.toggle("mock-in-test", name === "test");
    if (name !== "intro") {
      var top = app.getBoundingClientRect().top + window.pageYOffset - 8;
      try { window.scrollTo({ top: top, behavior: "smooth" }); } catch (e) { window.scrollTo(0, top); }
    }
  }
  function saveProgress() { saveJSON(sessionStorage, PROG_KEY, state); }
  function elapsed() { return Math.floor((Date.now() - state.startedAt) / 1000); }
  function remaining() { return Math.max(0, TOTAL_SEC - elapsed()); }

  function sectionName(i) { return sections[Q[i].sec] ? sections[Q[i].sec].name : ""; }
  function answered() { return state.answers.filter(function (a) { return a !== null && a !== undefined; }).length; }

  /* --- the generator --- */
  function generatePaper() {
    var seenStore = loadJSON(localStorage, SEEN_KEY, { ids: [], last: [] });
    if (!seenStore.ids) seenStore.ids = [];
    if (!seenStore.last) seenStore.last = [];
    var gen = core.generate(sections, POOL, seenStore.ids, seenStore.last);
    Q = gen.questions;
    state = { ids: Q.map(function (q) { return q.uid; }), answers: [], marked: [], current: 0, startedAt: null, name: state.name || "" };
    for (var i = 0; i < Q.length; i++) { state.answers.push(null); state.marked.push(false); }
    seenStore.last = state.ids.slice();
    state.ids.forEach(function (id) {
      if (seenStore.ids.indexOf(id) < 0) seenStore.ids.push(id);
    });
    if (seenStore.ids.length > 2000) seenStore.ids = seenStore.ids.slice(-2000);
    saveJSON(localStorage, SEEN_KEY, seenStore);
    renderFreshLine(gen.fresh, seenStore);
  }

  function renderFreshLine(fresh, seenStore) {
    if (!freshEl) return;
    var repeats = Q.length - fresh;
    var seenCount = seenStore ? seenStore.ids.length : 0;
    var txt = "<strong>This paper: " + Q.length + " questions</strong> \u2014 " + fresh + " never served to you before";
    if (repeats) txt += ", " + repeats + " repeated (the pool of " + poolSize + " has cycled on this device)";
    else txt += " \u2014 none repeated";
    txt += ". You have been served " + seenCount + " of the " + poolSize +
      " questions in this pool. <em>Every attempt picks a different paper.</em>";
    freshEl.innerHTML = txt;
  }

  function restorePaper(ids) {
    Q = ids.map(function (id) { return POOL[id]; }).filter(Boolean);
    Q.forEach(function (q, i) { q.n = i + 1; });
    /* recompute which section each question belongs to */
    var byIdSec = {};
    sections.forEach(function (sec, si) {
      sec.ids.forEach(function (id) { byIdSec[id] = si; });
    });
    Q.forEach(function (q) { q.sec = byIdSec[q.uid] !== undefined ? byIdSec[q.uid] : 0; });
  }

  /* --- rendering: question, palette --- */
  function renderQuestion() {
    var i = state.current, q = Q[i];
    var html = '<div class="mock-q-head"><span class="mock-q-num">Question ' + (i + 1) + " of " + Q.length + "</span>" +
      '<span class="mock-q-sec">' + esc(sectionName(i)) + "</span>" +
      '<span class="marks">' + marking.marksCorrect + " mark" + (marking.marksCorrect === 1 ? "" : "s") +
      (marking.marksWrong ? " \u00b7 \u2212" + marking.marksWrong : "") + "</span></div>" +
      (q.ctx ? '<p class="mock-ctx">' + q.ctx + "</p>" : "") +
      '<p class="qtext">' + q.stem + '</p><div class="mock-opts" role="radiogroup">';
    for (var k = 0; k < q.opts.length; k++) {
      var on = state.answers[i] === k;
      html += '<label class="mock-opt' + (on ? " is-picked" : "") + '"><input type="radio" name="q' + i + '" value="' + k + '"' +
        (on ? " checked" : "") + '><span class="mock-lab">(' + esc(q.labels[k]) + ")</span><span>" + q.opts[k] + "</span></label>";
    }
    html += "</div>" +
      '<div class="mock-q-actions">' +
      '<button type="button" class="btn" data-act="prev"' + (i === 0 ? " disabled" : "") + ">\u2190 Previous</button>" +
      '<button type="button" class="btn" data-act="clear">Clear response</button>' +
      '<button type="button" class="btn' + (state.marked[i] ? " is-marked" : "") + '" data-act="mark">' +
      (state.marked[i] ? "Unmark review" : "Mark for review") + "</button>" +
      '<button type="button" class="btn primary" data-act="next">' + (i === Q.length - 1 ? "Go to first unanswered" : "Save & next \u2192") + "</button>" +
      "</div>";
    qEl.innerHTML = html;
    progressEl.textContent = answered() + " / " + Q.length + " answered";
    sectionEl.textContent = "Section " + String.fromCharCode(65 + q.sec) + " \u00b7 " + sectionName(i);
  }

  function renderPalette() {
    var html = "";
    var lastSec = -1;
    for (var i = 0; i < Q.length; i++) {
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
    if (i < 0 || i >= Q.length) return;
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
      var un = Q.length - answered();
      var msg = un > 0 ? "You have " + un + " unanswered question" + (un === 1 ? "" : "s") + ". Submit anyway?" : "Submit the test now?";
      if (!confirm(msg)) return;
    }
    if (ticker) { clearInterval(ticker); ticker = null; }
    var timeSec = Math.min(TOTAL_SEC, elapsed());
    var result = core.score(Q, state.answers, marking);
    var attempt = {
      exam: exam.id, title: exam.title, label: label, mode: mode, slot: slot,
      chapter: mode === "chapter" ? chapter.id : null,
      name: state.name, at: new Date().toISOString(),
      marks: result.marks, max: result.max, pct: result.pct, correct: result.correct, wrong: result.wrong,
      skipped: result.skipped, timeSec: timeSec, auto: !!auto
    };
    var list = attempts();
    list.unshift(attempt);
    saveJSON(localStorage, ATT_KEY, list.slice(0, 200));
    saveJSON(localStorage, LAST_KEY, { attempt: attempt, answers: state.answers, ids: state.ids });
    try { sessionStorage.removeItem(PROG_KEY); } catch (e) { /* ignore */ }
    state.startedAt = null;
    renderReport(attempt, result);
    show("report");
  }

  function renderReport(attempt, result) {
    lastResult = result; lastAttempt = attempt;
    var pct = result.pct, grade = core.grade(pct);
    var secRows = result.sections.map(function (s) {
      var name = sections[s.sec] ? sections[s.sec].name : "Section " + (s.sec + 1);
      return "<tr><td>" + esc(name) + "</td><td>" + s.correct + " / " + s.total + "</td><td>" + s.wrong + "</td><td>" + s.skipped +
        "</td><td>" + s.marks + " / " + s.max + "</td><td><span class=\"rep-mini\"><i style=\"width:" + s.pct + "%\"></i></span> " + s.pct + "%</td></tr>";
    }).join("");
    var weak = core.weakTopics(result.topics);
    var weakHtml = weak.length ? "<ol class=\"rep-weak\">" + weak.map(function (t) {
      var links = "";
      if (t.url) links += ' <a href="' + esc(t.url) + '">Revise \u2192</a>';
      if (t.practice) links += ' <a href="' + esc(t.practice) + '">Practise \u2192</a>';
      return "<li><strong>" + esc(t.topic) + "</strong> <span class=\"hint\">" + esc(t.src) + " \u00b7 " + t.correct + " / " + t.total +
        " correct</span>" + links + "</li>";
    }).join("") + "</ol>" : '<p class="hint">Nothing flagged \u2014 every topic scored 60% or better. Try the next mock.</p>';
    var map = result.per.map(function (st, i) {
      var sym = st === "correct" ? "\u2713" : st === "wrong" ? "\u2717" : "\u2013";
      return '<button type="button" class="qmap-c is-' + st + '" data-review="' + i + '" title="Q' + (i + 1) + " " + st + '">' + (i + 1) + "<i>" + sym + "</i></button>";
    }).join("");
    var avg = Q.length ? Math.round(attempt.timeSec / Q.length) : 0;
    var html =
      '<div class="rep">' +
      '<div class="rep-head"><div><p class="kicker">SCORE REPORT \u00b7 MOCK TEST' + (attempt.auto ? " \u00b7 AUTO-SUBMITTED AT TIME-OUT" : "") + "</p>" +
      "<h2>" + esc(exam.title) + " \u2014 " + esc(label) + "</h2>" +
      '<p class="rep-meta">' + (attempt.name ? "<strong>" + esc(attempt.name) + "</strong> \u00b7 " : "") + esc(fmtDate(attempt.at)) +
      " \u00b7 " + Q.length + " questions \u00b7 " + core.fmtTime(TOTAL_SEC) + " \u00b7 +" + marking.marksCorrect +
      (marking.marksWrong ? " / \u2212" + marking.marksWrong : ", no negative") + "</p></div>" +
      '<div class="rep-score"><span class="rep-big">' + result.marks + '</span><span class="rep-of">/ ' + result.max + "</span>" +
      '<span class="rep-pct">' + pct + "%</span><span class=\"rep-grade\">" + esc(grade) + "</span></div></div>" +
      '<div class="bar rep-bar"><span class="fill" style="width:' + pct + '%"></span></div>' +
      '<div class="rep-stats">' +
      "<div><strong>" + result.correct + "</strong><span>Correct</span></div>" +
      "<div><strong>" + result.wrong + "</strong><span>Wrong</span></div>" +
      "<div><strong>" + result.skipped + "</strong><span>Unattempted</span></div>" +
      "<div><strong>" + result.accuracy + "%</strong><span>Accuracy</span></div>" +
      (marking.marksWrong ? "<div><strong>\u2212" + result.negative + "</strong><span>Lost to negatives</span></div>" : "") +
      "<div><strong>" + core.fmtTime(attempt.timeSec) + "</strong><span>Time used</span></div>" +
      "<div><strong>" + avg + " s</strong><span>Per question</span></div>" +
      "</div>" +
      '<div class="rep-cols"><div><h3>Section-wise</h3><div class="tablewrap"><table class="rep-table"><thead><tr><th>Section</th><th>Correct</th><th>Wrong</th><th>Skipped</th><th>Marks</th><th>%</th></tr></thead><tbody>' +
      secRows + "</tbody></table></div></div>" +
      '<div><h3>Revise first</h3>' + weakHtml + "</div></div>" +
      '<h3>Question map <span class="hint">click a question to review it</span></h3><div class="qmap">' + map + "</div>" +
      '<p class="rep-foot">Generated on this device \u00b7 Class 10 CBSE study hub \u00b7 ' + meta.onlineUrl + " \u00b7 original practice material, not an official paper.</p>" +
      '<p class="btnrow no-print">' +
      '<button type="button" class="btn primary" data-act="print">Download report (PDF / print)</button>' +
      '<button type="button" class="btn" data-act="txt">Download report (.txt)</button>' +
      '<button type="button" class="btn" data-act="review">Review answers</button>' +
      '<button type="button" class="btn" data-act="paper">Printable paper</button>' +
      '<button type="button" class="btn" data-act="retake">Retake with new questions</button>' +
      '<a class="btn" href="index.html">All ' + esc(exam.title) + " mocks</a>" +
      "</p></div>";
    views.report.innerHTML = html;
  }

  function renderReview(filter, focus) {
    var box = $("[data-mock-review]");
    var answers = lastAttemptAnswers();
    var html = "";
    for (var i = 0; i < Q.length; i++) {
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
        '<span class="qcode">Q' + (i + 1) + " \u00b7 " + esc(sectionName(i)) + "</span><span class=\"qcode\">" + esc(q.topic) + "</span></div>" +
        '<p class="qtext"><strong>' + (i + 1) + ".</strong> " + (q.ctx ? '<span class="mock-ctx-inline">[' + q.ctx + "]</span> " : "") + q.stem + "</p><ul class=\"rev-opts\">" + opts + "</ul>" +
        '<div class="ans"><p><strong>Explanation:</strong> ' + q.exp + "</p>" +
        (q.url ? '<p><a href="' + esc(q.url) + '">Read the chapter \u2192</a> \u00b7 <a href="' + esc(q.practice) + '">Practise it \u2192</a></p>' : "") +
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
    generatePaper();
    state.startedAt = null;
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
    if (!last || !last.answers || !last.ids) return false;
    restorePaper(last.ids);
    if (Q.length !== last.answers.length) return false;
    state.answers = last.answers.map(function (a) { return a === undefined ? null : a; });
    state.ids = last.ids;
    renderReport(last.attempt, core.score(Q, state.answers, marking));
    show("report");
    return true;
  }

  /* --- the printable paper (rendered from the generated questions) --- */
  function renderPaper() {
    var tools = $("[data-paper-tools]");
    var body = $("[data-paper-body]");
    if (!tools || !body || !Q.length) return;
    tools.innerHTML =
      '<p class="btnrow">' +
      '<button type="button" class="btn primary" data-act="print-paper">Print / Save as PDF</button>' +
      '<button type="button" class="btn" data-act="txt-paper">Download paper (.txt)</button>' +
      '<button type="button" class="btn" data-act="txt-key">Answer key (.txt)</button>' +
      '<button type="button" class="btn" data-act="to-intro">\u2190 Back</button>' +
      "</p>" +
      "<p><label><input type=\"checkbox\" data-paper-key checked> Include the answer key and explanations when printing (it starts on a new page)</label> " +
      '<label class="paper-toggle"><input type="checkbox" data-paper-show-key> Show the key on screen now</label></p>' +
      '<p class="hint">This is the same generated paper as the online test. In the print dialog choose <em>Save as PDF</em> \u2014 portrait A4, default margins.</p>';

    var qsHtml = [];
    var currentSec = null;
    Q.forEach(function (q) {
      if (q.sec !== currentSec) {
        currentSec = q.sec;
        var first = q.n, lastQ = first + sections[q.sec].count - 1;
        qsHtml.push(
          '<h2 class="paper-sec">Section ' + String.fromCharCode(65 + q.sec) + " \u00b7 " + esc(sections[q.sec].name) +
          " <span>Q" + first + "\u2013Q" + lastQ + " \u00b7 " + (sections[q.sec].count * marking.marksCorrect) + " marks</span></h2>"
        );
      }
      var opts = q.labels.map(function (l, i) {
        return '<li><span class="paper-lab">(' + esc(l) + ")</span> " + q.opts[i] + "</li>";
      }).join("");
      var ctx = q.ctx ? '<span class="paper-ctx">[' + q.ctx + "]</span> " : "";
      qsHtml.push(
        '<div class="paper-q"><p class="paper-stem"><strong>' + q.n + ".</strong> " + ctx + q.stem + "</p>" +
        '<ul class="paper-opts">' + opts + "</ul></div>"
      );
    });

    var omr = Q.map(function (q) {
      return '<div class="omr-row"><span class="omr-n">' + q.n + "</span>" +
        q.labels.map(function (l) { return '<span class="omr-bubble">' + esc(l) + "</span>"; }).join("") + "</div>";
    }).join("");

    var keyRows = Q.map(function (q) {
      return "<tr><td>" + q.n + "</td><td><strong>(" + esc(q.labels[q.ans]) + ")</strong> " + q.opts[q.ans] +
        "</td><td>" + q.exp + "</td><td>" + esc(q.topic) + "</td></tr>";
    }).join("");

    body.innerHTML =
      '<header class="paper-head">' +
      '<p class="paper-brand">Class 10 CBSE study hub \u00b7 Mock test (generated)</p>' +
      "<h1>" + esc(exam.title) + " <small>" + esc(exam.code) + "</small></h1>" +
      '<p class="paper-set">' + esc(label) + " \u00b7 generated " + esc(fmtDate(new Date().toISOString())) + "</p>" +
      '<table class="paper-meta"><tbody>' +
      "<tr><th>Time allowed</th><td>" + core.fmtMinutes(minutes) + "</td><th>Maximum marks</th><td>" + maxMarks + "</td></tr>" +
      "<tr><th>Questions</th><td>" + Q.length + "</td><th>Marking</th><td>" + esc(core.markingText(marking)) + "</td></tr>" +
      '<tr><th>Name</th><td class="paper-blank"></td><th>Date</th><td class="paper-blank"></td></tr>' +
      "</tbody></table>" +
      '<ol class="paper-instr">' +
      "<li>All questions are compulsory unless you are practising negative marking; each has exactly one correct option.</li>" +
      "<li>Mark your answers on the answer grid at the end, then check them against the key.</li>" +
      "<li>" + esc(exam.length || "Mock") + " \u2014 pattern: " + esc(exam.patternNote || "") + "</li>" +
      "</ol></header>" +
      '<main class="paper-qs">' + qsHtml.join("") + "</main>" +
      '<section class="paper-omr"><h2>Answer grid</h2><div class="omr">' + omr + "</div></section>" +
      '<section class="paper-key" data-paper-key-block>' +
      "<h2>Answer key &amp; explanations \u2014 " + esc(exam.title) + " \u00b7 " + esc(label) + "</h2>" +
      '<div class="tablewrap"><table class="key-table"><thead><tr><th>Q</th><th>Answer</th><th>Why</th><th>Topic</th></tr></thead>' +
      "<tbody>" + keyRows + "</tbody></table></div></section>" +
      '<footer class="paper-foot">Original practice material from ' + SITE_URL + "/ \u2014 not an official paper. Created by Mohammad Umair." +
      " Score this paper online: " + meta.onlineUrl + "</footer>";

    var paper = app.querySelector("[data-paper]");
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
      if (i < Q.length - 1) go(i + 1);
      else { var first = state.answers.indexOf(null); go(first === -1 ? 0 : first); }
    }
    else if (act === "clear") { state.answers[i] = null; saveProgress(); render(); }
    else if (act === "mark") { state.marked[i] = !state.marked[i]; saveProgress(); render(); }
    else if (act === "print") window.print();
    else if (act === "print-paper") window.print();
    else if (act === "txt") download("mock-report-" + exam.id + "-" + fileTag + ".txt",
      core.reportText(meta, lastResult, lastAttempt, Q));
    else if (act === "txt-paper") download("mock-" + exam.id + "-" + fileTag + "-paper.txt",
      core.paperText(meta, Q));
    else if (act === "txt-key") download("mock-" + exam.id + "-" + fileTag + "-key.txt",
      core.keyText(meta, Q));
    else if (act === "review") renderReview("all");
    else if (act === "retake") retake();
    else if (act === "last-report") openLastReport();
    else if (act === "regen") {
      if (state.startedAt) return; /* never regenerate mid-test */
      generatePaper();
    }
    else if (act === "paper") { renderPaper(); show("paper"); }
    else if (act === "to-intro") show(state.startedAt ? "test" : "intro");
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

  /* --- boot: resume the running test, reopen the last report, or
   *        generate a fresh paper --- */
  var saved = loadJSON(sessionStorage, PROG_KEY, null);
  if (saved && saved.startedAt && saved.ids && saved.ids.length) {
    restorePaper(saved.ids);
    if (Q.length === saved.ids.length) {
      state = saved;
      if (nameInput) nameInput.value = state.name || "";
      if (state.answers.length !== Q.length) state.answers = Q.map(function () { return null; });
      if (TOTAL_SEC - Math.floor((Date.now() - state.startedAt) / 1000) > 0) {
        show("test");
        render();
        startTimer();
      } else {
        submit(true);
      }
      return;
    }
  }
  if (location.hash === "#report" && openLastReport()) {
    /* reopened from an attempts table */
  } else {
    generatePaper();
    show("intro");
    showLast();
  }
})(this);
