FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure globosgenerados directory exists
RUN mkdir -p globosgenerados

# Expose port
EXPOSE 5000

# Run the Flask application
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 60"]