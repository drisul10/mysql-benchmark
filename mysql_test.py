#!/usr/bin/env python3
"""
MySQL Performance Testing Script

DESCRIPTION:
    Comprehensive MySQL performance testing tool that measures write and read
    operations under various scenarios. Tests include single inserts, batch
    inserts, concurrent writes, updates, point reads, and range queries.

FEATURES:
    - Connection testing and validation before running tests
    - Connection pooling for efficient resource management
    - Environment variable support for secure credential handling
    - SSL/TLS support for encrypted connections
    - Read and write performance tests with detailed metrics
    - Robust error handling and validation
    - Configurable commit batching for realistic testing
    - Detailed latency statistics (avg, median, P95, P99)
    - JSON output for result analysis

REQUIREMENTS:
    - Python 3.6+
    - mysql-connector-python package

    Install: pip3 install mysql-connector-python

USAGE EXAMPLES:

    1. Basic test using environment variables (RECOMMENDED):
        export MYSQL_HOST=localhost
        export MYSQL_USER=root
        export MYSQL_PASS=mypassword
        export MYSQL_DB=perftest
        python3 mysql_test.py --label "Local-MySQL"

    2. Test connection only (verify credentials and permissions):
        python3 mysql_test.py --host localhost --user root --pass mypass \
            --test-connection-only

    3. Full performance test with all parameters:
        python3 mysql_test.py --host localhost --user root --pass mypass \
            --db perftest --label "Local-MySQL" \
            --single-inserts 5000 \
            --batch-count 200 --batch-size 100 \
            --threads 20 --writes-per-thread 100 \
            --read-queries 2000 \
            --range-queries 200 --range-size 100

    4. Test with SSL/TLS (for cloud databases like RDS):
        python3 mysql_test.py --host rds.amazonaws.com --user admin --pass mypass \
            --ssl-ca /path/to/rds-ca-bundle.pem \
            --label "RDS-MySQL"

    5. Write tests only (skip read tests):
        python3 mysql_test.py --host localhost --user root --pass mypass \
            --skip-reads --single-inserts 10000 --threads 30

    6. Read tests only (skip write tests):
        python3 mysql_test.py --host localhost --user root --pass mypass \
            --skip-writes --read-queries 5000 --range-queries 500

    7. Test with realistic commit batching:
        python3 mysql_test.py --host localhost --user root --pass mypass \
            --commit-every 10 --concurrent-commit-every 50

    8. Keep test data after completion (for manual inspection):
        python3 mysql_test.py --host localhost --user root --pass mypass \
            --no-cleanup

    9. Custom connection pool size and timeout:
        python3 mysql_test.py --host localhost --user root --pass mypass \
            --pool-size 20 --connect-timeout 30

ENVIRONMENT VARIABLES:
    MYSQL_HOST      - Database host (e.g., localhost, rds.amazonaws.com)
    MYSQL_USER      - Database user (e.g., root, admin)
    MYSQL_PASS      - Database password (preferred over --pass)
    MYSQL_PASSWORD  - Alternative to MYSQL_PASS
    MYSQL_DB        - Database name (default: perftest)

OUTPUT:
    - Real-time progress output to stdout
    - JSON file with detailed results (auto-named by default)
    - Metrics include: TPS/QPS, latency (avg, median, P95, P99, min, max)

TESTS PERFORMED:
    1. Single INSERT operations (with configurable commit frequency)
    2. Batch INSERT operations (executemany)
    3. Concurrent write operations (multi-threaded)
    4. UPDATE operations
    5. Point read operations (SELECT by primary key)
    6. Range read operations (SELECT with LIMIT)

SECURITY NOTES:
    - Use environment variables for passwords (not --pass)
    - Enable SSL/TLS for production/cloud databases
    - Test user needs: CREATE, DROP, INSERT, UPDATE, SELECT permissions
    - Test creates/drops table named 'perf_test_writes'

AUTHOR: Enhanced MySQL Performance Testing Script
VERSION: 2.0
"""

import mysql.connector
from mysql.connector import pooling, Error
import time
import statistics
import json
import argparse
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List

