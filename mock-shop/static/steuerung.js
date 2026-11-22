/*
 * Test page logic (plain JavaScript).
 *
 * 1. Loads public settings from /api/control/config (links, voice agent id).
 * 2. The two buttons call the shop's backend (/api/control/...), which
 *    forwards the click to n8n. The browser never talks to n8n directly.
 * 3. Shows clear status messages and a countdown while a button is cooling down.
 * 4. Adds the ElevenLabs voice agent widget if an agent id is configured.
 */

const $ = (id) => document.getElementById(id);

const actions = {
  check: {
    button: $("btn-check"),
    status: $("status-check"),
    url: "/api/control/check-new-products",
    body: () => ({ limit: Number($("limit").value), collection: $("collection").value }),
    success: "Gestartet! In ca. 10–30 Sekunden stehen neue Produkte im Google Sheet (Status „Wartet auf Freigabe“). Weiter mit Schritt 2.",
  },
  upload: {
    button: $("btn-upload"),
    status: $("status-upload"),
    url: "/api/control/upload-approved",
    body: () => ({}),
    success: "Gestartet! In wenigen Sekunden sind die freigegebenen Produkte im Shop. Status im Sheet: „Hochgeladen“.",
  },
};

function showStatus(action, text, kind) {
  action.status.textContent = text;
  action.status.className = `status ${kind}`;
}

/** Disable a button and count down, e.g. "Bitte warten (42 s)". */
function cooldown(action, seconds) {
  const { button } = action;
  button.disabled = true;
  let left = seconds;
  const tick = () => {
    if (left <= 0) {
      button.disabled = false;
      button.textContent = button.dataset.label;
      return;
    }
    button.textContent = `Bitte warten (${left} s)`;
    left -= 1;
    setTimeout(tick, 1000);
  };
  tick();
}

async function run(name) {
  const action = actions[name];
  const password = $("password").value;
  if (!password) {
    showStatus(action, "Bitte zuerst das Demo-Passwort eingeben.", "error");
    $("password").focus();
    return;
  }

  action.button.disabled = true;
  showStatus(action, "Wird gestartet …", "info");
  try {
    const res = await fetch(action.url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password, ...action.body() }),
    });
    const data = await res.json().catch(() => ({}));

    if (res.ok) {
      showStatus(action, action.success, "ok");
      cooldown(action, window.COOLDOWN || 60);
    } else if (res.status === 429) {
      showStatus(action, data.detail || "Bitte kurz warten.", "info");
      cooldown(action, Number(res.headers.get("Retry-After")) || 30);
    } else {
      const detail = typeof data.detail === "string" ? data.detail : "Unbekannter Fehler.";
      showStatus(action, detail, "error");
      action.button.disabled = false;
    }
  } catch {
    showStatus(action, "Keine Verbindung zum Server.", "error");
    action.button.disabled = false;
  }
}

function addVoiceAgent(agentId) {
  // Official ElevenLabs embed: a custom element + their script
  const widget = document.createElement("elevenlabs-convai");
  widget.setAttribute("agent-id", agentId);
  document.body.append(widget);
  const script = document.createElement("script");
  script.src = "https://unpkg.com/@elevenlabs/convai-widget-embed";
  script.async = true;
  document.body.append(script);
}

async function init() {
  $("btn-check").addEventListener("click", () => run("check"));
  $("btn-upload").addEventListener("click", () => run("upload"));

  try {
    const cfg = await (await fetch("/api/control/config")).json();
    window.COOLDOWN = cfg.cooldown;
    $("supplier-link").href = cfg.supplier_url;
    $("shop-count").textContent = `(${cfg.shop_product_count} Produkte)`;

    if (cfg.sheet_url) {
      $("sheet-link").href = cfg.sheet_url;
    } else {
      $("sheet-link").removeAttribute("href");
      $("sheet-link").classList.add("disabled");
      $("sheet-link").textContent = "📄 Google Sheet (Link nicht eingerichtet)";
    }
    if (!cfg.enabled) {
      $("not-configured").hidden = false;
      Object.values(actions).forEach((a) => (a.button.disabled = true));
    }
    if (cfg.voice_agent_id) addVoiceAgent(cfg.voice_agent_id);
  } catch {
    $("not-configured").hidden = false;
  }
}

init();
