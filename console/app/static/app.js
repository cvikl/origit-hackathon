// Origit Console: tiny client. Token-gated actions (sync, Bob review, Art.14 draft), diff colouring, copy.
(function () {
  const KEY = "origit_token";
  function token(force) {
    let t = localStorage.getItem(KEY);
    if (!t || force) { t = prompt("Console token (X-Origit-Token). Stored in this browser only."); if (t) localStorage.setItem(KEY, t.trim()); }
    return t;
  }
  function status(msg, kind) {
    const el = document.getElementById("action-status"); if (!el) return;
    el.hidden = false; el.textContent = msg; el.style.borderColor = kind === "err" ? "var(--danger)" : "var(--line)";
  }
  document.querySelectorAll("[data-action]").forEach(btn => btn.addEventListener("click", async () => {
    const t = token(); if (!t) return;
    const url = btn.dataset.url, action = btn.dataset.action;
    btn.disabled = true;
    status(action === "upgrade" ? "Switching plan…" : action === "review" ? "IBM Bob is reading the record, the reads and the diff… (30–120 s, spends Bobcoins)" : action === "draft" ? "IBM Bob is drafting the Article 14 early warning…" : "Syncing…");
    try {
      const body = btn.dataset.body; const r = await fetch(url, { method: "POST", headers: Object.assign({ "X-Origit-Token": t }, body ? { "Content-Type": "application/json" } : {}), body: body || undefined });
      const j = await r.json().catch(() => ({}));
      if (r.status === 401) { localStorage.removeItem(KEY); status("Wrong token. Click again to re-enter.", "err"); btn.disabled = false; return; }
      if (!r.ok) { status((j.error || j.detail || r.statusText) + "", "err"); btn.disabled = false; return; }
      status("Done. Reloading…"); location.reload();
    } catch (e) { status("Request failed: " + e, "err"); btn.disabled = false; }
  }));
  document.querySelectorAll("[data-copy]").forEach(b => b.addEventListener("click", () => {
    const el = document.querySelector(b.dataset.copy); if (!el) return;
    navigator.clipboard.writeText(el.innerText).then(() => { b.textContent = "Copied"; setTimeout(() => b.textContent = "Copy", 1500); });
  }));
  const s = document.getElementById("signin"); if (s) s.addEventListener("click", () => alert("Origit Console is in private beta. Public repositories are readable by everyone. Pushing and Bob actions use the console token."));
  const d = document.getElementById("diff");
  if (d) {
    const esc = x => x.replace(/&/g, "&amp;").replace(/</g, "&lt;");
    d.innerHTML = d.textContent.split("\n").map(l => {
      if (l.startsWith("+++") || l.startsWith("---") || l.startsWith("diff ") || l.startsWith("index ")) return '<span class="hdr">' + esc(l) + "</span>";
      if (l.startsWith("@@")) return '<span class="hunk">' + esc(l) + "</span>";
      if (l.startsWith("+")) return '<span class="add">' + esc(l) + "</span>";
      if (l.startsWith("-")) return '<span class="del">' + esc(l) + "</span>";
      return esc(l);
    }).join("\n");
  }
})();
