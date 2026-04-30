# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8501

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download the spaCy model during the build phase
RUN python -m spacy download en_core_web_sm

# Copy the rest of the application code into the container
COPY . .

# Create a directory for persistent data (matching the Volume mount point)
RUN mkdir -p /app/data

# Expose the port Streamlit will run on
EXPOSE ${PORT}

# Healthcheck to ensure the app is running
HEALTHCHECK CMD curl --fail http://localhost:${PORT}/_stcore/health

# Command to run the application
ENTRYPOINT streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0
