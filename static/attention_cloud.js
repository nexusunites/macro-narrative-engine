(() => {
  const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll("[data-attention-cloud]").forEach((root) => {
    const payload = root.querySelector("[data-cloud-payload]");
    const detail = root.querySelector("[data-cloud-detail]");
    if (!payload || !detail) return;

    let entries;
    try { entries = JSON.parse(payload.textContent); } catch (_) { return; }
    if (!Array.isArray(entries) || !entries.length) return;

    const buttons = [...root.querySelectorAll("[data-cloud-entry]")];
    const byName = new Map(entries.map((entry, index) => [entry.name, index]));
    let highlightTimer;

    const fillChips = (container, items, connected = false) => {
      container.replaceChildren();
      const values = Array.isArray(items) && items.length ? items : [root.dataset.emptyLabel || ""];
      values.forEach((label) => {
        const element = connected && byName.has(label) ? document.createElement("button") : document.createElement("span");
        if (element.tagName === "BUTTON") {
          element.type = "button";
          element.dataset.cloudRelated = label;
        }
        element.textContent = label;
        container.appendChild(element);
      });
    };

    const reveal = () => {
      detail.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "nearest" });
      window.clearTimeout(highlightTimer);
      detail.classList.remove("is-highlighted");
      if (reducedMotion()) return;
      void detail.offsetWidth;
      detail.classList.add("is-highlighted");
      highlightTimer = window.setTimeout(() => detail.classList.remove("is-highlighted"), 600);
    };

    const select = (index, shouldReveal = true) => {
      const entry = entries[index];
      if (!entry) return;
      buttons.forEach((button, buttonIndex) => button.setAttribute("aria-pressed", buttonIndex === index ? "true" : "false"));
      detail.querySelector("[data-cloud-name]").textContent = entry.name;
      const trend = detail.querySelector("[data-cloud-trend]");
      trend.textContent = entry.trend;
      trend.className = `cloud-detail-trend cloud-direction-${entry.direction}`;
      detail.querySelector("[data-cloud-why]").textContent = entry.why;
      const tape = detail.querySelector("[data-cloud-tape]");
      tape.hidden = !entry.tape;
      detail.querySelector("[data-cloud-tape-text]").textContent = entry.tape || "";
      fillChips(detail.querySelector("[data-cloud-driving]"), entry.driving);
      fillChips(detail.querySelector("[data-cloud-watch]"), entry.watch_for);
      fillChips(detail.querySelector("[data-cloud-connected]"), entry.connected, true);
      if (shouldReveal) reveal();
    };

    buttons.forEach((button, index) => button.addEventListener("click", () => select(index)));
    detail.addEventListener("click", (event) => {
      const related = event.target.closest("[data-cloud-related]");
      if (!related) return;
      const index = byName.get(related.dataset.cloudRelated);
      if (index !== undefined) select(index);
    });
  });
})();
