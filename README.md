# MySQL Performance Testing Tool

Comprehensive MySQL performance testing script that measures write and read operations under various scenarios.

## Features

- Connection testing and validation
- Connection pooling for efficient resource management
- Environment variable support for secure credential handling
- SSL/TLS support for encrypted connections
- Read and write performance tests with detailed metrics
- Robust error handling and validation
- Configurable commit batching
- Detailed latency statistics (avg, median, P95, P99)
- JSON output for result analysis

## Prerequisites

- Python 3.6 or higher
- MySQL server (local or remote)
- Database user with CREATE, DROP, INSERT, UPDATE, SELECT permissions

## Installation

### Option 1: Using the wrapper script (Recommended)

The `mysql_test.sh` script automatically manages the virtual environment:

```bash
./mysql_test.sh --help
```

### Option 2: Manual setup

1. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the script:
```bash
python3 mysql_test.py --help
```

## Quick Start

### 1. Set environment variables (Recommended for security):

```bash
export MYSQL_HOST=localhost
export MYSQL_USER=root
export MYSQL_PASS=your_password
export MYSQL_DB=perftest
```

### 2. Test connection:

```bash
./mysql_test.sh --test-connection-only
```

### 3. Run basic performance test:

```bash
./mysql_test.sh --label "Local-MySQL"
```

## Usage Examples

### Basic Tests

```bash
# Quick test with default settings
./mysql_test.sh --host localhost --user root --pass mypass --label "Local-MySQL"

# Test connection only
./mysql_test.sh --host localhost --user root --pass mypass --test-connection-only
```

### Full Performance Test

```bash
./mysql_test.sh --host localhost --user root --pass mypass \
    --label "Local-MySQL" \
    --single-inserts 5000 \
    --batch-count 200 --batch-size 100 \
    --threads 20 --writes-per-thread 100 \
    --read-queries 2000 \
    --range-queries 200 --range-size 100
```

### Cloud Database with SSL

```bash
./mysql_test.sh --host rds.amazonaws.com --user admin --pass mypass \
    --ssl-ca /path/to/rds-ca-bundle.pem \
    --label "RDS-MySQL" \
    --db production_test
```

### Selective Testing

```bash
# Write tests only
./mysql_test.sh --host localhost --user root --pass mypass \
    --skip-reads --single-inserts 10000 --threads 30

# Read tests only
./mysql_test.sh --host localhost --user root --pass mypass \
    --skip-writes --read-queries 5000 --range-queries 500
```

### Realistic Commit Batching

```bash
# Commit every 10 inserts (more realistic than commit-per-insert)
./mysql_test.sh --host localhost --user root --pass mypass \
    --commit-every 10 --concurrent-commit-every 50
```

### Keep Test Data

```bash
# Don't drop the test table after completion
./mysql_test.sh --host localhost --user root --pass mypass \
    --no-cleanup
```

## Command Line Options

### Connection Parameters

| Option | Environment Variable | Description |
|--------|---------------------|-------------|
| `--host` | `MYSQL_HOST` | Database host |
| `--user` | `MYSQL_USER` | Database user |
| `--pass` | `MYSQL_PASS` or `MYSQL_PASSWORD` | Database password |
| `--db` | `MYSQL_DB` | Database name (default: perftest) |
| `--label` | - | Label for this test run |

### SSL/TLS Options

| Option | Description |
|--------|-------------|
| `--ssl-ca` | Path to SSL CA certificate |
| `--ssl-cert` | Path to SSL client certificate |
| `--ssl-key` | Path to SSL client key |

### Connection Pool Settings

| Option | Default | Description |
|--------|---------|-------------|
| `--pool-size` | 10 | Connection pool size |
| `--connect-timeout` | 10 | Connection timeout in seconds |

### Test Parameters

| Option | Default | Description |
|--------|---------|-------------|
| `--single-inserts` | 1000 | Number of single INSERT operations |
| `--commit-every` | 1 | Commit frequency for single inserts |
| `--batch-count` | 100 | Number of batch operations |
| `--batch-size` | 100 | Records per batch |
| `--threads` | 10 | Number of concurrent threads |
| `--writes-per-thread` | 100 | Writes per thread |
| `--concurrent-commit-every` | 10 | Commit frequency in concurrent test |
| `--read-queries` | 1000 | Number of point read queries |
| `--range-queries` | 100 | Number of range queries |
| `--range-size` | 100 | Rows per range query |

### Control Options

| Option | Description |
|--------|-------------|
| `--skip-writes` | Skip write tests |
| `--skip-reads` | Skip read tests |
| `--test-connection-only` | Only test connection and exit |
| `--output` | Custom output JSON filename |
| `--no-cleanup` | Don't drop test table after tests |

## Tests Performed

