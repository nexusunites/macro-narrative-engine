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
