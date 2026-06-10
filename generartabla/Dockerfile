FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi8 \
    libglib2.0-0 \
    fontconfig \
    fonts-dejavu-core \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p globosgenerados
EXPOSE 5002
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-5002} --workers 1 --timeout 120"]