1. **Single INSERT Operations**: Individual INSERT statements with configurable commit frequency
2. **Batch INSERT Operations**: Bulk inserts using `executemany()`
3. **Concurrent Write Operations**: Multi-threaded write testing
4. **UPDATE Operations**: Individual UPDATE statements
5. **Point Read Operations**: SELECT by primary key (fastest reads)
6. **Range Read Operations**: SELECT with LIMIT (multi-row queries)

## Metrics Collected

For each test, the following metrics are captured:

- **Total Time**: Overall test duration in seconds
- **Throughput**: TPS (transactions/sec) or QPS (queries/sec)
- **Average Latency**: Mean operation time in milliseconds
- **Median Latency**: 50th percentile
- **P95 Latency**: 95th percentile (useful for SLA definition)
- **P99 Latency**: 99th percentile (outlier detection)
- **Min/Max Latency**: Fastest and slowest operations

## Output

Results are automatically saved to the `output/` directory with the naming pattern:
```
output/mysql_perf_<label>_<timestamp>.json
```

Example output structure:
```json
{
  "label": "Local-MySQL",
  "host": "localhost",
  "database": "perftest",
  "timestamp": "2025-01-15T10:30:00.123456",
  "results": {
    "single_inserts": {
      "total_time_sec": 12.34,
      "records": 1000,
      "tps": 81.03,
      "avg_latency_ms": 12.34,
      "p95_latency_ms": 23.45
    },
    ...
  }
}
```

## Security Best Practices

1. **Use environment variables for passwords**:
   ```bash
   export MYSQL_PASS=your_password
   ./mysql_test.sh --host localhost --user root
   ```

2. **Enable SSL/TLS for cloud databases**:
   ```bash
   ./mysql_test.sh --host rds.amazonaws.com --user admin --pass mypass \
       --ssl-ca /path/to/ca-bundle.pem
   ```

3. **Use dedicated test database**:
   - Don't test on production databases
   - Create a separate database for performance testing

4. **Limit permissions**:
   - Test user only needs: CREATE, DROP, INSERT, UPDATE, SELECT
   - No need for GRANT, SUPER, or other admin privileges

## Troubleshooting

### Connection Refused
```bash
# Check if MySQL is running
mysql -u root -p -e "SELECT 1"

# Check host and port
./mysql_test.sh --host localhost --user root --pass mypass --test-connection-only
```

### Permission Denied
```sql
-- Grant required permissions
GRANT CREATE, DROP, INSERT, UPDATE, SELECT ON perftest.* TO 'testuser'@'localhost';
FLUSH PRIVILEGES;
```

### SSL Connection Issues
```bash
# Verify SSL certificate path
ls -l /path/to/ca-bundle.pem

# Test SSL connection manually
mysql --host=rds.amazonaws.com --user=admin --password --ssl-ca=/path/to/ca-bundle.pem
```

### Virtual Environment Issues
```bash
# Remove and recreate virtual environment
rm -rf venv
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Server Deployment

### Why Use Virtual Environment on Servers?

**Yes, you should use venv on servers!** Benefits:
- ✅ Isolation from system packages
- ✅ No sudo/root access needed
- ✅ Clean dependency management
- ✅ Multiple apps with different Python versions
- ✅ Reproducible environments

### Option 1: Deploy with venv (Simple)

The `mysql_test.sh` script auto-creates venv on first run:

```bash
# Copy files to server
scp mysql_test.py mysql_test.sh requirements.txt user@server:/opt/mysql-benchmark/

# On server - first run creates venv automatically
cd /opt/mysql-benchmark
./mysql_test.sh --test-connection-only
```

### Option 2: Deploy with Docker (Recommended)

**Build and run:**
```bash
# Build image
docker build -t mysql-perf-test .

# Run test
docker run --rm --network host \
  -e MYSQL_HOST=localhost \
  -e MYSQL_USER=root \
  -e MYSQL_PASS=yourpassword \
  -v $(pwd)/output:/app/output \
  mysql-perf-test \
  --label "Production-Test" \
  --single-inserts 10000 \
  --yes
```

**Using docker-compose:**
```bash
# Set environment variables
export MYSQL_HOST=localhost
export MYSQL_USER=root
export MYSQL_PASS=yourpassword

# Run test
docker-compose up

# Results saved to ./output/ directory
```

### Option 3: System-wide Installation (Not Recommended)

Only if you absolutely must:
```bash
# On Ubuntu/Debian
sudo apt install python3-pip
pip3 install --user mysql-connector-python

# Run directly
python3 mysql_test.py --host localhost --user root --pass xxx
```

## Performance Tips

1. **Baseline Test**: Run with default parameters first
2. **Commit Batching**: Use `--commit-every 10` or higher for realistic results
3. **Connection Pool**: Increase `--pool-size` for high concurrency tests
4. **Network Latency**: Test both local and remote databases
5. **Multiple Runs**: Run tests 3-5 times and compare results

## License

This script is provided as-is for performance testing purposes.

## Version

2.0 - Enhanced with connection pooling, SSL support, and comprehensive testing
