/* Agent setting: host freedom. Uses the same countdown dialog as the other guards. */
(function () {
  var silent = false;

  function field() { return document.getElementById("host-freedom-field"); }
  function box() { return document.getElementById("s-host-freedom"); }

  function markDirty() {
    if (typeof markSettingsDirty === "function") markSettingsDirty();
  }

  function wire() {
    var input = box();
    if (!input || input.dataset.hfWired) return;
    input.dataset.hfWired = "1";
    input.addEventListener("change", async function () {
      if (silent) return;
      if (!input.checked) {
        markDirty();
        return;
      }
      input.checked = false;
      var ask = window.askCountdown;
      if (typeof ask !== "function") return;
      var title = (typeof t === "function") ? t("hostFreedomTitle") : "Host freedom";
      var body = (typeof t === "function") ? t("hostFreedomBody") : "";
      var yes = (typeof t === "function") ? t("wantFreedom") : "I want freedom";
      var no = (typeof t === "function") ? t("wantSafe") : "I want safe";
      var ok = await ask(title, body, 5, { ok: yes, cancel: no, danger: true });
      if (!ok) return;
      silent = true;
      input.checked = true;
      silent = false;
      markDirty();
    });
  }

  window.KerniqHostFreedom = {
    sync: function (opts) {
      opts = opts || {};
      var row = field();
      var input = box();
      wire();
      if (opts.server) {
        if (row) row.hidden = true;
        if (input) input.checked = false;
        return;
      }
      if (!input) return;
      silent = true;
      input.checked = !!opts.enabled;
      silent = false;
    },
    checked: function () {
      var row = field();
      var input = box();
      if (!input || (row && row.hidden)) return false;
      return !!input.checked;
    }
  };
})();