class MySQLPerformanceTester:
    """
    MySQL Performance Testing Class

    A comprehensive testing framework for measuring MySQL database performance
    across various workload patterns including writes, reads, and concurrent operations.

    Attributes:
        host (str): Database server hostname or IP address
        user (str): Database username
        password (str): Database password
        database (str): Database name to test against
        label (str): Human-readable label for this test run
        results (dict): Dictionary storing all test results
        connect_timeout (int): Connection timeout in seconds
        ssl_config (dict): SSL/TLS configuration parameters
        pool (MySQLConnectionPool): Connection pool for efficient connection management

    Example:
        tester = MySQLPerformanceTester(
            host='localhost',
            user='root',
            password='mypass',
            database='perftest',
            label='Local-MySQL',
            pool_size=10
        )
        tester.test_connection()
        tester.setup_test_table()
        tester.test_single_inserts(1000)
    """

    def __init__(self, host, user, password, database, label="MySQL",
        pool_size=10, ssl_ca=None, ssl_cert=None, ssl_key=None,
        connect_timeout=10):
        """
        Initialize the MySQL Performance Tester

        Args:
            host (str): Database server hostname or IP
            user (str): Database username
            password (str): Database password
            database (str): Database name to use for testing
            label (str, optional): Label for this test run. Defaults to "MySQL"
            pool_size (int, optional): Connection pool size. Defaults to 10
            ssl_ca (str, optional): Path to SSL CA certificate. Defaults to None
            ssl_cert (str, optional): Path to SSL client certificate. Defaults to None
            ssl_key (str, optional): Path to SSL client key. Defaults to None
            connect_timeout (int, optional): Connection timeout in seconds. Defaults to 10

        Raises:
            mysql.connector.Error: If connection pool initialization fails
        """
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.label = label
        self.results = {}
        self.connect_timeout = connect_timeout

        # SSL configuration
        self.ssl_config = {}
        if ssl_ca:
            self.ssl_config['ca'] = ssl_ca
        if ssl_cert:
            self.ssl_config['cert'] = ssl_cert
        if ssl_key:
            self.ssl_config['key'] = ssl_key

        # Initialize connection pool for efficient connection management
        try:
            pool_config = {
                'pool_name': 'mysql_perf_pool',
                'pool_size': pool_size,
                'host': self.host,
                'user': self.user,
                'password': self.password,
                'database': self.database,
                'connect_timeout': self.connect_timeout,
                'autocommit': False  # Explicit commit control for testing
            }

            # Add SSL configuration if provided
            if self.ssl_config:
                pool_config['ssl_disabled'] = False
                for key, value in self.ssl_config.items():
                    pool_config[f'ssl_{key}'] = value

            self.pool = pooling.MySQLConnectionPool(**pool_config)
            print(f"✓ Connection pool initialized (size: {pool_size})")
        except Error as e:
            print(f"✗ Failed to create connection pool: {e}")
            raise

    def get_connection(self):
        """
        Get a connection from the connection pool

        Returns:
            mysql.connector.connection.MySQLConnection: Database connection from pool

        Raises:
            mysql.connector.Error: If unable to get connection from pool
        """
        try:
            return self.pool.get_connection()
        except Error as e:
            print(f"✗ Failed to get connection from pool: {e}")
            raise

    def test_connection(self) -> bool:
        """
        Test database connectivity and validate connection parameters

        Performs a basic connectivity check by executing a test query and
        retrieving server information. Also checks SSL/TLS status if configured.

        Returns:
            bool: True if connection successful, False otherwise

        Note:
            This method should be called before running any performance tests
            to ensure the database is accessible and credentials are correct.
        """
        print(f"\n{'='*60}")
        print(f"Testing Connection to {self.label}...")
        print(f"{'='*60}")
        print(f"Host: {self.host}")
        print(f"User: {self.user}")
        print(f"Database: {self.database}")
        print(f"SSL: {'Enabled' if self.ssl_config else 'Disabled'}")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Test query to verify connection and get server info
            cursor.execute("SELECT VERSION(), DATABASE(), USER()")
            version, db, user = cursor.fetchone()

            print(f"\n✓ Connection successful!")
            print(f"  MySQL Version: {version}")
            print(f"  Database: {db}")
            print(f"  User: {user}")

            # Check SSL status if SSL is configured
            cursor.execute("SHOW STATUS LIKE 'Ssl_cipher'")
            ssl_status = cursor.fetchone()
            if ssl_status and ssl_status[1]:
                print(f"  SSL Cipher: {ssl_status[1]}")

            cursor.close()
            conn.close()
            return True

        except Error as e:
            print(f"\n✗ Connection failed: {e}")
            return False

    def validate_permissions(self) -> bool:
        """
        Validate that the database user has required permissions

        Tests that the user has CREATE, DROP, INSERT, and UPDATE permissions
        needed to run the performance tests. Creates and drops a temporary
        test table to verify permissions.

        Returns:
            bool: True if all required permissions are present, False otherwise

        Note:
            This validation helps prevent test failures due to insufficient
            privileges. The test creates a temporary table 'permission_test'
            which is automatically dropped after validation.
        """
        print(f"\n{'='*60}")
        print(f"Validating Permissions...")
        print(f"{'='*60}")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check CREATE permission
            try:
                cursor.execute("CREATE TABLE permission_test (id INT)")
                cursor.execute("DROP TABLE permission_test")
                print("✓ CREATE/DROP permissions: OK")
            except Error as e:
                print(f"✗ CREATE/DROP permissions: FAILED ({e})")
                return False

            # Check INSERT permission
            try:
                cursor.execute("CREATE TABLE permission_test (id INT)")
                cursor.execute("INSERT INTO permission_test VALUES (1)")
                cursor.execute("DROP TABLE permission_test")
                print("✓ INSERT permissions: OK")
            except Error as e:
                print(f"✗ INSERT permissions: FAILED ({e})")
                cursor.execute("DROP TABLE IF EXISTS permission_test")
                return False

            conn.commit()
            cursor.close()
            conn.close()
            return True

        except Error as e:
            print(f"✗ Permission validation failed: {e}")
            return False

    def setup_test_table(self):
        """
        Create the test table for performance testing

        Drops existing 'perf_test_writes' table if it exists and creates
        a new one with the following schema:
            - id: Auto-increment primary key
            - test_data: VARCHAR(255) for test data
            - numeric_value: INT for indexed queries
            - timestamp_value: TIMESTAMP with default CURRENT_TIMESTAMP
            - Indexes on numeric_value and timestamp_value

        The table uses InnoDB engine for transaction support.

        Raises:
            mysql.connector.Error: If table creation fails
        """
        print(f"\n{'='*60}")
        print(f"Setting up test table on {self.label}...")
        print(f"{'='*60}")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Drop if exists to ensure clean state
            cursor.execute("DROP TABLE IF EXISTS perf_test_writes")

            # Create test table with indexes for performance testing
            cursor.execute("""
                CREATE TABLE perf_test_writes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    test_data VARCHAR(255),
                    numeric_value INT,
                    timestamp_value TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_numeric (numeric_value),
                    INDEX idx_timestamp (timestamp_value)
                ) ENGINE=InnoDB
            """)

            conn.commit()
            cursor.close()
            conn.close()
            print(f"✓ Test table created successfully")
        except Error as e:
            print(f"✗ Failed to create test table: {e}")
            raise

    def calculate_percentile(self, data: List[float], percentile: int) -> float:
        """
        Calculate percentile with robust handling of edge cases

        Uses Python's statistics.quantiles() for large datasets and falls back
        to manual calculation for small datasets or when quantiles fail.

        Args:
            data (List[float]): List of numeric values (typically latencies)
            percentile (int): Percentile to calculate (e.g., 95, 99)

        Returns:
            float: The calculated percentile value

        Note:
            - Returns 0.0 for empty datasets
            - Returns the single value for single-element datasets
            - Uses quantiles() for datasets with 100+ elements
            - Falls back to manual calculation for smaller datasets
        """
        if not data:
            return 0.0

        if len(data) == 1:
            return data[0]

        # Use quantiles for datasets with enough points (more accurate)
        if len(data) >= 100 and percentile in [95, 99]:
            try:
                if percentile == 95:
                    return statistics.quantiles(data, n=20)[18]
                elif percentile == 99:
                    return statistics.quantiles(data, n=100)[98]
            except statistics.StatisticsError:
                pass

        # Fallback to manual percentile calculation for small datasets
        sorted_data = sorted(data)
        index = int(len(sorted_data) * (percentile / 100.0))
        return sorted_data[min(index, len(sorted_data) - 1)]

    def test_single_inserts(self, num_inserts=1000, commit_every=1):
        """
        Test individual INSERT statement performance

        Executes individual INSERT statements and measures latency for each
        operation. Supports configurable commit frequency to simulate different
        transaction patterns.

        Args:
            num_inserts (int, optional): Number of INSERT operations. Defaults to 1000
            commit_every (int, optional): Commit frequency (1 = commit after each insert,
                                         10 = commit after every 10 inserts). Defaults to 1

        Metrics Collected:
            - Total time (seconds)
            - Throughput (TPS - transactions per second)
            - Average latency (milliseconds)
            - Median latency
            - P95 latency (95th percentile)
            - P99 latency (99th percentile)
            - Min/Max latency

        Results stored in: self.results['single_inserts']

        Raises:
            mysql.connector.Error: If INSERT operations fail
        """
        print(f"\n{'='*60}")
        print(f"TEST 1: Single INSERT Operations")
        print(f"{'='*60}")
        print(f"Testing {num_inserts} individual INSERT statements...")
        print(f"Commit strategy: Every {commit_every} insert(s)")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            latencies = []
            start_time = time.time()

            # Show progress every 10%
            progress_step = max(1, num_inserts // 10)

            for i in range(num_inserts):
                insert_start = time.time()

                cursor.execute(
                    "INSERT INTO perf_test_writes (test_data, numeric_value) VALUES (%s, %s)",
                    (f"test_data_{i}", i)
                )

                # Commit based on commit_every parameter
                if (i + 1) % commit_every == 0:
                    conn.commit()

                insert_end = time.time()
                latencies.append((insert_end - insert_start) * 1000)  # Convert to ms

                if (i + 1) % progress_step == 0:
                    print(f"  Progress: {i + 1}/{num_inserts} ({((i+1)/num_inserts*100):.0f}%)")

            # Final commit if needed
            conn.commit()

            end_time = time.time()
            total_time = end_time - start_time

            cursor.close()
            conn.close()

            self.results['single_inserts'] = {
                'total_time_sec': round(total_time, 2),
                'records': num_inserts,
                'tps': round(num_inserts / total_time, 2),
                'avg_latency_ms': round(statistics.mean(latencies), 2),
                'median_latency_ms': round(statistics.median(latencies), 2),
                'p95_latency_ms': round(self.calculate_percentile(latencies, 95), 2),
                'p99_latency_ms': round(self.calculate_percentile(latencies, 99), 2),
                'min_latency_ms': round(min(latencies), 2),
                'max_latency_ms': round(max(latencies), 2),
                'commit_every': commit_every
            }

            print(f"\n📊 RESULTS:")
            print(f"  ✓ Total Time: {self.results['single_inserts']['total_time_sec']} seconds")
            print(f"  ✓ Throughput: {self.results['single_inserts']['tps']} TPS (writes/sec)")
            print(f"  ✓ Avg Latency: {self.results['single_inserts']['avg_latency_ms']} ms")
            print(f"  ✓ Median Latency: {self.results['single_inserts']['median_latency_ms']} ms")
            print(f"  ✓ P95 Latency: {self.results['single_inserts']['p95_latency_ms']} ms")
            print(f"  ✓ P99 Latency: {self.results['single_inserts']['p99_latency_ms']} ms")
            print(f"  ✓ Min/Max: {self.results['single_inserts']['min_latency_ms']}/{self.results['single_inserts']['max_latency_ms']} ms")

        except Error as e:
            print(f"✗ Single insert test failed: {e}")
            raise

    def test_batch_inserts(self, num_batches=100, batch_size=100):
        """
        Test batch INSERT performance using executemany()

        Executes batch INSERT operations using cursor.executemany() which is
        more efficient than individual INSERTs. Each batch is committed as
        a single transaction.

        Args:
            num_batches (int, optional): Number of batches to execute. Defaults to 100
            batch_size (int, optional): Number of records per batch. Defaults to 100

        Metrics Collected:
            - Total time (seconds)
            - Total records inserted
            - Throughput (TPS - records per second)
            - Average batch latency (milliseconds)
            - P95 batch latency

        Results stored in: self.results['batch_inserts']

        Raises:
            mysql.connector.Error: If batch INSERT operations fail

        Note:
            Total records inserted = num_batches * batch_size
        """
        print(f"\n{'='*60}")
        print(f"TEST 2: Batch INSERT Operations")
        print(f"{'='*60}")
        print(f"Testing {num_batches} batches x {batch_size} records per batch...")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            batch_latencies = []
            start_time = time.time()
            total_records = 0

            progress_step = max(1, num_batches // 10)

            for batch_num in range(num_batches):
                batch_start = time.time()

                # Prepare batch data
                values = [(f"batch_data_{batch_num}_{i}", batch_num * batch_size + i)
                         for i in range(batch_size)]

                # Execute batch insert
                cursor.executemany(
                    "INSERT INTO perf_test_writes (test_data, numeric_value) VALUES (%s, %s)",
                    values
                )
                conn.commit()

                batch_end = time.time()
                batch_latencies.append((batch_end - batch_start) * 1000)
                total_records += batch_size

                if (batch_num + 1) % progress_step == 0:
                    print(f"  Progress: {batch_num + 1}/{num_batches} batches ({((batch_num+1)/num_batches*100):.0f}%)")

            end_time = time.time()
            total_time = end_time - start_time

            cursor.close()
            conn.close()

            self.results['batch_inserts'] = {
                'total_time_sec': round(total_time, 2),
                'records': total_records,
                'batches': num_batches,
                'batch_size': batch_size,
                'tps': round(total_records / total_time, 2),
                'avg_batch_latency_ms': round(statistics.mean(batch_latencies), 2),
                'p95_batch_latency_ms': round(self.calculate_percentile(batch_latencies, 95), 2)
            }

            print(f"\n📊 RESULTS:")
            print(f"  ✓ Total Time: {self.results['batch_inserts']['total_time_sec']} seconds")
            print(f"  ✓ Total Records: {self.results['batch_inserts']['records']}")
            print(f"  ✓ Throughput: {self.results['batch_inserts']['tps']} TPS (records/sec)")
            print(f"  ✓ Avg Batch Time: {self.results['batch_inserts']['avg_batch_latency_ms']} ms")
            print(f"  ✓ P95 Batch Time: {self.results['batch_inserts']['p95_batch_latency_ms']} ms")

        except Error as e:
            print(f"✗ Batch insert test failed: {e}")
            raise

    def concurrent_writer(self, thread_id, num_writes, commit_every=10):
        """
        Worker function for concurrent write testing

        Executed by multiple threads in parallel to test concurrent write
        performance. Each thread gets its own connection from the pool.

        Args:
            thread_id (int): Unique identifier for this thread
            num_writes (int): Number of writes this thread should perform
            commit_every (int, optional): Commit frequency. Defaults to 10

        Returns:
            List[float]: List of latencies (in milliseconds) for each write

        Note:
            Returns empty list if thread encounters an error
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            latencies = []

            for i in range(num_writes):
                start = time.time()
                cursor.execute(
                    "INSERT INTO perf_test_writes (test_data, numeric_value) VALUES (%s, %s)",
                    (f"thread_{thread_id}_data_{i}", thread_id * 10000 + i)
                )

                if (i + 1) % commit_every == 0:
                    conn.commit()

                end = time.time()
                latencies.append((end - start) * 1000)

            # Final commit
            conn.commit()

            cursor.close()
            conn.close()

            return latencies
        except Error as e:
            print(f"✗ Thread {thread_id} failed: {e}")
            return []

    def test_concurrent_writes(self, num_threads=10, writes_per_thread=100, commit_every=10):
        """
        Test concurrent write performance with multiple threads

        Spawns multiple threads that simultaneously write to the database to
        measure performance under concurrent load. Each thread uses its own
        connection from the pool.

        Args:
            num_threads (int, optional): Number of concurrent threads. Defaults to 10
            writes_per_thread (int, optional): Writes per thread. Defaults to 100
            commit_every (int, optional): Commit frequency per thread. Defaults to 10

        Metrics Collected:
            - Total time (seconds)
            - Total writes (num_threads * writes_per_thread)
            - Throughput (TPS - total writes per second)
            - Average latency across all threads
            - Median latency
            - P95 and P99 latency
            - Max latency

        Results stored in: self.results['concurrent_writes']

        Raises:
            mysql.connector.Error: If concurrent write operations fail

        Note:
            This test measures how well the database handles concurrent write
            load, which is common in production environments.
        """
        print(f"\n{'='*60}")
        print(f"TEST 3: Concurrent Write Operations")
        print(f"{'='*60}")
        print(f"Testing {num_threads} threads x {writes_per_thread} writes per thread...")
        print(f"Commit strategy: Every {commit_every} insert(s) per thread")

        try:
            start_time = time.time()
            all_latencies = []

            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [
                    executor.submit(self.concurrent_writer, thread_id, writes_per_thread, commit_every)
                    for thread_id in range(num_threads)
                ]

                completed = 0
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        all_latencies.extend(result)
                    completed += 1
                    print(f"  Thread {completed}/{num_threads} completed")

            end_time = time.time()
            total_time = end_time - start_time
            total_writes = num_threads * writes_per_thread

            if not all_latencies:
                print("✗ No successful writes in concurrent test")
                return

            self.results['concurrent_writes'] = {
                'total_time_sec': round(total_time, 2),
                'records': total_writes,
                'threads': num_threads,
                'writes_per_thread': writes_per_thread,
                'tps': round(total_writes / total_time, 2),
                'avg_latency_ms': round(statistics.mean(all_latencies), 2),
                'median_latency_ms': round(statistics.median(all_latencies), 2),
                'p95_latency_ms': round(self.calculate_percentile(all_latencies, 95), 2),
                'p99_latency_ms': round(self.calculate_percentile(all_latencies, 99), 2),
                'max_latency_ms': round(max(all_latencies), 2),
                'commit_every': commit_every
            }

            print(f"\n📊 RESULTS:")
            print(f"  ✓ Total Time: {self.results['concurrent_writes']['total_time_sec']} seconds")
            print(f"  ✓ Total Writes: {self.results['concurrent_writes']['records']}")
            print(f"  ✓ Throughput: {self.results['concurrent_writes']['tps']} TPS")
            print(f"  ✓ Avg Latency: {self.results['concurrent_writes']['avg_latency_ms']} ms")
            print(f"  ✓ Median Latency: {self.results['concurrent_writes']['median_latency_ms']} ms")
            print(f"  ✓ P95 Latency: {self.results['concurrent_writes']['p95_latency_ms']} ms")
            print(f"  ✓ P99 Latency: {self.results['concurrent_writes']['p99_latency_ms']} ms")
            print(f"  ✓ Max Latency: {self.results['concurrent_writes']['max_latency_ms']} ms")

        except Error as e:
            print(f"✗ Concurrent write test failed: {e}")
            raise

    def test_updates(self, num_updates=1000):
        """
        Test UPDATE statement performance

        Executes individual UPDATE statements on existing records and measures
        latency for each operation. Updates records by numeric_value (indexed).

        Args:
            num_updates (int, optional): Number of UPDATE operations. Defaults to 1000

        Metrics Collected:
            - Total time (seconds)
            - Throughput (TPS - updates per second)
            - Average latency
            - P95 latency

        Results stored in: self.results['updates']

        Raises:
            mysql.connector.Error: If UPDATE operations fail

        Note:
            Requires data to exist in the table (from previous INSERT tests)
        """
        print(f"\n{'='*60}")
        print(f"TEST 4: UPDATE Operations")
        print(f"{'='*60}")
        print(f"Testing {num_updates} UPDATE statements...")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            latencies = []
            start_time = time.time()

            progress_step = max(1, num_updates // 10)

            for i in range(num_updates):
                update_start = time.time()

                cursor.execute(
                    "UPDATE perf_test_writes SET test_data = %s WHERE numeric_value = %s",
                    (f"updated_data_{i}", i)
                )
                conn.commit()

                update_end = time.time()
                latencies.append((update_end - update_start) * 1000)

                if (i + 1) % progress_step == 0:
                    print(f"  Progress: {i + 1}/{num_updates} ({((i+1)/num_updates*100):.0f}%)")

            end_time = time.time()
            total_time = end_time - start_time

            cursor.close()
            conn.close()

            self.results['updates'] = {
                'total_time_sec': round(total_time, 2),
                'records': num_updates,
                'tps': round(num_updates / total_time, 2),
                'avg_latency_ms': round(statistics.mean(latencies), 2),
                'p95_latency_ms': round(self.calculate_percentile(latencies, 95), 2)
            }

            print(f"\n📊 RESULTS:")
            print(f"  ✓ Total Time: {self.results['updates']['total_time_sec']} seconds")
            print(f"  ✓ Throughput: {self.results['updates']['tps']} TPS")
            print(f"  ✓ Avg Latency: {self.results['updates']['avg_latency_ms']} ms")
            print(f"  ✓ P95 Latency: {self.results['updates']['p95_latency_ms']} ms")

        except Error as e:
            print(f"✗ Update test failed: {e}")
            raise

    def test_point_reads(self, num_reads=1000):
        """
        Test point read performance (SELECT by primary key)

        Executes SELECT queries using the primary key index, which represents
        the fastest possible read operation. Measures query latency.

        Args:
            num_reads (int, optional): Number of point read queries. Defaults to 1000

        Metrics Collected:
            - Total time (seconds)
            - Throughput (QPS - queries per second)
            - Average latency
            - Median latency
            - P95 and P99 latency
            - Min/Max latency

        Results stored in: self.results['point_reads']

        Raises:
            mysql.connector.Error: If SELECT operations fail

        Note:
            Requires data to exist in the table (from previous INSERT tests)
            This test measures optimal read performance using indexed lookups
        """
        print(f"\n{'='*60}")
        print(f"TEST 5: Point Read Operations (SELECT by PK)")
        print(f"{'='*60}")
        print(f"Testing {num_reads} point read queries...")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get max ID to know the range
            cursor.execute("SELECT MIN(id), MAX(id) FROM perf_test_writes")
            min_id, max_id = cursor.fetchone()

            if min_id is None or max_id is None:
                print("✗ No data available for read test")
                return

            print(f"  ID range: {min_id} to {max_id}")

            latencies = []
            start_time = time.time()

            progress_step = max(1, num_reads // 10)

            for i in range(num_reads):
                # Read a random ID within range
                read_id = min_id + (i % (max_id - min_id + 1))

                read_start = time.time()
                cursor.execute(
                    "SELECT * FROM perf_test_writes WHERE id = %s",
                    (read_id,)
                )
                result = cursor.fetchone()
                read_end = time.time()

                latencies.append((read_end - read_start) * 1000)

                if (i + 1) % progress_step == 0:
                    print(f"  Progress: {i + 1}/{num_reads} ({((i+1)/num_reads*100):.0f}%)")

            end_time = time.time()
            total_time = end_time - start_time

            cursor.close()
            conn.close()

            self.results['point_reads'] = {
                'total_time_sec': round(total_time, 2),
                'records': num_reads,
                'qps': round(num_reads / total_time, 2),
                'avg_latency_ms': round(statistics.mean(latencies), 2),
                'median_latency_ms': round(statistics.median(latencies), 2),
                'p95_latency_ms': round(self.calculate_percentile(latencies, 95), 2),
                'p99_latency_ms': round(self.calculate_percentile(latencies, 99), 2),
                'min_latency_ms': round(min(latencies), 2),
                'max_latency_ms': round(max(latencies), 2)
            }

            print(f"\n📊 RESULTS:")
            print(f"  ✓ Total Time: {self.results['point_reads']['total_time_sec']} seconds")
            print(f"  ✓ Throughput: {self.results['point_reads']['qps']} QPS (queries/sec)")
            print(f"  ✓ Avg Latency: {self.results['point_reads']['avg_latency_ms']} ms")
            print(f"  ✓ Median Latency: {self.results['point_reads']['median_latency_ms']} ms")
            print(f"  ✓ P95 Latency: {self.results['point_reads']['p95_latency_ms']} ms")
            print(f"  ✓ P99 Latency: {self.results['point_reads']['p99_latency_ms']} ms")

        except Error as e:
            print(f"✗ Point read test failed: {e}")
            raise

    def test_range_reads(self, num_queries=100, range_size=100):
        """
        Test range read performance (SELECT with LIMIT)

        Executes SELECT queries that return multiple rows using LIMIT clause.
        This simulates typical application queries that fetch result sets.

        Args:
            num_queries (int, optional): Number of range queries. Defaults to 100
            range_size (int, optional): Number of rows per query (LIMIT). Defaults to 100

        Metrics Collected:
            - Total time (seconds)
            - Throughput (QPS - queries per second)
            - Average latency
            - P95 latency

        Results stored in: self.results['range_reads']

        Raises:
            mysql.connector.Error: If SELECT operations fail

        Note:
            Requires data to exist in the table (from previous INSERT tests)
            This test measures performance of queries returning multiple rows
        """
        print(f"\n{'='*60}")
        print(f"TEST 6: Range Read Operations")
        print(f"{'='*60}")
        print(f"Testing {num_queries} range queries (LIMIT {range_size})...")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            latencies = []
            start_time = time.time()

            progress_step = max(1, num_queries // 10)

            for i in range(num_queries):
                read_start = time.time()

                cursor.execute(
                    "SELECT * FROM perf_test_writes WHERE numeric_value >= %s LIMIT %s",
                    (i * 10, range_size)
                )
                results = cursor.fetchall()

                read_end = time.time()
                latencies.append((read_end - read_start) * 1000)

                if (i + 1) % progress_step == 0:
                    print(f"  Progress: {i + 1}/{num_queries} ({((i+1)/num_queries*100):.0f}%)")

            end_time = time.time()
            total_time = end_time - start_time

            cursor.close()
            conn.close()

            self.results['range_reads'] = {
                'total_time_sec': round(total_time, 2),
                'queries': num_queries,
                'range_size': range_size,
                'qps': round(num_queries / total_time, 2),
                'avg_latency_ms': round(statistics.mean(latencies), 2),
                'p95_latency_ms': round(self.calculate_percentile(latencies, 95), 2)
            }

            print(f"\n📊 RESULTS:")
            print(f"  ✓ Total Time: {self.results['range_reads']['total_time_sec']} seconds")
            print(f"  ✓ Throughput: {self.results['range_reads']['qps']} QPS")
            print(f"  ✓ Avg Latency: {self.results['range_reads']['avg_latency_ms']} ms")
            print(f"  ✓ P95 Latency: {self.results['range_reads']['p95_latency_ms']} ms")

        except Error as e:
            print(f"✗ Range read test failed: {e}")
            raise

    def cleanup(self):
        """
        Clean up test table and resources

        Drops the 'perf_test_writes' table created during testing.
        Called automatically after tests complete unless --no-cleanup is specified.

        Note:
            This method does not raise exceptions on failure to allow
            graceful cleanup even if the connection is in an error state.
        """
        print(f"\n{'='*60}")
        print(f"Cleaning up...")
        print(f"{'='*60}")
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS perf_test_writes")
            conn.commit()
            cursor.close()
            conn.close()
            print(f"✓ Test table dropped")
        except Error as e:
            print(f"✗ Cleanup failed: {e}")

    def save_results(self, filename):
        """
        Save test results to JSON file

        Exports all test results along with metadata (host, label, timestamp)
        to a JSON file for later analysis.

        Args:
            filename (str): Path to output JSON file

        Returns:
            str: The filename where results were saved

        Note:
            JSON structure includes:
            - label: Test run label
            - host: Database host
            - database: Database name
            - timestamp: ISO format timestamp
            - results: Dictionary of all test results
        """
        results_with_metadata = {
            'label': self.label,
            'host': self.host,
            'database': self.database,
            'timestamp': datetime.now().isoformat(),
            'results': self.results
        }

        with open(filename, 'w') as f:
            json.dump(results_with_metadata, f, indent=2)

        print(f"\n✓ Results saved to: {filename}")
        return filename

def main():
    """
    Main function - Command line interface for MySQL performance testing

    Parses command line arguments, initializes the tester, validates connectivity
    and permissions, runs the selected tests, and saves results to JSON.

    The function handles:
    - Argument parsing and validation
    - Environment variable fallback for credentials
    - Connection and permission validation
    - Test execution (write and/or read tests)
    - Result output and cleanup

    Exit codes:
        0: Success
        1: Error (connection failed, permission denied, etc.)

    See module docstring for usage examples.
    """
    parser = argparse.ArgumentParser(
        description='MySQL Performance Testing - Enhanced Version',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using command line arguments
  python3 mysql_test.py --host localhost --user root --pass mypass --label "Local-MySQL"

  # Using environment variables
  export MYSQL_HOST=localhost
  export MYSQL_USER=root
  export MYSQL_PASS=mypass
  python3 mysql_test.py --label "Local-MySQL"

  # Full test with SSL
  python3 mysql_test.py --host rds.amazonaws.com --user admin --pass mypass \\
      --ssl-ca /path/to/ca.pem --label "RDS-MySQL" \\
      --single-inserts 5000 --threads 20

  # Test connection only
  python3 mysql_test.py --host localhost --user root --pass mypass --test-connection-only
        """
    )

    # Connection parameters (can use env variables)
    parser.add_argument('--host',
                       default=os.getenv('MYSQL_HOST'),
                       help='Database host (env: MYSQL_HOST)')
    parser.add_argument('--user',
                       default=os.getenv('MYSQL_USER'),
                       help='Database user (env: MYSQL_USER)')
    parser.add_argument('--pass',
                       dest='password',
                       default=os.getenv('MYSQL_PASS') or os.getenv('MYSQL_PASSWORD'),
                       help='Database password (env: MYSQL_PASS or MYSQL_PASSWORD)')
    parser.add_argument('--db',
                       default=os.getenv('MYSQL_DB', 'perftest'),
                       help='Database name (env: MYSQL_DB, default: perftest)')
    parser.add_argument('--label',
                       default='MySQL',
                       help='Label for this database (e.g., "EC2-MySQL", "RDS-MySQL")')

    # SSL options
    parser.add_argument('--ssl-ca', help='Path to SSL CA certificate')
    parser.add_argument('--ssl-cert', help='Path to SSL client certificate')
    parser.add_argument('--ssl-key', help='Path to SSL client key')

    # Connection pool settings
    parser.add_argument('--pool-size', type=int, default=10,
                       help='Connection pool size (default: 10)')
    parser.add_argument('--connect-timeout', type=int, default=10,
                       help='Connection timeout in seconds (default: 10)')

    # Test parameters
    parser.add_argument('--single-inserts', type=int, default=1000,
                       help='Number of single inserts (default: 1000)')
    parser.add_argument('--commit-every', type=int, default=1,
                       help='Commit every N inserts in single insert test (default: 1)')
    parser.add_argument('--batch-count', type=int, default=100,
                       help='Number of batches (default: 100)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Records per batch (default: 100)')
    parser.add_argument('--threads', type=int, default=10,
                       help='Concurrent threads (default: 10)')
    parser.add_argument('--writes-per-thread', type=int, default=100,
                       help='Writes per thread (default: 100)')
    parser.add_argument('--concurrent-commit-every', type=int, default=10,
                       help='Commit every N inserts in concurrent test (default: 10)')
    parser.add_argument('--read-queries', type=int, default=1000,
                       help='Number of read queries (default: 1000)')
    parser.add_argument('--range-queries', type=int, default=100,
                       help='Number of range queries (default: 100)')
    parser.add_argument('--range-size', type=int, default=100,
                       help='Range query size (default: 100)')

    # Control options
    parser.add_argument('--skip-writes', action='store_true',
                       help='Skip write tests')
    parser.add_argument('--skip-reads', action='store_true',
                       help='Skip read tests')
    parser.add_argument('--test-connection-only', action='store_true',
                       help='Only test connection and exit')
    parser.add_argument('--output', help='Output JSON filename (default: auto-generated)')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Do not drop test table after tests')
    parser.add_argument('--yes', '-y', action='store_true',
                       help='Skip confirmation prompt and start tests immediately')

    args = parser.parse_args()

    # Validate required parameters
    if not args.host or not args.user or not args.password:
        print("Error: --host, --user, and --pass are required (or set via environment variables)")
        print("\nSet environment variables:")
        print("  export MYSQL_HOST=your_host")
        print("  export MYSQL_USER=your_user")
        print("  export MYSQL_PASS=your_password")
        sys.exit(1)

    print("="*60)
    print("MySQL Performance Testing Suite (Enhanced)")
    print("="*60)
    print(f"Database: {args.label}")
    print(f"Host: {args.host}")
    print(f"Database: {args.db}")
    print(f"Connection Pool Size: {args.pool_size}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Create tester instance
    try:
        tester = MySQLPerformanceTester(
            args.host,
            args.user,
            args.password,
            args.db,
            args.label,
            pool_size=args.pool_size,
            ssl_ca=args.ssl_ca,
            ssl_cert=args.ssl_cert,
            ssl_key=args.ssl_key,
            connect_timeout=args.connect_timeout
        )
    except Exception as e:
        print(f"\n✗ Failed to initialize tester: {e}")
        sys.exit(1)

    # Test connection
    if not tester.test_connection():
        print("\n✗ Connection test failed. Exiting.")
        sys.exit(1)

    if args.test_connection_only:
        print("\n✓ Connection test successful. Exiting (--test-connection-only specified)")
        sys.exit(0)

    # Validate permissions
    if not tester.validate_permissions():
        print("\n✗ Permission validation failed. Exiting.")
        sys.exit(1)

    print("\nTest Configuration:")
    if not args.skip_writes:
        print(f"  - Single Inserts: {args.single_inserts} (commit every {args.commit_every})")
        print(f"  - Batch Inserts: {args.batch_count} x {args.batch_size}")
        print(f"  - Concurrent: {args.threads} threads x {args.writes_per_thread} writes (commit every {args.concurrent_commit_every})")
        print(f"  - Updates: {args.single_inserts}")
    if not args.skip_reads:
        print(f"  - Point Reads: {args.read_queries}")
        print(f"  - Range Reads: {args.range_queries} x {args.range_size} records")

    if not args.yes:
        input("\nPress Enter to start testing (or Ctrl+C to cancel)...")
    else:
        print("\nStarting tests automatically (--yes flag specified)...")

    try:
        # Setup
        tester.setup_test_table()

        # Write tests
        if not args.skip_writes:
            tester.test_single_inserts(args.single_inserts, args.commit_every)
            tester.test_batch_inserts(args.batch_count, args.batch_size)
            tester.test_concurrent_writes(args.threads, args.writes_per_thread, args.concurrent_commit_every)
            tester.test_updates(args.single_inserts)

        # Read tests
        if not args.skip_reads:
            tester.test_point_reads(args.read_queries)
            tester.test_range_reads(args.range_queries, args.range_size)

        # Save results
        # Create output directory if it doesn't exist
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

        if args.output:
            output_file = args.output
        else:
            safe_label = args.label.replace(' ', '_').replace('/', '_')
            output_file = os.path.join(output_dir, f"mysql_perf_{safe_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        tester.save_results(output_file)

        # Print summary
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY - {args.label}")
        print(f"{'='*60}")

        if 'single_inserts' in tester.results:
            print(f"\nSingle Inserts:")
            print(f"  TPS: {tester.results['single_inserts']['tps']}")
            print(f"  Avg Latency: {tester.results['single_inserts']['avg_latency_ms']} ms")
            print(f"  P95 Latency: {tester.results['single_inserts']['p95_latency_ms']} ms")

        if 'batch_inserts' in tester.results:
            print(f"\nBatch Inserts:")
            print(f"  TPS: {tester.results['batch_inserts']['tps']}")
            print(f"  Avg Batch Time: {tester.results['batch_inserts']['avg_batch_latency_ms']} ms")

        if 'concurrent_writes' in tester.results:
            print(f"\nConcurrent Writes:")
            print(f"  TPS: {tester.results['concurrent_writes']['tps']}")
            print(f"  Avg Latency: {tester.results['concurrent_writes']['avg_latency_ms']} ms")
            print(f"  P95 Latency: {tester.results['concurrent_writes']['p95_latency_ms']} ms")

        if 'updates' in tester.results:
            print(f"\nUpdates:")
            print(f"  TPS: {tester.results['updates']['tps']}")
            print(f"  Avg Latency: {tester.results['updates']['avg_latency_ms']} ms")

        if 'point_reads' in tester.results:
            print(f"\nPoint Reads:")
            print(f"  QPS: {tester.results['point_reads']['qps']}")
            print(f"  Avg Latency: {tester.results['point_reads']['avg_latency_ms']} ms")
            print(f"  P95 Latency: {tester.results['point_reads']['p95_latency_ms']} ms")

        if 'range_reads' in tester.results:
            print(f"\nRange Reads:")
            print(f"  QPS: {tester.results['range_reads']['qps']}")
            print(f"  Avg Latency: {tester.results['range_reads']['avg_latency_ms']} ms")

    except KeyboardInterrupt:
        print("\n\n✗ Testing interrupted by user")
    except Exception as e:
        print(f"\n✗ Testing failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if not args.no_cleanup:
            tester.cleanup()
        else:
            print("\n✓ Test table preserved (--no-cleanup specified)")

    print(f"\n{'='*60}")
    print(f"Testing Complete!")
    if not args.test_connection_only:
        print(f"Results saved to: {output_file}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
