(function () {
  "use strict";

  document.querySelectorAll("[data-save-history]").forEach(function (button) {
    button.addEventListener("click", function () {
      var body = new URLSearchParams();
      body.append("action", "save");
      body.append("view_type", button.dataset.viewType || "");
      body.append("replay_id", button.dataset.replayId || "");
      body.append("label", button.dataset.label || "");
      button.disabled = true;
      fetch("/preferences/history", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: body.toString(),
        redirect: "follow"
      }).then(function (response) {
        if (!response.ok) {
          throw new Error("Unable to save");
        }
        button.textContent = "Saved";
      }).catch(function () {
        button.textContent = "Could not save";
        button.disabled = false;
      });
    });
  });
}());

(function () {
  "use strict";

  var cloudRoot = document.querySelector("[data-attention-cloud]");
  var panel = document.querySelector("[data-watchlist-panel]");
  var toggle = document.querySelector("[data-watchlist-toggle]");
  if (!cloudRoot || !panel || !toggle) return;

  var payload = cloudRoot.querySelector("[data-cloud-payload]");
  var entries;
  try { entries = JSON.parse(payload.textContent); } catch (_) { return; }
  if (!Array.isArray(entries) || !entries.length) return;

  var watched = new Set(entries.filter(function (entry) { return entry.watched; }).map(function (entry) { return entry.name; }));
  var list = panel.querySelector("[data-watchlist-list]");
  var empty = panel.querySelector("[data-watchlist-empty]");
  var count = toggle.querySelector("[data-watchlist-count]");
  var hint = panel.querySelector("[data-watchlist-hint]");
  var star = cloudRoot.querySelector("[data-cloud-star]");
  var selected = entries[0];
  var glyphs = { up: "▲", down: "▼", steady: "→" };

  function updatePersonalization(entry, isWatched) {
    var section = document.getElementById("my-narratives");
    if (!section) return;
    var cards = Array.prototype.slice.call(section.querySelectorAll("[data-personalization-name]"));
    var card = cards.find(function (item) { return item.dataset.personalizationName === entry.name; });
    if (!isWatched) {
      if (card) card.remove();
    } else if (!card) {
      var grid = section.querySelector("[data-personalization-grid]");
      if (!grid) {
        grid = document.createElement("div");
        grid.className = "personalization-grid";
        grid.dataset.personalizationGrid = "";
        section.querySelector("[data-personalization-empty]")?.replaceWith(grid);
      }
      card = document.createElement("article");
      card.className = "personalization-card";
      card.dataset.personalizationName = entry.name;
      var title = document.createElement("h3");
      title.textContent = entry.name;
      var trend = document.createElement("strong");
      trend.textContent = entry.trend;
      var summary = document.createElement("p");
      summary.textContent = cloudRoot.dataset.watchlistHistory;
      var link = document.createElement("a");
      link.className = "investigate-link";
      link.href = "/research/group:" + encodeURIComponent(entry.name);
      link.textContent = cloudRoot.dataset.watchlistInvestigate;
      card.append(title, trend, summary, link);
      grid.appendChild(card);
    }
    var gridNow = section.querySelector("[data-personalization-grid]");
    if (gridNow && !gridNow.children.length) {
      var message = document.createElement("div");
      message.className = "section-empty";
      message.dataset.personalizationEmpty = "";
      message.textContent = panel.querySelector("[data-watchlist-empty]").textContent;
      gridNow.replaceWith(message);
    }
  }

  function updateStar() {
    var on = selected && watched.has(selected.name);
    star.textContent = on ? "★" : "☆";
    star.classList.toggle("is-watched", on);
    star.setAttribute("aria-pressed", on ? "true" : "false");
    star.setAttribute("aria-label", on ? cloudRoot.dataset.watchlistRemove : cloudRoot.dataset.watchlistAdd);
  }

  function render() {
    list.replaceChildren();
    entries.forEach(function (entry, index) {
      if (!watched.has(entry.name)) return;
      var row = document.createElement("div");
      row.className = "watchlist-row";
      var select = document.createElement("button");
      select.type = "button";
      select.className = "watchlist-select";
      var glyph = document.createElement("span");
      glyph.className = "watchlist-glyph cloud-direction-" + entry.direction;
      glyph.textContent = glyphs[entry.direction];
      glyph.setAttribute("aria-hidden", "true");
      var name = document.createElement("span");
      name.className = "watchlist-name";
      name.textContent = entry.name;
      var word = document.createElement("span");
      word.className = "watchlist-word";
      word.textContent = entry.trend.split(" ")[0];
      select.append(glyph, name, word);
      select.addEventListener("click", function () { cloudRoot.selectCloudEntry(index, true); });
      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "watchlist-remove";
      remove.textContent = "×";
      remove.setAttribute("aria-label", cloudRoot.dataset.watchlistRemove + ": " + entry.name);
      remove.addEventListener("click", function () { setWatched(entry, false); });
      row.append(select, remove);
      list.appendChild(row);
    });
    var size = watched.size;
    count.textContent = String(size);
    hint.textContent = size + " " + (size === 1 ? cloudRoot.dataset.watchlistSingular : cloudRoot.dataset.watchlistPlural);
    empty.hidden = size > 0;
    updateStar();
  }

  function setWatched(entry, on, persist) {
    var wasWatched = watched.has(entry.name);
    if (on) watched.add(entry.name); else watched.delete(entry.name);
    entry.watched = on;
    updatePersonalization(entry, on);
    render();
    if (persist === false || !cloudRoot.dataset.watchlistPersist) return;
    var body = new URLSearchParams();
    body.append("csrf_token", cloudRoot.dataset.watchlistCsrf || "");
    body.append("narrative_level", "group");
    body.append("narrative_key", entry.name);
    body.append("action", on ? "follow" : "unfollow");
    fetch(cloudRoot.dataset.watchlistPersist, {
      method: "POST",
      headers: {"Content-Type": "application/x-www-form-urlencoded"},
      body: body.toString(),
      redirect: "follow"
    }).then(function (response) {
      if (!response.ok) throw new Error("Unable to update watchlist");
    }).catch(function () {
      setWatched(entry, wasWatched, false);
    });
  }

  function open() {
    panel.hidden = false;
    document.body.classList.add("watchlist-open");
    toggle.hidden = true;
    toggle.setAttribute("aria-expanded", "true");
  }

  function close() {
    panel.hidden = true;
    document.body.classList.remove("watchlist-open");
    toggle.hidden = false;
    toggle.setAttribute("aria-expanded", "false");
  }

  star.addEventListener("click", function () { setWatched(selected, !watched.has(selected.name)); });
  cloudRoot.addEventListener("cloud-selection-changed", function (event) {
    selected = event.detail.entry;
    updateStar();
  });
  toggle.addEventListener("click", open);
  panel.querySelector("[data-watchlist-close]").addEventListener("click", close);
  render();
}());
