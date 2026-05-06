FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Firefox for Selenium
RUN apt-get update && apt-get install -y \
    libpq-dev \
    firefox-esr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5002

# Run the application
CMD ["python", "app.py"]