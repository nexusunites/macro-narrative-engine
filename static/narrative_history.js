(() => {
  "use strict";

  const numeric = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  document.querySelectorAll("[data-history-chart]").forEach((root) => {
    const data = root.querySelector("[data-history-points]");
    const stage = root.querySelector("[data-history-stage]");
    const svg = root.querySelector("svg");
    const crosshair = root.querySelector("[data-history-crosshair]");
    const active = root.querySelector("[data-history-active]");
    const valueReadout = root.querySelector("[data-history-value]");
    const dateReadout = root.querySelector("[data-history-date]");
    const stateReadout = root.querySelector("[data-history-state]");
    if (!data || !stage || !svg || !crosshair || !active) return;

    let parsed;
    try {
      parsed = JSON.parse(data.textContent);
    } catch {
      return;
    }
    const key = root.dataset.valueKey;
    const suffix = root.dataset.suffix || "";
    const points = parsed.map((point, index) => ({
      ...point,
      index,
      value: numeric(point[key]),
    })).filter((point) => point.value !== null);
    if (!points.length) return;

    const width = 640;
    const padX = 34;
    const plotWidth = width - 68;
    const xFor = (point) => padX + (plotWidth * point.index / Math.max(1, parsed.length - 1));
    const show = (point) => {
      const x = xFor(point);
      crosshair.setAttribute("x1", x);
      crosshair.setAttribute("x2", x);
      active.setAttribute("cx", x);
      const nearestCircleY = (() => {
        const values = points.map((candidate) => candidate.value);
        const low = key === "rank" ? 1 : Math.min(0, ...values);
        const high = Math.max(...values, low + 1);
        const ratio = (point.value - low) / (high - low);
        return 22 + ((key === "rank" ? ratio : 1 - ratio) * 136);
      })();
      active.setAttribute("cy", nearestCircleY);
      valueReadout.textContent = `${point.value}${suffix}`;
      dateReadout.textContent = point.label;
      stateReadout.textContent = point.pulse_state;
    };

    stage.addEventListener("pointermove", (event) => {
      const bounds = svg.getBoundingClientRect();
      const x = (event.clientX - bounds.left) / bounds.width * width;
      const nearest = points.reduce((best, point) => (
        Math.abs(xFor(point) - x) < Math.abs(xFor(best) - x) ? point : best
      ), points[0]);
      show(nearest);
    });
    stage.addEventListener("pointerleave", () => show(points[points.length - 1]));
    root.classList.add("chart-enhanced");
    show(points[points.length - 1]);
  });
})();
