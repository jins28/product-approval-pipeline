FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY static ./static

# Run as a normal user, not root (security best practice)
RUN useradd --create-home shop && mkdir -p /app/data/media && chown shop /app/data
USER shop

EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
