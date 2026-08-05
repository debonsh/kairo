FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (config + source). Secrets stay out of the image — use env_file in compose.
COPY config ./config
COPY src ./src

# API server + Streamlit dashboard
EXPOSE 8000 8501

CMD ["python", "-m", "src.main"]
