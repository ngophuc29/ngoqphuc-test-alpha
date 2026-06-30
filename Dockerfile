FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Copy dependencies file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure Python outputs are printed immediately (no buffering)
ENV PYTHONUNBUFFERED=1

# Run the sync job by default
CMD ["python", "main.py"]
