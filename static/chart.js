(() => {
  "use strict";

  const WIDTH = 640;
  const HEIGHT = 180;
  const PAD_X = 34;
  const PAD_Y = 22;
  const PLOT_WIDTH = WIDTH - PAD_X * 2;
  const PLOT_HEIGHT = HEIGHT - PAD_Y * 2;

  const number = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const formatScore = (value) => (
    Number.isInteger(value) ? String(value) : value.toFixed(1)
  );

  const chartCoordinates = (points) => {
    const scores = points.map((point) => point.score);
    const minScore = Math.min(...scores);
    const maxScore = Math.max(...scores);
    const padding = Math.max(5, (maxScore - minScore) * 0.15);
    let domainMin = Math.max(0, minScore - padding);
    let domainMax = Math.min(100, maxScore + padding);

    if (domainMin === domainMax) {
      domainMin = Math.max(0, domainMin - 5);
      domainMax = Math.min(100, domainMax + 5);
    }

    const xStep = PLOT_WIDTH / Math.max(1, points.length - 1);
    const plotted = points.map((point, index) => ({
      ...point,
      x: PAD_X + xStep * index,
      y: PAD_Y + (
        (domainMax - point.score) / (domainMax - domainMin) * PLOT_HEIGHT
      ),
    }));

    return { plotted, minScore, maxScore };
  };

  const selectRange = (allPoints, range) => {
    if (range === "all") return allPoints;
    const days = Number(range);
    const latest = new Date(`${allPoints[allPoints.length - 1].date}T00:00:00`);
    if (!Number.isFinite(days) || Number.isNaN(latest.getTime())) return allPoints;
    const cutoff = new Date(latest);
    cutoff.setDate(cutoff.getDate() - days + 1);
    return allPoints.filter((point) => {
      const date = new Date(`${point.date}T00:00:00`);
      return !Number.isNaN(date.getTime()) && date >= cutoff;
    });
  };

  document.querySelectorAll("[data-support-chart]").forEach((root) => {
    const dataElement = root.querySelector("[data-chart-points]");
    const stage = root.querySelector("[data-chart-stage]");
    const svg = root.querySelector(".support-chart");
    if (!dataElement || !stage || !svg) return;

    let parsed;
    try {
      parsed = JSON.parse(dataElement.textContent);
    } catch {
      return;
    }

    const allPoints = parsed
      .map((point) => ({ ...point, score: number(point.score) }))
      .filter((point) => point.date && point.label && point.score !== null);
    if (allPoints.length < 2) return;

    const line = root.querySelector("[data-chart-line]");
    const area = root.querySelector("[data-chart-area]");
    const crosshair = root.querySelector("[data-chart-crosshair]");
    const activePoint = root.querySelector("[data-chart-active-point]");
    const scoreReadout = root.querySelector("[data-chart-score]");
    const dateReadout = root.querySelector("[data-chart-date]");
    const minLabel = root.querySelector("[data-chart-min]");
    const maxLabel = root.querySelector("[data-chart-max]");
    const rangeButtons = Array.from(root.querySelectorAll("[data-chart-range]"));
    let plotted = [];

    const showPoint = (index) => {
      const point = plotted[index];
      if (!point) return;
      crosshair.setAttribute("x1", point.x);
      crosshair.setAttribute("x2", point.x);
      activePoint.setAttribute("cx", point.x);
      activePoint.setAttribute("cy", point.y);
      scoreReadout.textContent = formatScore(point.score);
      dateReadout.textContent = point.label;
    };

    const render = (range) => {
      const selected = selectRange(allPoints, range);
      if (selected.length < 2) return false;
      const coordinates = chartCoordinates(selected);
      plotted = coordinates.plotted;
      const linePoints = plotted.map((point) => `${point.x},${point.y}`).join(" ");
      line.setAttribute("points", linePoints);
      area.setAttribute(
        "points",
        `${plotted[0].x},${HEIGHT - PAD_Y} ${linePoints} ${plotted[plotted.length - 1].x},${HEIGHT - PAD_Y}`,
      );
      minLabel.textContent = formatScore(coordinates.minScore);
      maxLabel.textContent = formatScore(coordinates.maxScore);
      showPoint(plotted.length - 1);
      return true;
    };

    rangeButtons.forEach((button) => {
      const available = selectRange(allPoints, button.dataset.chartRange).length >= 2;
      button.disabled = !available;
      button.addEventListener("click", () => {
        if (!render(button.dataset.chartRange)) return;
        rangeButtons.forEach((candidate) => {
          const active = candidate === button;
          candidate.classList.toggle("active", active);
          candidate.setAttribute("aria-pressed", String(active));
        });
      });
    });

    stage.addEventListener("pointermove", (event) => {
      const bounds = svg.getBoundingClientRect();
      if (!bounds.width || !plotted.length) return;
      const svgX = (event.clientX - bounds.left) / bounds.width * WIDTH;
      const index = plotted.reduce((nearest, point, candidate) => (
        Math.abs(point.x - svgX) < Math.abs(plotted[nearest].x - svgX)
          ? candidate
          : nearest
      ), 0);
      showPoint(index);
    });

    stage.addEventListener("pointerleave", () => showPoint(plotted.length - 1));
    root.classList.add("chart-enhanced");
    render("all");
  });
})();
