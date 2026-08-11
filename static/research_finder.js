(function () {
  "use strict";

  var input = document.getElementById("finderInput");
  var clear = document.getElementById("finderClear");
  var chipRow = document.getElementById("chipRow");
  var crypto = document.getElementById("chipCrypto");
  var chipHint = document.getElementById("chipHint");
  var empty = document.getElementById("indexEmpty");
  var studioHint = document.getElementById("studioHint");
  if (!input || !clear || !chipRow || !empty) { return; }

  var activeThemes = [];
  var cards = Array.prototype.slice.call(document.querySelectorAll("[data-narrative-card]"));

  function includesQuery(element, query) {
    return !query || (element.dataset.search || "").toLowerCase().indexOf(query) >= 0;
  }

  function matchesTheme(story) {
    return !activeThemes.length || activeThemes.indexOf(story.dataset.theme) >= 0;
  }

  function renderIndex() {
    var query = input.value.trim().toLowerCase();
    var shown = 0;
    clear.classList.toggle("hidden", !query);

    cards.forEach(function (card) {
      var narrativeMatches = includesQuery(card, query);
      var stories = Array.prototype.slice.call(card.querySelectorAll("[data-story]"));
      var visibleStories = 0;

      stories.forEach(function (story) {
        var visible = (narrativeMatches || includesQuery(story, query)) && matchesTheme(story);
        story.classList.toggle("hidden", !visible);
        if (visible) { visibleStories += 1; }
      });

      var visible = stories.length
        ? visibleStories > 0
        : narrativeMatches && !activeThemes.length;
      card.classList.toggle("hidden", !visible);
      if (visible) { shown += 1; }
    });

    empty.classList.toggle("hidden", shown > 0);
  }

  input.addEventListener("input", function () {
    chipHint.textContent = "";
    renderIndex();
  });
  clear.addEventListener("click", function () {
    input.value = "";
    renderIndex();
    input.focus();
  });

  Array.prototype.forEach.call(chipRow.querySelectorAll(".chip[data-theme]"), function (chip) {
    chip.addEventListener("click", function () {
      var theme = chip.dataset.theme;
      var index = activeThemes.indexOf(theme);
      if (index >= 0) { activeThemes.splice(index, 1); }
      else { activeThemes.push(theme); }
      var active = activeThemes.indexOf(theme) >= 0;
      chip.classList.toggle("on", active);
      chip.setAttribute("aria-pressed", active ? "true" : "false");
      chipHint.textContent = "";
      renderIndex();
    });
  });

  if (crypto) {
    crypto.addEventListener("click", function () {
      chipHint.textContent = document.getElementById("cryptoHintCopy").textContent;
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll(".sc-star"), function (star) {
    star.addEventListener("click", function () {
      studioHint.textContent = document.getElementById("studioHintCopy").textContent;
    });
  });
}());
