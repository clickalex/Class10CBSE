/* Save-as-PDF helper for pages that hold click-to-reveal answers (question
 * bank, drill, chapter practice, chapter pages).
 *
 * A browser prints a closed <details> as just its summary, so a page printed
 * as-is would be a list of "Show Answer" pills. This file opens every answer
 * for the duration of a print and closes the ones it opened afterwards:
 *
 *   - a button with data-save-pdf="answers" | "questions" prints this page with
 *     the answers open or hidden; data-scope="<section id>" prints only that
 *     section (one chapter on the question-bank page);
 *   - a plain Ctrl+P / browser Print also gets the answers (beforeprint).
 *
 * The layout itself is CSS: see "print" in theme/css/style.css, which reads
 * body[data-print] and body[data-print-scope]. Nothing leaves the browser.
 *
 * The logic is plain functions on `core`, exported for Node so the repository
 * tests can drive it against a stub document.
 */
(function (root) {
  "use strict";

  var core = {};

  /* Open every collapsed answer; return the ones opened so they can be shut again. */
  core.openAnswers = function (doc) {
    var opened = [];
    var all = doc.querySelectorAll("details.qans");
    for (var i = 0; i < all.length; i++) {
      if (!all[i].open) {
        all[i].open = true;
        opened.push(all[i]);
      }
    }
    return opened;
  };

  /* Switch the page into print mode. mode: "answers" (default) or "questions". */
  core.begin = function (doc, mode, scopeId) {
    var state = { opened: [], scope: null };
    var body = doc.body;
    mode = mode === "questions" ? "questions" : "answers";
    body.setAttribute("data-print", mode);
    if (scopeId) {
      var section = doc.getElementById(scopeId);
      if (section) {
        section.classList.add("is-print-scope");
        body.setAttribute("data-print-scope", scopeId);
        state.scope = section;
      }
    }
    if (mode === "answers") state.opened = core.openAnswers(doc);
    return state;
  };

  /* Undo begin(): the page goes back exactly as the reader had it. */
  core.end = function (doc, state) {
    if (!state) return;
    doc.body.removeAttribute("data-print");
    doc.body.removeAttribute("data-print-scope");
    if (state.scope) state.scope.classList.remove("is-print-scope");
    for (var i = 0; i < state.opened.length; i++) state.opened[i].open = false;
  };

  /* Wire the buttons and the browser's own print events to begin()/end(). */
  core.bind = function (win, doc) {
    var current = null;

    function start(mode, scopeId) {
      if (current) core.end(doc, current);
      current = core.begin(doc, mode, scopeId);
    }

    function finish() {
      core.end(doc, current);
      current = null;
    }

    /* Ctrl+P or the browser menu: no button was pressed, so print the answers. */
    win.addEventListener("beforeprint", function () {
      if (!current) start("answers", null);
    });
    win.addEventListener("afterprint", finish);

    /* Safari reports the end of a print through the print media query. */
    if (win.matchMedia) {
      var query = win.matchMedia("print");
      var onChange = function (event) { if (!event.matches) finish(); };
      if (query.addEventListener) query.addEventListener("change", onChange);
      else if (query.addListener) query.addListener(onChange);
    }

    doc.addEventListener("click", function (event) {
      var el = event.target && event.target.closest
        ? event.target.closest("[data-save-pdf]") : null;
      if (!el) return;
      if (event.preventDefault) event.preventDefault();
      start(el.getAttribute("data-save-pdf"), el.getAttribute("data-scope"));
      win.print();
    });

    return { start: start, finish: finish };
  };

  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof window !== "undefined" && typeof document !== "undefined") {
    core.bind(window, document);
  }
  root.C10Print = core;
})(this);
