/* Batch Builder UI. Plain DOM, no framework, no network access beyond this app. */
(function () {
  "use strict";

  var ROWS = ["A", "B", "C", "D", "E", "F", "G", "H"];
  var ROLE_LABEL = {
    cal: "Calibrators", qc: "Controls", qualcal: "Cutoff cal",
    qualqc: "Qual QCs", neg: "Negative", mbn1: "MBN 1", mbn2: "MBN 2",
    repeat: "Repeats", sample: "Samples", error: "Removed", empty: "Empty"
  };
  var SEVERITY_TITLE = {
    ERROR: "Errors - these must be corrected",
    WARNING: "Warnings - review before loading",
    NOTES: "Notes",
    SUCCESS: "Checks passed"
  };

  var state = { token: null, filename: null, lastRun: null };

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function busy(on, text) {
    $("busy").hidden = !on;
    $("busy-text").textContent = text || "";
  }

  /* ---------------- fetch with a deadline ---------------- */

  // Every request gets a deadline. Without one, a stalled call leaves the busy
  // overlay spinning with no way out and no explanation.
  function request(url, options, timeoutMs) {
    options = options || {};
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, timeoutMs || 60000);
    options.signal = controller.signal;
    return fetch(url, options)
      .then(function (r) {
        clearTimeout(timer);
        return r.json().catch(function () {
          throw new Error("The server sent a response that could not be read ("
            + r.status + " " + r.statusText + ").");
        });
      })
      .catch(function (e) {
        clearTimeout(timer);
        if (e.name === "AbortError") {
          throw new Error("The server did not respond in time. It may be busy "
            + "contacting Apollo, or it may have stopped. Check the console "
            + "window this application opened.");
        }
        throw e;
      });
  }

  /* ---------------- Apollo health ---------------- */

  function checkApollo(attempt) {
    attempt = attempt || 0;
    var pill = $("apollo-pill");
    request("/api/health", {}, 10000).then(function (d) {
      if (d.state === "checking") {
        pill.className = "pill pill-idle";
        pill.textContent = "Checking Apollo...";
        // The probe runs server-side; poll until it settles, then stop.
        if (attempt < 30) setTimeout(function () { checkApollo(attempt + 1); }, 1000);
        return;
      }
      if (d.ok) {
        pill.className = "pill pill-ok";
        pill.textContent = "Apollo connected";
        pill.title = d.apollo || "";
      } else {
        pill.className = "pill pill-bad";
        pill.textContent = "Apollo unavailable";
        pill.title = d.error || "";
        showApolloHelp(d.error);
      }
    }).catch(function (e) {
      pill.className = "pill pill-bad";
      pill.textContent = "Apollo unavailable";
      pill.title = String(e.message || e);
    });
  }

  function showApolloHelp(detail) {
    // Apollo being down does not stop a plate being loaded and inspected, so
    // say so rather than leaving the analyst guessing.
    if ($("apollo-help")) return;
    var bar = el("div", "banner banner-warn");
    bar.id = "apollo-help";
    bar.appendChild(el("strong", null, "Apollo is not reachable. "));
    bar.appendChild(document.createTextNode(
      "You can still load a plate file, see the plate map and check it for "
      + "layout problems. Generating a batch that needs an MBN will fail until "
      + "the connection is back."
      + (detail ? "  Details: " + detail : "")));
    var retry = el("button", "link", "Re-check connection");
    retry.style.marginLeft = "8px";
    retry.addEventListener("click", function () {
      retry.disabled = true;
      retry.textContent = "Re-checking...";
      request("/api/health/recheck", { method: "POST" }, 10000)
        .then(function () {
          setTimeout(function () {
            var b = $("apollo-help");
            if (b) b.remove();
            checkApollo();
          }, 1200);
        })
        .catch(function () {
          retry.disabled = false;
          retry.textContent = "Re-check connection";
        });
    });
    bar.appendChild(retry);
    document.body.insertBefore(bar, document.querySelector("main"));
  }

  /* ---------------- plate map ---------------- */

  function drawPlate(preview) {
    var host = $("plate");
    clear(host);
    if (!preview || !preview.wells || !preview.wells.length) {
      host.className = "plate plate-empty";
      host.appendChild(el("p", "placeholder",
        "Choose a Hamilton report to see the plate layout."));
      $("legend").hidden = true;
      $("counts").hidden = true;
      return;
    }

    host.className = "plate";
    var byPosition = {};
    preview.wells.forEach(function (w) { byPosition[w.position] = w; });

    var grid = el("div", "plate-grid");
    grid.appendChild(el("div", "plate-head", ""));
    for (var c = 1; c <= 12; c++) grid.appendChild(el("div", "plate-head", String(c)));

    ROWS.forEach(function (letter, rowIndex) {
      grid.appendChild(el("div", "plate-row-label", letter));
      for (var col = 1; col <= 12; col++) {
        var position = rowIndex * 12 + col;
        var well = byPosition[position] || { role: "empty", label: "", title: "Empty" };
        var cell = el("div", "well w-" + well.role);
        cell.title = letter + col + "  (position " + position + ")\n" +
          (well.title || "") + (well.label ? "\n" + well.label : "");
        cell.appendChild(el("b", null, letter + col));
        if (well.label) cell.appendChild(el("span", null, shorten(well.label)));
        grid.appendChild(cell);
      }
    });
    host.appendChild(grid);
    $("legend").hidden = false;

    var counts = $("counts");
    clear(counts);
    Object.keys(ROLE_LABEL).forEach(function (role) {
      var n = preview.counts[role];
      if (!n) return;
      var span = el("span");
      span.appendChild(el("b", null, String(n)));
      span.appendChild(document.createTextNode(" " + ROLE_LABEL[role]));
      counts.appendChild(span);
    });
    counts.hidden = false;
  }

  function showDetected(d) {
    var host = $("detected");
    if (!d) { host.hidden = true; return; }
    $("chip-format").textContent = d.format || "";
    $("chip-orient").textContent = "Fill order: " + (d.orientation_label || "?");
    $("chip-orient").title =
      "Detected from the order the machine filled the plate. This is what "
      + "determines the vial sequence.";
    var cond = $("chip-cond");
    if (d.condition) {
      cond.hidden = false;
      cond.textContent = "Condition: " + d.condition;
      cond.title = d.condition_label || "";
    } else {
      cond.hidden = true;
    }
    host.hidden = false;

    // Condition override and mockup mode only apply to Tox6 plates.
    var isTox6 = d.assay === "TO6";
    $("condition-field").hidden = !isTox6;
    $("mockup-field").hidden = !isTox6;
    if (!isTox6) {
      document.querySelector('[name="mockup"]').checked = false;
      document.querySelector('[name="condition"]').value = "";
    }
    syncMbnRequirement();
  }

  function syncMbnRequirement() {
    // A plate-only mockup has no batch in Apollo, so MBN 1 stops being required.
    var mockup = document.querySelector('[name="mockup"]');
    var mbn1 = document.querySelector('[name="mbn1"]');
    var on = mockup && mockup.checked;
    mbn1.required = !on;
    mbn1.disabled = on;
    document.querySelector('[name="mbn2"]').disabled = on;
    mbn1.placeholder = on ? "not used for a mockup" : "e.g. 500101";
  }

  function shorten(text) {
    if (text.length <= 11) return text;
    return text.slice(0, 4) + "…" + text.slice(-4);
  }

  /* ---------------- results ---------------- */

  function renderResults(data, wrote) {
    var host = $("results");
    clear(host);

    if (data.error && !data.findings.length) {
      host.appendChild(msg("ERROR", data.error));
      return;
    }

    if (wrote && data.ok) {
      host.appendChild(msg("SUCCESS",
        data.files.length + " file(s) written. A run report is saved alongside them."));
    } else if (!data.ok) {
      host.appendChild(msg("ERROR",
        data.error || "Validation failed; nothing was written."));
    } else {
      host.appendChild(msg("SUCCESS",
        "Batch is valid. " + data.files.length +
        " file(s) ready to generate; nothing has been written yet."));
    }

    ["ERROR", "WARNING", "NOTES", "SUCCESS"].forEach(function (severity) {
      var items = data.findings.filter(function (f) { return f.severity === severity; });
      if (!items.length) return;
      host.appendChild(el("div", "group-title", SEVERITY_TITLE[severity]));
      var limit = severity === "NOTES" ? 8 : items.length;
      items.slice(0, limit).forEach(function (f) {
        host.appendChild(msg(severity, f.message));
      });
      if (items.length > limit) {
        var more = el("p", "collapsed-note",
          "+ " + (items.length - limit) + " more (all listed in the run report).");
        host.appendChild(more);
      }
    });

    if (data.files && data.files.length) {
      var list = el("ul", "filelist");
      data.files.forEach(function (f) {
        var li = el("li");
        li.appendChild(el("span", null, f.name));
        var right = el("span");
        right.appendChild(el("span", null, f.rows + " injections"));
        if (wrote && data.run) {
          right.appendChild(document.createTextNode("  "));
          var a = el("a", null, "download");
          a.href = "/api/download/" + encodeURIComponent(data.run) +
            "/" + encodeURIComponent(f.name);
          right.appendChild(a);
        }
        li.appendChild(right);
        list.appendChild(li);
      });
      host.appendChild(list);
    }

    if (wrote && data.output_dir) {
      host.appendChild(el("p", "path", "Saved to: " + data.output_dir));
      $("download-zip").href = "/api/download/" + encodeURIComponent(data.run);
      $("result-actions").hidden = false;
      state.lastRun = data.run;
      loadRuns();
    } else {
      $("result-actions").hidden = true;
    }
  }

  function msg(severity, text) {
    return el("div", "msg msg-" + severity, text);
  }

  /* ---------------- file upload ---------------- */

  function uploadFile(file) {
    if (!file) return;
    if (!/\.xls$/i.test(file.name)) {
      renderResults({ ok: false, error: "Choose an Excel 97-2003 (.xls) report.", findings: [] }, false);
      return;
    }
    var body = new FormData();
    body.append("file", file);
    busy(true, "Reading the Hamilton report…");

    request("/api/upload", { method: "POST", body: body }, 120000)
      .then(function (d) {
        busy(false);
        if (!d.ok) {
          state.token = null;
          setFileLoaded(null);
          renderResults({ ok: false, error: d.error, findings: [] }, false);
          drawPlate(null);
          return;
        }
        state.token = d.token;
        state.filename = d.filename;
        setFileLoaded(d);
        showDetected(d.detected);
        drawPlate(d.preview);
        if (d.findings.length) {
          renderResults({ ok: true, findings: d.findings, files: [] }, false);
        }
        syncButtons();
      })
      .catch(function (e) {
        busy(false);
        renderResults({ ok: false, error: String(e), findings: [] }, false);
      });
  }

  function setFileLoaded(d) {
    var zone = $("dropzone");
    var idle = zone.querySelector(".dz-idle");
    var loaded = zone.querySelector(".dz-loaded");
    if (!d) {
      zone.classList.remove("loaded");
      idle.hidden = false;
      loaded.hidden = true;
      state.token = null;
      syncButtons();
      return;
    }
    zone.classList.add("loaded");
    idle.hidden = true;
    loaded.hidden = false;
    $("file-name").textContent = d.filename;
    var s = d.summary;
    var counts = (d.preview && d.preview.counts) || {};
    // Built from the same counts the plate map uses, so the two always agree.
    var parts = [s.wells + " wells"];
    Object.keys(ROLE_LABEL).forEach(function (role) {
      if (role === "empty") return;
      if (counts[role]) {
        parts.push(counts[role] + " " + ROLE_LABEL[role].toLowerCase());
      }
    });
    if (s.dropped) parts.push(s.dropped + " removed");
    $("file-summary").textContent = parts.join(" · ");
  }

  /* ---------------- submit ---------------- */

  function formData() {
    var body = new FormData($("batch-form"));
    body.append("token", state.token || "");
    // So the run report names the file the analyst chose, not the temp upload.
    body.append("filename", state.filename || "");
    return body;
  }

  function submit(url, label, wrote) {
    if (!state.token) return;
    busy(true, label);
    request(url, { method: "POST", body: formData() }, 90000)
      .then(function (d) {
        busy(false);
        renderResults(d, wrote && d.ok);
        if (d.preview) drawPlate(d.preview);
        window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
      })
      .catch(function (e) {
        busy(false);
        renderResults({ ok: false, error: String(e), findings: [] }, false);
      });
  }

  function syncButtons() {
    var ready = !!state.token;
    $("btn-check").disabled = !ready;
    $("btn-generate").disabled = !ready;
  }

  /* ---------------- run history ---------------- */

  function loadRuns() {
    request("/api/runs", {}, 20000).then(function (d) {
      var host = $("runs");
      clear(host);
      if (!d.runs || !d.runs.length) {
        host.appendChild(el("p", "placeholder", "No previous runs in " + d.root + "."));
        return;
      }
      var table = el("table", "runs");
      var head = el("tr");
      ["Run", "Files", ""].forEach(function (h) { head.appendChild(el("th", null, h)); });
      table.appendChild(head);
      d.runs.forEach(function (run) {
        var tr = el("tr");
        tr.appendChild(el("td", null, run.run));
        tr.appendChild(el("td", null, String(run.files.length)));
        var td = el("td");
        var a = el("a", null, "download");
        a.href = "/api/download/" + encodeURIComponent(run.run);
        td.appendChild(a);
        tr.appendChild(td);
        table.appendChild(tr);
      });
      host.appendChild(table);
    }).catch(function () { /* history is optional */ });
  }

  /* ---------------- wiring ---------------- */

  document.addEventListener("DOMContentLoaded", function () {
    var zone = $("dropzone");
    var input = $("file-input");

    zone.addEventListener("click", function (e) {
      if (e.target.id !== "clear-file") input.click();
    });
    zone.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
    });
    ["dragenter", "dragover"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) {
        e.preventDefault(); zone.classList.add("over");
      });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) {
        e.preventDefault(); zone.classList.remove("over");
      });
    });
    zone.addEventListener("drop", function (e) {
      if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
    });
    input.addEventListener("change", function () {
      if (input.files.length) uploadFile(input.files[0]);
    });
    $("clear-file").addEventListener("click", function (e) {
      e.stopPropagation();
      input.value = "";
      setFileLoaded(null);
      showDetected(null);
      drawPlate(null);
    });

    $("btn-check").addEventListener("click", function () {
      submit("/api/check", "Validating against Apollo…", false);
    });
    $("batch-form").addEventListener("submit", function (e) {
      e.preventDefault();
      submit("/api/generate", "Generating batch files…", true);
    });
    $("refresh-runs").addEventListener("click", loadRuns);
    document.querySelector('[name="mockup"]')
      .addEventListener("change", syncMbnRequirement);

    checkApollo();
    loadRuns();
    syncButtons();
  });
})();
