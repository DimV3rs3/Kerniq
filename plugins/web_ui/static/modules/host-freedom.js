/* Agent setting: host freedom. Server mode never shows it. */
(function () {
  var WAIT = 5;
  var silent = false;
  var timer = null;

  function field() { return document.getElementById("host-freedom-field"); }
  function box() { return document.getElementById("s-host-freedom"); }
  function modal() { return document.getElementById("host-freedom-modal"); }
  function confirmBtn() { return document.getElementById("hf-confirm"); }
  function countEl() { return document.getElementById("hf-count"); }

  function markDirty() {
    if (typeof markSettingsDirty === "function") markSettingsDirty();
  }

  function closeModal() {
    if (timer) { clearInterval(timer); timer = null; }
    var node = modal();
    if (node) node.classList.remove("on");
    document.body.classList.remove("modal-open");
  }

  function openModal() {
    var node = modal();
    var ok = confirmBtn();
    var count = countEl();
    if (!node || !ok) return;
    var left = WAIT;
    ok.disabled = true;
    if (count) count.textContent = String(left);
    node.classList.add("on");
    document.body.classList.add("modal-open");
    timer = setInterval(function () {
      left -= 1;
      if (count) count.textContent = left > 0 ? String(left) : "";
      if (left <= 0) {
        clearInterval(timer);
        timer = null;
        ok.disabled = false;
      }
    }, 1000);
  }

  function wire() {
    var input = box();
    if (!input || input.dataset.hfWired) return;
    input.dataset.hfWired = "1";
    input.addEventListener("change", function () {
      if (silent) return;
      if (!input.checked) {
        markDirty();
        return;
      }
      input.checked = false;
      openModal();
    });
    var cancel = document.getElementById("hf-cancel");
    var ok = confirmBtn();
    if (cancel) cancel.addEventListener("click", function () { closeModal(); });
    if (ok) ok.addEventListener("click", function () {
      if (ok.disabled) return;
      closeModal();
      silent = true;
      input.checked = true;
      silent = false;
      markDirty();
    });
    var node = modal();
    if (node) node.addEventListener("click", function (event) {
      if (event.target === node) closeModal();
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
      if (row) row.hidden = false;
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
