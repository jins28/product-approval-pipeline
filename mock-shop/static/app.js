/*
 * Minimal storefront: plain JavaScript, no framework, no build step.
 *
 * How it works
 * 1. On page load we fetch GET /api/storefront/products (public, read-only).
 * 2. The URL "hash" decides what to show (simple client-side routing):
 *      #/              -> product grid with search and sorting
 *      #/produkt/12    -> detail page of product 12
 * 3. All text from the API is inserted with textContent, never innerHTML,
 *    so scraped content can never inject HTML or scripts into our page.
 */

const app = document.getElementById("app");
let products = [];
let currency = "EUR";
const view = { search: "", sort: "newest" };   // remembered between views

// ---------- helpers ----------

/** Create an element: el("h2", {class: "x"}, "text", childElement, ...) */
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child == null) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function formatPrice(value) {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency }).format(Number(value));
}

/** Image box with a neutral placeholder when a product has no picture. */
function imageBox(image, fallbackAlt) {
  const box = el("div", { class: "img-box" });
  if (image) {
    box.append(el("img", { src: image.src, alt: image.alt || fallbackAlt, loading: "lazy" }));
  } else {
    box.append(el("span", { class: "img-placeholder" }, "Kein Bild vorhanden"));
  }
  return box;
}

// ---------- views ----------

function renderGrid() {
  document.title = "Demo Möbelshop";

  const search = el("input", {
    type: "search", placeholder: "Produkte suchen …", "aria-label": "Produkte suchen",
    value: view.search,
    oninput: (e) => { view.search = e.target.value; drawCards(); },
  });

  const sort = el("select", { "aria-label": "Sortieren", onchange: (e) => { view.sort = e.target.value; drawCards(); } },
    el("option", { value: "newest" }, "Neueste zuerst"),
    el("option", { value: "price-asc" }, "Preis aufsteigend"),
    el("option", { value: "price-desc" }, "Preis absteigend"),
    el("option", { value: "name" }, "Name A–Z"),
  );
  sort.value = view.sort;

  const count = el("h1");
  const grid = el("div", { class: "grid" });

  function drawCards() {
    const term = view.search.trim().toLowerCase();
    const list = products
      .filter((p) => p.title.toLowerCase().includes(term))
      .sort((a, b) => {
        if (view.sort === "price-asc") return a.price - b.price;
        if (view.sort === "price-desc") return b.price - a.price;
        if (view.sort === "name") return a.title.localeCompare(b.title, "de");
        return b.id - a.id;  // newest first
      });

    count.textContent = `Alle Produkte (${list.length})`;
    grid.replaceChildren(
      ...list.map((p) =>
        el("a", { class: "card", href: `#/produkt/${p.id}` },
          imageBox(p.images[0], p.title),
          el("div", { class: "card-body" },
            el("h2", {}, p.title),
            el("div", { class: "price" }, formatPrice(p.price)),
          ),
        ),
      ),
    );
    if (list.length === 0) {
      grid.replaceChildren(el("p", { class: "status" },
        products.length ? "Keine Treffer für diese Suche." : "Noch keine Produkte hochgeladen."));
    }
  }

  app.replaceChildren(el("div", { class: "toolbar" }, count, search, sort), grid);
  drawCards();
}

function renderDetail(id) {
  const p = products.find((x) => x.id === id);
  if (!p) {
    app.replaceChildren(el("a", { class: "back", href: "#/" }, "← Zurück zur Übersicht"),
      el("p", { class: "status" }, "Dieses Produkt gibt es nicht (mehr)."));
    return;
  }
  document.title = `${p.title} · Demo Möbelshop`;

  // Gallery: big image + clickable thumbnails
  const mainSlot = el("div", {}, imageBox(p.images[0], p.title));  // big image lives here
  const thumbs = el("div", { class: "thumbs" });
  p.images.forEach((img, i) => {
    const btn = el("button", {
      type: "button", "aria-label": `Bild ${i + 1} anzeigen`, "aria-current": String(i === 0),
      onclick: () => {
        mainSlot.replaceChildren(imageBox(img, p.title));
        thumbs.querySelectorAll("button").forEach((b) => b.setAttribute("aria-current", String(b === btn)));
      },
    }, el("img", { src: img.src, alt: "" }));
    thumbs.append(btn);
  });
  const gallery = el("div", { class: "gallery" }, mainSlot, p.images.length > 1 ? thumbs : null);

  // Accordion sections: only shown if the field has content
  const section = (title, text, open = false) =>
    text ? el("details", open ? { open: "" } : {}, el("summary", {}, title), el("p", {}, text)) : null;

  app.replaceChildren(
    el("a", { class: "back", href: "#/" }, "← Zurück zur Übersicht"),
    el("div", { class: "detail" },
      gallery,
      el("div", { class: "info" },
        el("div", { class: "type" }, p.product_type),
        el("h1", {}, p.title),
        el("div", { class: "price" }, formatPrice(p.price)),
        p.description ? el("p", { class: "description" }, p.description) : null,
        el("button", { class: "cart-btn", type: "button", disabled: "" }, "In den Warenkorb"),
        el("p", { class: "cart-note" }, "Demo-Shop: Bestellungen sind nicht möglich."),
        section("Abmessungen", p.dimensions, true),
        section("Material & Verarbeitung", p.material_construction),
        section("Eigenschaften & Haptik", p.features_feel),
      ),
    ),
  );
  window.scrollTo(0, 0);
}

// ---------- routing ----------

function route() {
  const match = location.hash.match(/^#\/produkt\/(\d+)$/);
  if (match) renderDetail(Number(match[1]));
  else renderGrid();
}

async function start() {
  try {
    const res = await fetch("/api/storefront/products");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    products = data.products;
    currency = data.currency || "EUR";
    route();
    window.addEventListener("hashchange", route);
  } catch (err) {
    app.replaceChildren(el("p", { class: "error" }, `Produkte konnten nicht geladen werden (${err.message}).`));
  }
}

start();
