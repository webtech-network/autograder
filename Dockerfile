# 1. Use an official Python image as the base
FROM python:3.10-slim

# 2. Set environment variables
ENV PYTHONUNBUFFERED=1

# 3. Install Node.js and build essentials
RUN apt-get update && \
    apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# 4. Set the working directory within the container
WORKDIR /app

# 5. Install Python dependencies
# Copy only the requirements file first to leverage Docker's cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Install Node.js dependencies
# Copy package files and install modules. Avoid using the -g flag for project dependencies.
COPY package.json package-lock.json* ./
RUN npm install

# 7. Copy the rest of the code into the working directory
COPY . .

# 8. Make the entrypoint script executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 9. Set the entrypoint to execute the script
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]