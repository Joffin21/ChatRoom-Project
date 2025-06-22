# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /code

# Copy the requirements file and install the dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY ./app /code/app
COPY ./static /code/static

COPY run.sh .
RUN chmod +x run.sh

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["./run.sh"] 