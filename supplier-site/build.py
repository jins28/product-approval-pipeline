"""
Builds the fictional supplier website "Nordholm Furniture Co." into ./public

    python build.py

Input:  products.json (all product data in one file)
Output: public/index.html            -> catalogue page with all products
        public/products/<slug>.html  -> one page per product
        public/images/<slug>-N.svg   -> simple drawn product images
        public/robots.txt            -> scrapers are welcome

The output is plain static HTML (no JavaScript needed to see the products),
so it can be hosted anywhere: Netlify (drag & drop the public folder),
or locally with the "supplier" container in docker-compose.

Everything here is invented: names, texts and drawings are our own,
so the site and the scraped data can be published freely.
"""

import html
import json
import shutil
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "public"
COMPANY = "Nordholm Furniture Co."

CSS = """
*{box-sizing:border-box}body{margin:0;font-family:Georgia,'Times New Roman',serif;color:#2a2622;background:#fbf9f6;line-height:1.55}
a{color:inherit}.banner{background:#2a2622;color:#f3eee6;font:13px/1.4 system-ui,sans-serif;text-align:center;padding:.45rem 1rem}
header{padding:1.2rem clamp(1rem,4vw,3rem);border-bottom:1px solid #e6dfd4;display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:.5rem}
.logo{font-size:1.4rem;letter-spacing:.08em;text-transform:uppercase;text-decoration:none}.sub{font:14px system-ui,sans-serif;color:#7a7268}
main{max-width:1100px;margin:0 auto;padding:1.5rem clamp(1rem,4vw,3rem) 3rem}
.grid{display:grid;gap:1.25rem;grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}
.product-card{display:block;text-decoration:none;background:#fff;border:1px solid #e6dfd4;border-radius:6px;overflow:hidden}
.product-card img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block}.card-body{padding:.8rem 1rem 1rem}
.card-body h2{font-size:1.05rem;margin:0 0 .2rem}.price{font-family:system-ui,sans-serif;font-weight:600}
.cat{font:12px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.08em;color:#7a7268}
.product{display:grid;gap:2rem;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr)}@media(max-width:780px){.product{grid-template-columns:1fr}}
.gallery img{width:100%;border-radius:6px;border:1px solid #e6dfd4;margin-bottom:.6rem;display:block}
h1{margin:.2rem 0 .4rem;font-size:1.7rem}.sku{font:13px system-ui,sans-serif;color:#7a7268}
details{border-top:1px solid #e6dfd4;padding:.7rem 0}details:last-of-type{border-bottom:1px solid #e6dfd4}
summary{cursor:pointer;font-weight:bold}details ul{margin:.5rem 0 0;padding-left:1.2rem}
footer{text-align:center;font:13px system-ui,sans-serif;color:#7a7268;padding:2rem 1rem}
"""


def esc(value) -> str:
    return html.escape(str(value))


def euro(price: str) -> str:
    whole, cents = f"{float(price):.2f}".split(".")
    return f"€{int(whole):,}.{cents}"


# ---------------------------------------------------------------------------
# Drawn product images (SVG)
# ---------------------------------------------------------------------------

