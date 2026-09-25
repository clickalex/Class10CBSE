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

  /* --- sidebar drawer (the table of contents on a phone) --- */
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.getElementById("backdrop");

  window.openMenu = function () {
    if (sidebar) sidebar.classList.add("open");
    if (backdrop) backdrop.classList.add("show");
  };

  window.closeMenu = function () {
    if (sidebar) sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("show");
  };

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") window.closeMenu();
  });

  if (sidebar) {
    var current = sidebar.querySelector(".toc-item.is-on");
    /* keep the highlighted entry in view when the list is long (Hindi: 40) */
    if (current && current.scrollIntoView) {
      current.scrollIntoView({ block: "nearest" });
    }
  }

  /* --- back to top ---
   * Shown after a scroll. Must scroll the document, not the button: an inline
   * scrollTo() resolves to Element.scrollTo on the button itself, which does
   * not move the page. The sidebar is its own scroller, so reset that too. */
  var totop = document.getElementById("totop");
  if (totop) {
    var reduceMotion = window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function scrollY() {
      return window.pageYOffset ||
        document.documentElement.scrollTop ||
        document.body.scrollTop ||
        0;
    }

    function syncTotop() {
      totop.hidden = scrollY() < 240;
    }

    function scrollEl(el) {
      if (!el) return;
      var behavior = reduceMotion ? "auto" : "smooth";
      try {
        el.scrollTo({ top: 0, left: 0, behavior: behavior });
      } catch (e) {
        try { el.scrollTo(0, 0); } catch (e2) { el.scrollTop = 0; }
      }
    }

    totop.addEventListener("click", function () {
      var behavior = reduceMotion ? "auto" : "smooth";
      try {
        window.scrollTo({ top: 0, left: 0, behavior: behavior });
      } catch (e) {
        window.scrollTo(0, 0);
        var root = document.scrollingElement || document.documentElement;
        root.scrollTop = 0;
        document.body.scrollTop = 0;
      }
      scrollEl(sidebar);
      if (window.closeMenu) window.closeMenu();
    });

    window.addEventListener("scroll", syncTotop, { passive: true });
    window.addEventListener("pageshow", syncTotop);
    syncTotop();
  }

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

  /* --- IT-style Q&A bar: filter by type, show/hide answers, revealed count --- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-qbar]"), function (bar) {
    var scope = bar.parentElement || document;
    var cards = function () {
      return Array.prototype.slice.call(scope.querySelectorAll(".qcard"));
    };
    var revealedEl = bar.querySelector("[data-revealed]");
    var shownEl = bar.querySelector("[data-shown]");

    function visibleCards() {
      return cards().filter(function (c) {
        return c.className.indexOf("is-hidden") === -1;
      });
    }

    function recount() {
      var vis = visibleCards();
      var open = vis.filter(function (c) {
        var d = c.querySelector("details.qans");
        return d && d.open;
      }).length;
      if (revealedEl) revealedEl.textContent = String(open);
      if (shownEl) shownEl.textContent = String(vis.length);
    }

    Array.prototype.forEach.call(bar.querySelectorAll(".qfilter"), function (btn) {
      btn.addEventListener("click", function () {
        var key = btn.getAttribute("data-filter");
        Array.prototype.forEach.call(bar.querySelectorAll(".qfilter"), function (b) {
          b.className = b.className.replace(/\bis-on\b/g, "").replace(/\s+/g, " ").trim();
        });
        btn.className += " is-on";
        cards().forEach(function (c) {
          var t = c.getAttribute("data-type");
          if (key === "all" || t === key) c.classList.remove("is-hidden");
          else c.classList.add("is-hidden");
        });
        recount();
      });
    });

    var showAll = bar.querySelector("[data-show-all]");
    var hideAll = bar.querySelector("[data-hide-all]");
    if (showAll) {
      showAll.addEventListener("click", function () {
        visibleCards().forEach(function (c) {
          var d = c.querySelector("details.qans");
          if (d) d.open = true;
        });
        recount();
      });
    }
    if (hideAll) {
      hideAll.addEventListener("click", function () {
        cards().forEach(function (c) {
          var d = c.querySelector("details.qans");
          if (d) d.open = false;
        });
        recount();
      });
    }

    scope.addEventListener("toggle", recount, true);
    recount();
  });

  /* --- admission watch report: how long ago the last check ran --- */
  /* The page is rebuilt after every daily check, so an old timestamp means the
   * check was delayed or has stopped; say so instead of looking current. */
  var STALE_HOURS = 36; /* one daily run plus generous room for GitHub delays */
  Array.prototype.forEach.call(document.querySelectorAll("[data-checked-at]"), function (el) {
    var checked = Date.parse(el.getAttribute("data-checked-at"));
    if (isNaN(checked)) return;
    var hours = Math.max(0, (Date.now() - checked) / 3600000);
    var whole = Math.floor(hours);
    var days = Math.floor(hours / 24);
    var age = hours < 1 ? "less than an hour ago"
      : hours < 48 ? whole + (whole === 1 ? " hour ago" : " hours ago")
      : days + " days ago";
    var label = el.querySelector("[data-age]");
    if (label) label.textContent = " (" + age + ")";
    var stale = document.querySelector("[data-report-stale]");
    if (stale && hours > STALE_HOURS) stale.hidden = false;
  });
})();
