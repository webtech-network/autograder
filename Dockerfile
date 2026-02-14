# 1. Use an official Python image as the base
FROM python:3.10-slim

# 2. Set environment variables
ENV PYTHONUNBUFFERED=1

# 3. Install Node.js and other necessary tools

RUN apt-get update && \
    apt-get install -y tree curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs


# 4. Set the working directory for the rest of the build
WORKDIR /app

# 5. Copy and install Python dependencies first to leverage caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN echo "INSIDE DOCKERFILE THIS IS GRADING_PRESET ${GRADING_PRESET}"

# 6. Copy the rest of your application code
COPY . .

# 8. Copy the entrypoint and make it executable
COPY github_action/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 9. Set the entrypoint for the container
ENTRYPOINT ["/entrypoint.sh"]