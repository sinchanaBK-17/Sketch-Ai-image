(() => {
  const $ = (id) => document.getElementById(id);
  const canvas = $("canvas");
  const ctx = canvas.getContext("2d");
  const history = [];
  let drawing = false, tool = "pen", last = null;

  function resetCanvas() {
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
  function snapshot() {
    history.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
    if (history.length > 30) history.shift();
  }
  function pos(e) {
    const r = canvas.getBoundingClientRect();
    return {
      x: ((e.clientX - r.left) * canvas.width) / r.width,
      y: ((e.clientY - r.top) * canvas.height) / r.height,
    };
  }
  function drawTo(p) {
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = Number($("brushSize").value) * (tool === "eraser" ? 2 : 1);
    ctx.strokeStyle = tool === "eraser" ? "#fff" : "#000";
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last = p;
  }

  canvas.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    canvas.setPointerCapture(e.pointerId);
    snapshot();
    drawing = true;
    last = pos(e);
    drawTo({ x: last.x + 0.01, y: last.y + 0.01 }); // dot on single tap
  });
  canvas.addEventListener("pointermove", (e) => { if (drawing) drawTo(pos(e)); });
  ["pointerup", "pointercancel", "pointerleave"].forEach((ev) =>
    canvas.addEventListener(ev, () => { drawing = false; })
  );

  function setTool(t) {
    tool = t;
    $("penBtn").classList.toggle("active", t === "pen");
    $("eraserBtn").classList.toggle("active", t === "eraser");
  }
  $("penBtn").onclick = () => setTool("pen");
  $("eraserBtn").onclick = () => setTool("eraser");
  $("undoBtn").onclick = () => { const s = history.pop(); if (s) ctx.putImageData(s, 0, 0); };
  $("clearBtn").onclick = () => { snapshot(); resetCanvas(); };
  $("strength").oninput = (e) => { $("strengthVal").textContent = e.target.value; };

  $("fileInput").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) return showError("Please choose an image file.");
    const img = new Image();
    img.onload = () => {
      snapshot();
      resetCanvas();
      const scale = Math.min(canvas.width / img.width, canvas.height / img.height);
      const w = img.width * scale, h = img.height * scale;
      ctx.drawImage(img, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
      URL.revokeObjectURL(img.src);
      hideError();
    };
    img.onerror = () => showError("Could not load that image.");
    img.src = URL.createObjectURL(file);
    e.target.value = "";
  });

  function showError(msg) { const b = $("errorBox"); b.textContent = msg; b.classList.remove("hidden"); }
  function hideError() { $("errorBox").classList.add("hidden"); }

  $("generateBtn").onclick = async () => {
    hideError();
    const btn = $("generateBtn");
    btn.disabled = true;
    $("loader").classList.remove("hidden");
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image: canvas.toDataURL("image/png"),
          prompt: $("prompt").value,
          style: $("style").value,
          provider: $("provider").value,
          strength: $("strength").value,
        }),
      });
      let data;
      try { data = await res.json(); } catch { throw new Error("Server returned an unexpected response."); }
      if (!res.ok || !data.ok) throw new Error(data.error || "Generation failed.");

      const wrap = $("resultWrap");
      wrap.className = "";
      wrap.innerHTML = "";
      const img = document.createElement("img");
      img.src = data.image;
      img.alt = "Generated image";
      wrap.appendChild(img);

      const meta = $("meta");
      meta.classList.remove("hidden");
      meta.textContent = "";
      const lines = [
        `Provider: ${data.provider} · ${data.seconds}s`,
        data.note,
        `Prompt used: ${data.prompt}`,
      ];
      lines.forEach((t) => { const d = document.createElement("div"); d.textContent = t; meta.appendChild(d); });

      const dl = $("downloadBtn");
      dl.href = data.image;
      dl.classList.remove("hidden");
    } catch (err) {
      showError(err.message || "Something went wrong.");
    } finally {
      btn.disabled = false;
      $("loader").classList.add("hidden");
    }
  };

  // ---------- API key box ----------
  function setKeyUI(d) {
    const st = $("keyStatus");
    st.className = "keystatus " + (d.active ? "ok" : "bad");
    st.textContent = d.active
      ? `Active ✓ ${d.masked || ""}${typeof d.credits === "number" ? " · " + d.credits.toFixed(1) + " credits" : ""}`
      : d.message || "Not active";
    $("providerBadge").textContent = d.active ? "Stability AI ready" : "Demo mode (no active API key)";
  }
  async function loadKey() {
    try {
      const r = await fetch("/api/key");
      setKeyUI(await r.json());
    } catch { setKeyUI({ active: false, message: "Could not check key." }); }
  }
  $("keySave").onclick = async () => {
    hideError();
    const btn = $("keySave");
    btn.disabled = true;
    $("keyStatus").className = "keystatus";
    $("keyStatus").textContent = "Verifying…";
    try {
      const r = await fetch("/api/key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: $("keyInput").value }),
      });
      const d = await r.json();
      setKeyUI(d);
      if (d.active) $("keyInput").value = "";
    } catch { setKeyUI({ active: false, message: "Network error while verifying key." }); }
    finally { btn.disabled = false; }
  };
  $("keyRemove").onclick = async () => {
    const r = await fetch("/api/key", { method: "DELETE" });
    setKeyUI(await r.json());
  };
  loadKey();

  resetCanvas();
})();
