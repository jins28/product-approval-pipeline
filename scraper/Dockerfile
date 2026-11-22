FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scraper.py app.py ./

# Run as a normal user, not root
RUN useradd --create-home scraper && mkdir -p /app/data/media && chown -R scraper /app/data
USER scraper

EXPOSE 8002
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
