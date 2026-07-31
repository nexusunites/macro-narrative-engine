(() => {
  "use strict";
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
  const followUps = (questions) => {
    const buttons = (questions || []).map((question) =>
      `<button type="button" data-analyst-question="${escapeHtml(question)}">${escapeHtml(question)}</button>`
    ).join("");
    return buttons ? `<div class="ai-analyst-suggestions">${buttons}</div>` : "";
  };
  const render = (response, target) => {
    if (response.boundary) {
      target.innerHTML = `<p>${escapeHtml(response.message)}</p>${followUps(response.follow_up_questions)}`;
      return;
    }
    const evidence = (response.supporting_evidence || []).map((item) => {
      const title = escapeHtml(item.title);
      const attribution = [item.source, item.provider, item.published_at].filter(Boolean).map(escapeHtml).join(" · ");
      const linked = item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${title}</a>` : title;
      return `<li>${linked}${attribution ? `<small>${attribution}</small>` : ""}</li>`;
    }).join("");
    const limitations = (response.limitations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    target.innerHTML = [
      response.note ? `<p class="ai-analyst-note">${escapeHtml(response.note)}</p>` : "",
      `<h3>${escapeHtml(response.headline)}</h3>`,
      response.summary ? `<p>${escapeHtml(response.summary)}</p>` : "",
      response.what_changed ? `<p><strong>What changed</strong> ${escapeHtml(response.what_changed)}</p>` : "",
      response.why_it_matters ? `<p><strong>Why it matters</strong> ${escapeHtml(response.why_it_matters)}</p>` : "",
      response.market_confirmation ? `<p><strong>Market context</strong> ${escapeHtml(response.market_confirmation)}</p>` : "",
      evidence ? `<div><strong>Supporting evidence</strong><ul>${evidence}</ul></div>` : "",
      limitations ? `<div><strong>Limits</strong><ul>${limitations}</ul></div>` : "",
      followUps(response.follow_up_questions)
    ].join("");
  };
  document.querySelectorAll("[data-ai-analyst]").forEach((panel) => {
    const form = panel.querySelector("[data-analyst-form]");
    const input = form.querySelector("input");
    const status = panel.querySelector("[data-analyst-status]");
    const target = panel.querySelector("[data-analyst-response]");
    panel.addEventListener("click", (event) => {
      const suggestion = event.target.closest("[data-analyst-question]");
      if (!suggestion) return;
      input.value = suggestion.dataset.analystQuestion;
      form.requestSubmit();
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!input.value.trim()) return;
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      status.textContent = panel.dataset.loadingCopy;
      try {
        const result = await fetch("/api/ai-analyst", {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({mode: panel.dataset.mode, scope: panel.dataset.scope, question: input.value.trim()})
        });
        if (!result.ok) throw new Error("Analyst request failed");
        render(await result.json(), target);
        status.textContent = "";
      } catch (_error) {
        status.textContent = panel.dataset.errorCopy;
      } finally {
        button.disabled = false;
      }
    });
  });
})();
