# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in this project, please report it by creating a private security advisory on GitHub or emailing the maintainers directly. Do not create public issues for security vulnerabilities.

## Security Best Practices

### 1. Credential Management

**NEVER commit credentials to git:**
- ✅ Use environment variables (`MYSQL_PASS`)
- ✅ Use `.env` file (excluded from git)
- ✅ Use secure credential stores (AWS Secrets Manager, HashiCorp Vault)
- ❌ Never use `--pass` on production systems (visible in process list)
- ❌ Never hardcode passwords in scripts

**Example secure usage:**
```bash
# Set environment variables
export MYSQL_HOST=localhost
export MYSQL_USER=root
export MYSQL_PASS=your_secure_password

# Run without password in command
./mysql_test.sh --label "Test" --yes
```

### 2. SQL Injection Protection

This tool uses **parameterized queries** for all user inputs:
- ✅ All queries use `%s` placeholders with tuple parameters
- ✅ No string concatenation in SQL statements
- ✅ mysql-connector-python handles escaping automatically

Example safe query:
```python
cursor.execute(
    "SELECT * FROM table WHERE id = %s",  # Safe: parameterized
    (user_input,)
)
```

### 3. Network Security

**For production databases:**
- ✅ Use SSL/TLS connections (`--ssl-ca /path/to/ca.pem`)
- ✅ Use firewall rules to restrict database access
- ✅ Use dedicated database users with minimal privileges
- ✅ Use connection timeouts (`--connect-timeout 10`)

**Required MySQL privileges:**
```sql
GRANT CREATE, DROP, INSERT, UPDATE, SELECT ON perftest.* TO 'testuser'@'host';
```

### 4. Data Exposure

**This tool does NOT expose:**
- ❌ Passwords (not saved in output files)
- ❌ Sensitive data (only performance metrics)
- ❌ Query contents (only timing data)

**Output files contain:**
- ✅ Performance metrics (TPS, latency)
- ✅ Test configuration (host, database name, label)
- ✅ Timestamps

### 5. File Permissions

**Recommended file permissions:**
```bash
# Script files
chmod 755 mysql_test.py mysql_test.sh

# Environment files (if used)
chmod 600 .env

# SSL certificates
chmod 600 *.pem *.key
chmod 644 *.crt
```

### 6. Docker Security

**When using Docker:**
- ✅ Use `--network host` only when necessary
- ✅ Don't expose MySQL port unnecessarily
- ✅ Use Docker secrets for passwords (not environment variables)
- ✅ Run containers as non-root user

### 7. Production Usage

**For production testing:**
1. **Use dedicated test database** - Not production data
2. **Use read-only replicas** - For read-only tests
3. **Schedule during off-peak hours** - Minimize impact
4. **Monitor resource usage** - CPU, memory, disk I/O
5. **Set connection limits** - `--pool-size 10` or less
6. **Use SSL/TLS** - Always encrypt connections
7. **Audit test results** - Review before sharing

### 8. Known Security Considerations

**This tool:**
- Creates and drops tables (requires CREATE/DROP privileges)
- Generates load on the database (can affect performance)
- Stores results in JSON files (ensure proper file permissions)
- Uses connection pooling (configurable pool size)

**Mitigation:**
- Use `--test-connection-only` to verify setup without load
- Use dedicated test databases
- Limit concurrent connections with `--threads` and `--pool-size`
- Clean up with `--no-cleanup` to inspect data

## Security Checklist

Before running in production:

- [ ] Credentials stored securely (environment variables or secrets manager)
- [ ] SSL/TLS enabled for remote connections
- [ ] Dedicated test database created
- [ ] User has minimal required privileges
- [ ] Firewall rules configured
- [ ] Connection timeout set appropriately
- [ ] Output directory permissions secured
- [ ] Test scheduled during off-peak hours
- [ ] Resource monitoring in place
- [ ] Team informed about test schedule

## Compliance

This tool is designed for:
- ✅ Performance testing
- ✅ Capacity planning
- ✅ Benchmark comparisons
- ✅ Infrastructure validation

This tool is NOT designed for:
- ❌ Production data access
- ❌ Backup/restore operations
- ❌ Schema migrations
- ❌ Penetration testing (without authorization)

## Updates

- **v2.0** - Added SSL/TLS support, connection pooling, environment variable support
- **v1.0** - Initial release with basic security measures

## Contact

For security concerns, please create a private security advisory on GitHub.
