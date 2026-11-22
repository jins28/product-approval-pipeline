"""
Scraper API: lets n8n start the scraper with a simple HTTP request.

    GET /health                      -> {"status": "ok"}
    GET /scrape?limit=5              -> scraped products as JSON
    GET /scrape?limit=5&images=false -> same, without downloading images
    GET /scrape?source=supplier&collection=chair         -> demo supplier, chairs only
    GET /scrape?source=shopify&collection=sofas          -> the Shopify store from .env
        (for Shopify a full collection link works too)

Why an API instead of running a script from n8n?
n8n just sees one more HTTP endpoint (easy to call, easy to test in the
browser or Postman). The scraper keeps its own Python libraries in its own
container, and n8n's "Execute Command" node is disabled by default in
newer n8n versions for security reasons.
"""

from fastapi import FastAPI, HTTPException, Query

import scraper

app = FastAPI(title="Scraper API", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/scrape")
def scrape(limit: int = Query(5, ge=1, le=50), images: bool = True,
           collection: str = "", source: str | None = None) -> dict:
    # A plain "def" (not async): FastAPI runs it in a worker thread,
    # so the slow, polite scraping does not block other requests.
    source = source or scraper.SOURCE
    if source not in scraper.SOURCES:
        raise HTTPException(status_code=422, detail=f"source must be one of {scraper.SOURCES}")
    try:
        # for the supplier, collection is just a simple filter word ("sofa"/"chair")
        if source == "shopify":
            handle = scraper.collection_handle(collection or scraper.COLLECTION)
        else:
            handle = collection or "all"
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    try:
        return scraper.scrape(limit=limit, with_images=images, collection=handle, source=source)
    except ValueError as err:      # e.g. Shopify store not configured
        raise HTTPException(status_code=422, detail=str(err)) from err
    except Exception as err:
        # Whole run failed (e.g. site unreachable): clear error for n8n
        raise HTTPException(status_code=502, detail=f"Scraping failed: {err}") from err
