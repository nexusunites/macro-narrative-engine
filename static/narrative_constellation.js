(() => {
  document.querySelectorAll("[data-constellation]").forEach((root) => {
    const payload = root.querySelector("[data-constellation-nodes]");
    if (!payload) return;
    let nodes;
    try { nodes = JSON.parse(payload.textContent); } catch (_) { return; }
    const byHref = new Map(nodes.map((node) => [node.href, node]));
    const card = root.querySelector("[data-constellation-card]");
    const show = (anchor) => {
      const node = byHref.get(anchor.getAttribute("href"));
      if (!node || !card) return;
      card.querySelector("[data-card-name]").textContent = node.display_name;
      card.querySelector("[data-card-state]").textContent = `${node.lifecycle_state || "Current story"} · ${node.direction}`;
      card.querySelector("[data-card-explanation]").textContent = node.explanation;
      card.querySelector("[data-card-metric]").textContent = node.share == null ? "" : `${node.share}% of visible narrative attention`;
    };
    root.querySelectorAll(".constellation-node").forEach((anchor) => {
      anchor.addEventListener("pointerenter", () => show(anchor));
      anchor.addEventListener("focus", () => show(anchor));
    });
    const toggle = root.querySelector("[data-constellation-toggle]");
    if (toggle) toggle.addEventListener("toggle", () => {
      root.querySelectorAll("[data-constellation-xray]").forEach((item) => { item.toggleAttribute("hidden", !toggle.open); });
    });
  });
})();
