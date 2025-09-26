# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
# The build context is the root, so we can copy it directly.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend application code into the container
COPY backend/ /app

# Expose the port the app runs on
EXPOSE 8000

# Specify the command to run the Flask application
# Use gunicorn for a production-ready server.
# We need to add a dependency on gunicorn to requirements.txt
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "main:app"]