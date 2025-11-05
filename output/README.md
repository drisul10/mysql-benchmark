# Test Results Output

This folder contains MySQL performance test results in JSON format.

## File Naming Convention

Files are automatically named with the pattern:
```
mysql_perf_<LABEL>_<TIMESTAMP>.json
```

Example:
```
mysql_perf_Docker-MySQL-8.0_20251105_140933.json
```

## JSON Structure

Each result file contains:
- Test metadata (label, host, database, timestamp)
- Performance metrics for each test:
  - Single INSERT operations
  - Batch INSERT operations
  - Concurrent write operations
  - UPDATE operations
  - Point read operations (SELECT by PK)
  - Range read operations (SELECT with LIMIT)

## Analyzing Results

You can compare results using:
- Simple diff: `diff result1.json result2.json`
- JSON viewers: `jq . result.json`
- Custom analysis scripts

## Cleanup

To remove old results:
```bash
# Remove results older than 7 days
find output/ -name "mysql_perf_*.json" -mtime +7 -delete

# Remove all results
rm output/mysql_perf_*.json
```
