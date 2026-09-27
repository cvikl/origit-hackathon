// Landing page: two single-series line charts (inline SVG, crosshair tooltip) and the market calculator.
(function () {
  const DATA = {
    adoption: { x: ["2023", "2024", "2025"], y: [70, 76, 84], unit: "%", yMin: 60, yMax: 90, yTicks: [60, 70, 80, 90], color: "var(--viz-1)", label: "using or planning to use AI tools" },
    attacks: { x: ["2024", "2025", "2026 H1"], y: [6, 14, 37], unit: "", yMin: 0, yMax: 40, yTicks: [0, 10, 20, 30, 40], color: "var(--viz-2)", label: "campaigns tracked" },
  };
  const NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
  function draw(host, d) {
    const W = host.clientWidth || 520, H = 220, pad = { l: 40, r: 44, t: 16, b: 28 };
    const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    const xs = d.x.map((_, i) => pad.l + (d.x.length === 1 ? iw / 2 : i * iw / (d.x.length - 1)));
    const y0 = d.yMin || 0, sc = v => pad.t + ih - ((v - y0) / (d.yMax - y0)) * ih; const ys = d.y.map(sc);
    host.textContent = "";
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", height: H, role: "img", "aria-label": d.label }, host);
    d.yTicks.forEach(t => { const y = sc(t); el("line", { x1: pad.l, x2: W - pad.r, y1: y, y2: y, class: "grid" }, svg); const tx = el("text", { x: pad.l - 8, y: y + 4, class: "tick", "text-anchor": "end" }, svg); tx.textContent = t + d.unit; });
    d.x.forEach((lab, i) => { const tx = el("text", { x: xs[i], y: H - 8, class: "tick", "text-anchor": "middle" }, svg); tx.textContent = lab; });
    const path = xs.map((x, i) => `${i ? "L" : "M"}${x},${ys[i]}`).join(" ");
    el("path", { d: `${path} L${xs[xs.length - 1]},${pad.t + ih} L${xs[0]},${pad.t + ih} Z`, class: "area", fill: d.color }, svg);
    el("path", { d: path, class: "line", stroke: d.color }, svg);
    xs.forEach((x, i) => el("circle", { cx: x, cy: ys[i], r: 4, class: "dot", fill: d.color }, svg));
    const last = d.x.length - 1; const endLab = el("text", { x: xs[last] + 10, y: ys[last] + 4, class: "endlabel" }, svg); endLab.textContent = d.y[last] + d.unit;
    // crosshair + tooltip
    const cross = el("line", { x1: 0, x2: 0, y1: pad.t, y2: pad.t + ih, class: "cross" }, svg); cross.style.opacity = 0;
    const tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true; host.appendChild(tip);
    const v = document.createElement("strong"); const l = document.createElement("span"); tip.append(v, l);
    function show(i) { cross.setAttribute("x1", xs[i]); cross.setAttribute("x2", xs[i]); cross.style.opacity = 1; v.textContent = d.y[i] + d.unit; l.textContent = d.x[i] + " · " + d.label; tip.hidden = false; const px = xs[i] / W * host.clientWidth; tip.style.left = Math.min(px + 12, host.clientWidth - tip.offsetWidth - 4) + "px"; tip.style.top = (ys[i] / H * host.clientHeight - 8) + "px"; }
    function hide() { cross.style.opacity = 0; tip.hidden = true; }
    svg.addEventListener("pointermove", ev => { const r = svg.getBoundingClientRect(); const x = (ev.clientX - r.left) / r.width * W; let best = 0; xs.forEach((px, i) => { if (Math.abs(px - x) < Math.abs(xs[best] - x)) best = i; }); show(best); });
    svg.addEventListener("pointerleave", hide);
    svg.tabIndex = 0; let k = 0; svg.addEventListener("keydown", ev => { if (ev.key === "ArrowRight") { k = Math.min(k + 1, last); show(k); } if (ev.key === "ArrowLeft") { k = Math.max(k - 1, 0); show(k); } }); svg.addEventListener("focus", () => show(k)); svg.addEventListener("blur", hide);
  }
  const hosts = document.querySelectorAll("[data-chart]");
  function drawAll() { hosts.forEach(h => draw(h, DATA[h.dataset.chart])); }
  drawAll(); let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(drawAll, 150); });
  // calculator
  const share = document.getElementById("share"), price = document.getElementById("price");
  if (share && price) {
    const fmt = n => n >= 1e9 ? "$" + (n / 1e9).toFixed(2) + "B" : "$" + Math.round(n / 1e6) + "M";
    function calc() { const s = +share.value, p = +price.value, seats = 180e6 * s / 100, arr = seats * p * 12;
      document.getElementById("share-out").textContent = s.toFixed(1) + "%"; document.getElementById("price-out").textContent = "$" + p;
      document.getElementById("seats").textContent = seats >= 1e6 ? (seats / 1e6).toFixed(1) + "M" : Math.round(seats / 1e3) + "K";
      document.getElementById("arr").textContent = fmt(arr); document.getElementById("vs").textContent = Math.round(arr / 2e9 * 100) + "%"; }
    share.addEventListener("input", calc); price.addEventListener("input", calc); calc();
  }
})();
