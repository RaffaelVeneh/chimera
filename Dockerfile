# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# The command to run when the container starts.
# It collects static files and then starts the Gunicorn server.
CMD ["sh", "-c", "python manage.py collectstatic --noinput && gunicorn chimera_core.wsgi:application --bind 0.0.0.0:8000"]