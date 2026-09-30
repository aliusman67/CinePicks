/* CinePicks - Frontend (vanilla JS, tanpa framework) */
(function () {
  "use strict";

  // Helper pencarian elemen yang aman: jika elemen tidak ada (mis. HTML lama
  // ter-cache), kembalikan stub agar aplikasi tetap berjalan dan tidak mati total.
  function $(id) {
    var el = document.getElementById(id);
    if (el) return el;
    return {
      addEventListener: function () {}, querySelector: function () { return { hidden: false }; },
      style: {}, classList: { add: function () {}, remove: function () {} },
      value: "", placeholder: "", textContent: "", hidden: false, disabled: false,
      scrollTop: 0, scrollHeight: 0, files: [],
      remove: function () {}, appendChild: function () {}, insertAdjacentHTML: function () {},
      removeAttribute: function () {}, setAttribute: function () {}, focus: function () {},
      click: function () {},
    };
  }

  var chatEl = $("chat");
  var formEl = $("composer");
  var inputEl = $("textInput");
  var sendBtn = $("sendBtn");
  var sendIco = sendBtn.querySelector(".send-ico");
  var spinEl = sendBtn.querySelector(".spin");
  var uploadBtn = $("uploadBtn");
  var fileInput = $("fileInput");
  var previewEl = $("preview");
  var previewImg = $("previewImg");
  var previewName = $("previewName");
  var previewClear = $("previewClear");
  var chipsEl = $("chips");
  var heroEl = $("hero");
  var heroActions = $("heroActions");
  var statusEl = $("statusText");

  var pendingFile = null;
  var previewUrl = null;
  var busy = false;
  var firstSend = true;

  // ID sesi untuk dukungan multi-turn ("lagi", "lainnya") di backend
  var sessionId = null;
  try {
    sessionId = localStorage.getItem("cinepicks_sid");
    if (!sessionId) {
      sessionId = "s" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
      localStorage.setItem("cinepicks_sid", sessionId);
    }
  } catch (e) {
    // localStorage diblokir (private mode) — fallback ke sesi per halaman
    sessionId = "s" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  /* ---------------- util ---------------- */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function nl2br(s) { return esc(s).replace(/\n/g, "<br>"); }
  function nowTime() {
    return new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
  }
  function scrollDown() { chatEl.scrollTop = chatEl.scrollHeight; }

  // Fallback gambar gagal dimuat (CSP-safe, tanpa inline onerror)
  chatEl.addEventListener("error", function (e) {
    if (e.target && e.target.tagName === "IMG") e.target.remove();
  }, true);

  function fetchTimeout(url, opts, ms) {
    var timer = null;
    var req = fetch(url, opts);
    if (typeof AbortController !== "undefined") {
      var ctrl = new AbortController();
      timer = setTimeout(function () { ctrl.abort(); }, ms || 20000);
      req = fetch(url, Object.assign({}, opts, { signal: ctrl.signal }));
    }
    // Bersihkan timer tanpa .finally() agar kompatibel dengan browser lama
    req.then(function () { if (timer) clearTimeout(timer); },
             function () { if (timer) clearTimeout(timer); });
    return req;
  }

  /* ---------------- render ---------------- */
  function msgShell(role, name) {
    return (
      '<div class="msg ' + role + '">' +
        '<div class="msg-head">' +
          '<span class="avatar">' + (role === "bot" ? "C" : "K") + "</span>" +
          '<span class="msg-name">' + esc(name) + '</span>' +
          '<span class="msg-time">' + nowTime() + "</span>" +
        "</div>" +
      "</div>"
    );
  }

  function addUser(text, imageUrl) {
    var div = document.createElement("div");
    div.innerHTML = msgShell("user", "Kamu");
    var inner = "";
    if (imageUrl) {
      inner += '<img src="' + imageUrl + '" alt="foto terkirim" style="max-width:230px;border-radius:12px;display:block;margin-bottom:6px;">';
    }
    if (text) inner += '<div class="bubble">' + nl2br(text) + "</div>";
    div.firstChild.insertAdjacentHTML("beforeend", inner);
    chatEl.appendChild(div.firstChild);
    scrollDown();
  }

  function addTyping() {
    var div = document.createElement("div");
    div.innerHTML = msgShell("bot", "CinePicks");
    var msgEl = div.firstChild;
    if (!msgEl) {
      msgEl = document.createElement("div");
      msgEl.className = "msg bot";
    }
    msgEl.insertAdjacentHTML(
      "beforeend",
      '<div class="bubble typing"><span></span><span></span><span></span></div>'
    );
    chatEl.appendChild(msgEl);
    scrollDown();
    return msgEl;
  }

  function movieCard(m) {
    var letter = esc((m.title || "?").charAt(0));
    var img = m.poster
      ? '<img src="' + esc(m.poster) + '" alt="' + esc(m.title) + '" loading="lazy">'
      : "";
    var poster =
      '<div class="poster"><span class="poster-letter">' + letter + "</span>" + img +
      '<span class="badge">&#9733; ' + esc(m.rating) + "</span>" +
      '<span class="badge-year">' + esc(m.year) + "</span></div>";
    var genres = (m.genres || []).map(function (g) { return "<span>" + esc(g) + "</span>"; }).join("");
    var stars = "";
    var r = Math.round((m.rating || 0) / 2);
    for (var i = 0; i < 5; i++) stars += i < r ? "&#9733;" : "&#9734;";
    return (
      '<div class="card">' +
        poster +
        '<div class="info">' +
          '<div class="title">' + esc(m.title) + "</div>" +
          '<div class="meta"><span class="star">' + stars + "</span> " + esc(m.rating) +
          " &middot; " + esc((m.votes || 0).toLocaleString("id")) + " votes</div>" +
          '<div class="genres">' + genres + "</div>" +
          (m.reason ? '<div class="why"><b>Kenapa direkomendasikan:</b> ' + nl2br(m.reason) + "</div>" : "") +
          (m.description || m.overview
            ? '<div class="syn"><b>Deskripsi:</b> ' + esc(m.description || m.overview) + "</div>"
            : "") +
        "</div>" +
      "</div>"
    );
  }

  function addBot(data) {
    var div = document.createElement("div");
    div.innerHTML = msgShell("bot", "CinePicks");
    var inner = '<div class="bubble">' + nl2br(data.reply || "") + "</div>";
    if (data.movies && data.movies.length) {
      inner += '<div class="bubble" style="max-width:100%;background:transparent;border:none;padding:0;">' +
        '<div class="movies">' + data.movies.map(movieCard).join("") + "</div></div>";
    }
    div.firstChild.insertAdjacentHTML("beforeend", inner);
    chatEl.appendChild(div.firstChild);
    scrollDown();
  }

  function addError(text) {
    var div = document.createElement("div");
    div.innerHTML = msgShell("bot", "CinePicks");
    div.firstChild.insertAdjacentHTML("beforeend", '<div class="bubble err">' + nl2br(text) + "</div>");
    chatEl.appendChild(div.firstChild);
    scrollDown();
  }

  function setBusy(v) {
    busy = v;
    sendBtn.disabled = v;
    uploadBtn.disabled = v;
    sendIco.hidden = v;
    spinEl.hidden = !v;
  }

  /* ---------------- API ---------------- */
  function postChat(message) {
    return fetchTimeout("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message, session_id: sessionId }),
    }, 20000).then(function (r) { return r.json(); });
  }
  function postUpload(file, caption) {
    var fd = new FormData();
    fd.append("file", file);
    if (caption) fd.append("caption", caption);
    return fetchTimeout("/api/upload", { method: "POST", body: fd }, 60000).then(function (r) { return r.json(); });
  }

  /* ---------------- aksi kirim ---------------- */
  function submit() {
    var text = inputEl.value.trim();
    var hasImage = !!pendingFile;
    if (busy || (!text && !hasImage)) return;

    var file = pendingFile;
    var imgUrl = null;
    if (file) imgUrl = URL.createObjectURL(file);

    if (firstSend) {
      firstSend = false;
      heroEl.classList.add("hidden");
    }
    addUser(text || "Analisis foto ini:", imgUrl);
    inputEl.value = "";
    clearPreview();
    var typing = addTyping();
    setBusy(true);

    var p = hasImage ? postUpload(file, text) : postChat(text);

    function finish() {
      setBusy(false);
      inputEl.focus();
    }
    p.then(function (data) {
      typing.remove();
      if (data && data.error) addError("Maaf: " + data.error);
      else addBot(data);
      finish();
    }, function () {
      typing.remove();
      addError("Gagal terhubung ke server. Pastikan backend berjalan.");
      finish();
    });
  }

  /* ---------------- upload ---------------- */
  function clearPreview() {
    if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
    pendingFile = null;
    fileInput.value = "";
    previewImg.removeAttribute("src");
    previewName.textContent = "";
    previewEl.hidden = true;
  }

  uploadBtn.addEventListener("click", function () { fileInput.click(); });
  fileInput.addEventListener("change", function () {
    var f = fileInput.files && fileInput.files[0];
    if (!f) return;
    if (!f.type || f.type.indexOf("image/") !== 0) {
      addError("File harus berupa gambar (JPEG, PNG, WebP, GIF, BMP).");
      fileInput.value = "";
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      addError("Ukuran gambar maksimal 10 MB.");
      fileInput.value = "";
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(f);
    pendingFile = f;
    previewImg.src = previewUrl;
    previewName.textContent = f.name + " (" + Math.round(f.size / 1024) + " KB)";
    previewEl.hidden = false;
    inputEl.placeholder = "Tambahkan catatan (opsional) lalu kirim...";
  });
  previewClear.addEventListener("click", function () {
    clearPreview();
    inputEl.placeholder = "Genre, mood, judul, atau tahun...";
  });

  /* ---------------- chips ---------------- */
  function chipClick(e) {
    var btn = e.target.closest(".chip");
    if (!btn || busy) return;
    inputEl.value = btn.getAttribute("data-q");
    submit();
  }
  chipsEl.addEventListener("click", chipClick);
  heroActions.addEventListener("click", chipClick);

  /* ---------------- form ---------------- */
  formEl.addEventListener("submit", function (e) {
    e.preventDefault();
    submit();
  });

  /* ---------------- health ---------------- */
  // Tampilkan error tak terduga di chat agar tidak gagal senyap
  window.addEventListener("error", function (e) {
    if (e && e.message && chatEl && chatEl.appendChild) {
      addError("Error: " + e.message);
    }
  });

  fetch("/api/health")
    .then(function (r) { return r.json(); })
    .then(function (h) {
      if (h && h.status === "ok") statusEl.textContent = "online · " + h.movies + " film";
      else statusEl.textContent = "offline";
    })
    .catch(function () {
      statusEl.textContent = "offline";
      document.querySelector(".dot").style.background = "#e74c3c";
      document.querySelector(".dot").style.boxShadow = "none";
    });
})();