def svg(shape: str, color: str, dark: str, background: str) -> str:
    """A simple flat drawing of a sofa or chair."""
    legs = '<rect x="{x}" y="330" width="14" height="40" rx="3" fill="#5a4632"/>'
    if shape.startswith("sofa"):
        r = 60 if shape == "sofa-round" else 14
        body = f"""
<rect x="170" y="150" width="460" height="130" rx="{r}" fill="{dark}"/>
<rect x="130" y="255" width="540" height="85" rx="{22 if r == 60 else 8}" fill="{color}"/>
<rect x="105" y="205" width="85" height="140" rx="{30 if r == 60 else 8}" fill="{dark}"/>
<rect x="610" y="205" width="85" height="140" rx="{30 if r == 60 else 8}" fill="{dark}"/>
<rect x="195" y="236" width="200" height="40" rx="12" fill="{color}"/>
<rect x="405" y="236" width="200" height="40" rx="12" fill="{color}"/>
{legs.format(x=150)}{legs.format(x=636)}"""
    elif shape == "armchair":
        body = f"""
<rect x="290" y="130" width="220" height="160" rx="40" fill="{dark}"/>
<rect x="270" y="262" width="260" height="78" rx="18" fill="{color}"/>
<rect x="240" y="215" width="70" height="130" rx="26" fill="{dark}"/>
<rect x="490" y="215" width="70" height="130" rx="26" fill="{dark}"/>
{legs.format(x=262)}{legs.format(x=524)}"""
    else:  # dining / accent chair
        body = f"""
<rect x="320" y="120" width="160" height="150" rx="28" fill="{color}" stroke="{dark}" stroke-width="10"/>
<rect x="300" y="268" width="200" height="34" rx="8" fill="{dark}"/>
<rect x="312" y="300" width="14" height="80" rx="4" fill="{dark}"/>
<rect x="474" y="300" width="14" height="80" rx="4" fill="{dark}"/>"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600">'
            f'<rect width="800" height="600" fill="{background}"/>'
            f'<ellipse cx="400" cy="375" rx="300" ry="14" fill="#000" opacity=".07"/>{body}</svg>')


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page(title: str, body: str, root: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><link rel="stylesheet" href="{root}style.css"></head>
<body>
<div class="banner">Fictional demo supplier for a portfolio project – not a real company, no orders possible.</div>
<header><a class="logo" href="{root}index.html">{COMPANY}</a><span class="sub">Trade catalogue · Sofas &amp; Chairs</span></header>
<main>{body}</main>
<footer>© {COMPANY} (fictional) · Product data for automation testing</footer>
</body></html>"""


def catalogue(products: list[dict]) -> str:
    cards = "\n".join(
        f"""<a class="product-card" href="products/{p['slug']}.html" data-category="{esc(p['category'].lower())}">
  <img src="images/{p['slug']}-1.svg" alt="{esc(p['name'])}">
  <div class="card-body"><div class="cat">{esc(p['category'])}</div><h2>{esc(p['name'])}</h2>
  <div class="price">{euro(p['price'])}</div></div></a>"""
        for p in products
    )
    body = f"<h1>All products ({len(products)})</h1>\n<div class=\"grid\">\n{cards}\n</div>"
    return page(f"Catalogue · {COMPANY}", body, root="")


def product_page(p: dict) -> str:
    def section(title: str, lines: list[str], open_: bool = False) -> str:
        items = "".join(f"<li>{esc(line)}</li>" for line in lines)
        return f'<details{" open" if open_ else ""}><summary>{esc(title)}</summary><div><ul>{items}</ul></div></details>'

    images = "".join(
        f'<img class="gallery-image" src="../images/{p["slug"]}-{n}.svg" alt="{esc(p["name"])} – view {n}">'
        for n in (1, 2)
    )
    body = f"""<p><a href="../index.html">← Back to catalogue</a></p>
<div class="product" data-category="{esc(p['category'].lower())}">
  <div class="gallery">{images}</div>
  <div class="info">
    <div class="cat">{esc(p['category'])}</div>
    <h1 class="product-title">{esc(p['name'])}</h1>
    <p class="price" data-price="{esc(p['price'])}">{euro(p['price'])}</p>
    <p class="sku">Item no. <span data-sku>{esc(p['sku'])}</span></p>
    <div class="description"><p>{esc(p['description'])}</p></div>
    {section("Dimensions", p["dimensions"], open_=True)}
    {section("Material & Construction", p["material"])}
    {section("Features & Feel", p["features"])}
  </div>
</div>"""
    return page(f"{p['name']} · {COMPANY}", body, root="../")


def build() -> None:
    products = json.loads((HERE / "products.json").read_text(encoding="utf-8"))
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "products").mkdir(parents=True)
    (OUT / "images").mkdir()

    (OUT / "style.css").write_text(CSS.strip(), encoding="utf-8")
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (OUT / "index.html").write_text(catalogue(products), encoding="utf-8")
    for p in products:
        (OUT / "products" / f"{p['slug']}.html").write_text(product_page(p), encoding="utf-8")
        (OUT / "images" / f"{p['slug']}-1.svg").write_text(svg(p["shape"], p["color"], p["dark"], "#f3efe8"), encoding="utf-8")
        (OUT / "images" / f"{p['slug']}-2.svg").write_text(svg(p["shape"], p["color"], p["dark"], "#e4ddd1"), encoding="utf-8")
    print(f"Built {len(products)} products into {OUT}")


if __name__ == "__main__":
    build()
