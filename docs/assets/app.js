/* Progress tracking for the Class 10 CBSE study hub.
 * State lives in localStorage under "c10cbse-progress" as a map of
 * "subject::chapter-id" -> true. Nothing leaves the browser.
 */
(function () {
  "use strict";

  var KEY = "c10cbse-progress";

  function load() {
    try {
      return JSON.parse(localStorage.getItem(KEY)) || {};
    } catch (e) {
      return {};
    }
  }

  function save(state) {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch (e) {
      /* storage unavailable (private mode) - progress just will not persist */
    }
  }

  var state = load();

  /* --- chapter "mark complete" checkboxes --- */
  Array.prototype.forEach.call(
    document.querySelectorAll("input.mark-complete"),
    function (box) {
      var key = box.getAttribute("data-key");
      if (state[key]) box.checked = true;
      box.addEventListener("change", function () {
        if (box.checked) state[key] = true;
        else delete state[key];
        save(state);
      });
    }
  );

  /* --- hub progress bar + per-unit counters --- */
  function countFor(subject) {
    var n = 0;
    Object.keys(state).forEach(function (k) {
      if (k.indexOf(subject + "::") === 0) n += 1;
    });
    return n;
  }

  Array.prototype.forEach.call(
    document.querySelectorAll(".bar .fill"),
    function (fill) {
      var subject = fill.getAttribute("data-subject");
      var total = parseInt(fill.getAttribute("data-total"), 10) || 0;
      var done = Math.min(countFor(subject), total);
      fill.style.width = total ? (done / total) * 100 + "%" : "0%";
    }
  );

  Array.prototype.forEach.call(
    document.querySelectorAll("[data-subject-text]"),
    function (el) {
      var subject = el.getAttribute("data-subject-text");
      var total = parseInt(el.getAttribute("data-total"), 10) || 0;
      var done = Math.min(countFor(subject), total);
      el.textContent = done + " of " + total + " chapters marked complete";
    }
  );

  Array.prototype.forEach.call(document.querySelectorAll(".prog"), function (el) {
    var key = el.getAttribute("data-unit");
    var total = parseInt(el.getAttribute("data-total"), 10) || 0;
    var done = 0;
    Object.keys(state).forEach(function (k) {
      /* unit ids are matched by the chapter's own key prefix set at render time */
      if (k.indexOf(key + "##") === 0) done += 1;
    });
    el.textContent = done + "/" + total + " chapters";
  });
})();
