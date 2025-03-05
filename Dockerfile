# Use official Python image as base
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 5000

# Run migrations and start the app when the container starts
CMD ["sh", "-c", "flask db upgrade && flask run --host=0.0.0.0"]