FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy test script
COPY mysql_test.py .

# Set environment variables (can be overridden at runtime)
ENV MYSQL_HOST=localhost
ENV MYSQL_USER=root
ENV MYSQL_DB=perftest

# Default command shows help
ENTRYPOINT ["python3", "mysql_test.py"]
CMD ["--help"]
