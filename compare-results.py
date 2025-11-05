#!/usr/bin/env python3
"""
MySQL Performance Test Results Comparison Tool

DESCRIPTION:
    Compare and analyze performance test results from two MySQL databases.
    Generates detailed comparison reports showing throughput, latency differences,
    and performance improvements across all test types.

FEATURES:
    - Side-by-side performance comparison
    - Percentage difference calculations
    - Visual indicators for winners
    - Support for all test types (writes and reads)
    - Multiple output formats (table, markdown, JSON)
    - Export comparison results
    - Statistical significance indicators

REQUIREMENTS:
    - Python 3.6+
    - JSON result files from mysql_test.py

USAGE EXAMPLES:

    1. Basic comparison (table format):
        python3 compare-results.py output/result1.json output/result2.json

    2. Export comparison to markdown (auto-saves to output/ folder):
        python3 compare-results.py result1.json result2.json --format markdown --output comparison.md

    3. Export to JSON for further analysis (auto-saves to output/ folder):
        python3 compare-results.py result1.json result2.json --format json --output comparison.json

    4. Compare with custom labels:
        python3 compare-results.py ec2.json rds.json --label1 "EC2-MySQL" --label2 "RDS-MySQL"

    5. Show only significant differences (>10%):
        python3 compare-results.py result1.json result2.json --threshold 10

OUTPUT FORMATS:
    - table: Console-friendly table format (default)
    - markdown: GitHub-flavored markdown tables
    - json: Machine-readable JSON format

INTERPRETATION:
    - Difference % is always positive (absolute difference)
    - Winner column shows which database performed better
    - Higher TPS/QPS is better (more throughput)
    - Lower Latency (ms) is better (faster response)
    - Winner shown only for significant differences (>10% by default)

AUTHOR: Enhanced MySQL Performance Testing Script
VERSION: 2.0
"""

import json
import argparse
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class ResultComparator:
    """
    MySQL Performance Result Comparator

    Compares two MySQL performance test results and generates detailed
    comparison reports with multiple output formats.

    Attributes:
        result1 (dict): First test result
        result2 (dict): Second test result
        label1 (str): Label for first result
        label2 (str): Label for second result
        threshold (float): Significance threshold percentage

    Example:
        comparator = ResultComparator(result1, result2)
        comparator.compare(format='table')
    """

    def __init__(self, result1: Dict, result2: Dict, label1: Optional[str] = None,
                 label2: Optional[str] = None, threshold: float = 10.0):
        """
        Initialize the comparator

        Args:
            result1: First test result dictionary
            result2: Second test result dictionary
            label1: Optional custom label for first result
            label2: Optional custom label for second result
            threshold: Significance threshold in percentage (default: 10.0)
        """
        self.result1 = result1
        self.result2 = result2
        self.label1 = label1 or result1.get('label', 'Database 1')
        self.label2 = label2 or result2.get('label', 'Database 2')
        self.threshold = threshold

        # Test definitions
        self.test_definitions = {
            'single_inserts': {
                'name': 'SINGLE INSERT OPERATIONS',
                'metrics': ['tps', 'avg_latency_ms', 'median_latency_ms', 'p95_latency_ms', 'p99_latency_ms']
            },
            'batch_inserts': {
                'name': 'BATCH INSERT OPERATIONS',
                'metrics': ['tps', 'avg_batch_latency_ms', 'p95_batch_latency_ms']
            },
            'concurrent_writes': {
                'name': 'CONCURRENT WRITE OPERATIONS',
                'metrics': ['tps', 'avg_latency_ms', 'median_latency_ms', 'p95_latency_ms', 'p99_latency_ms']
            },
            'updates': {
                'name': 'UPDATE OPERATIONS',
                'metrics': ['tps', 'avg_latency_ms', 'p95_latency_ms']
            },
            'point_reads': {
                'name': 'POINT READ OPERATIONS',
                'metrics': ['qps', 'avg_latency_ms', 'median_latency_ms', 'p95_latency_ms', 'p99_latency_ms']
            },
            'range_reads': {
                'name': 'RANGE READ OPERATIONS',
                'metrics': ['qps', 'avg_latency_ms', 'p95_latency_ms']
            }
        }

        # Metric display names
        self.metric_names = {
            'tps': 'Throughput (TPS)',
            'qps': 'Throughput (QPS)',
            'avg_latency_ms': 'Avg Latency (ms)',
            'median_latency_ms': 'Median Latency (ms)',
            'p95_latency_ms': 'P95 Latency (ms)',
            'p99_latency_ms': 'P99 Latency (ms)',
            'avg_batch_latency_ms': 'Avg Batch Latency (ms)',
            'p95_batch_latency_ms': 'P95 Batch Latency (ms)',
            'total_time_sec': 'Total Time (sec)'
        }

    def calculate_difference(self, val1: float, val2: float, lower_is_better: bool = False) -> Tuple[float, str]:
        """
        Calculate percentage difference and determine winner

        Args:
            val1: Value from first result
            val2: Value from second result
            lower_is_better: True if lower values are better (e.g., latency)

        Returns:
            Tuple of (percentage_diff, winner_label)
            Note: percentage_diff is always positive showing absolute improvement
        """
        if val2 == 0:
            return 0.0, ""

        # Calculate absolute percentage difference
        diff_pct = abs(((val1 - val2) / val2) * 100)

        # Determine winner - show database label
        if diff_pct >= self.threshold:
            if lower_is_better:
                winner = self.label1 if val1 < val2 else self.label2
            else:
                winner = self.label1 if val1 > val2 else self.label2
        else:
            winner = ""

        return diff_pct, winner

    def is_latency_metric(self, metric: str) -> bool:
        """Check if metric is a latency metric (lower is better)"""
        return 'latency' in metric or 'time' in metric

    def compare_table(self) -> str:
        """
        Generate table format comparison

        Returns:
            String containing formatted table comparison
        """
        output = []
        output.append("=" * 90)
        output.append("MYSQL PERFORMANCE COMPARISON")
        output.append("=" * 90)

        # Headers
        output.append(f"\nDatabase 1: {self.label1} ({self.result1['host']})")
        output.append(f"  Database: {self.result1['database']}")
        output.append(f"  Tested: {self.result1['timestamp']}")

        output.append(f"\nDatabase 2: {self.label2} ({self.result2['host']})")
        output.append(f"  Database: {self.result2['database']}")
        output.append(f"  Tested: {self.result2['timestamp']}")

        # Compare each test type
        for test_key, test_def in self.test_definitions.items():
            if test_key not in self.result1['results'] or test_key not in self.result2['results']:
                continue

            output.append(f"\n{'=' * 90}")
            output.append(f"{test_def['name']}")
            output.append(f"{'=' * 90}")

            r1 = self.result1['results'][test_key]
            r2 = self.result2['results'][test_key]

            # Table header
            output.append(f"\n{'Metric':<30} {self.label1:<20} {self.label2:<20} {'Difference':<20}")
            output.append("-" * 90)

            # Compare each metric
            for metric in test_def['metrics']:
                if metric not in r1 or metric not in r2:
                    continue

                val1 = r1[metric]
                val2 = r2[metric]
                lower_is_better = self.is_latency_metric(metric)
                diff_pct, winner = self.calculate_difference(val1, val2, lower_is_better)

                metric_name = self.metric_names.get(metric, metric)
                output.append(f"{metric_name:<30} {val1:<20.2f} {val2:<20.2f} {diff_pct:>7.2f}% {winner}")

        # Overall summary
        output.append(f"\n{'=' * 90}")
        output.append("OVERALL SUMMARY")
        output.append(f"{'=' * 90}")

        # Calculate averages
        summary = self._calculate_summary()

        if summary['write_tests']:
            output.append(f"\nAverage Write Throughput:")
            output.append(f"  {self.label1}: {summary['db1_write_tps']:.2f} TPS")
            output.append(f"  {self.label2}: {summary['db2_write_tps']:.2f} TPS")
            diff = abs((summary['db1_write_tps'] - summary['db2_write_tps']) / summary['db2_write_tps'] * 100)
            output.append(f"  Difference: {diff:.2f}%")

        if summary['read_tests']:
            output.append(f"\nAverage Read Throughput:")
            output.append(f"  {self.label1}: {summary['db1_read_qps']:.2f} QPS")
            output.append(f"  {self.label2}: {summary['db2_read_qps']:.2f} QPS")
            diff = abs((summary['db1_read_qps'] - summary['db2_read_qps']) / summary['db2_read_qps'] * 100)
            output.append(f"  Difference: {diff:.2f}%")

        # Winner determination
        output.append(f"\n{'=' * 90}")
        if summary['write_tests'] and summary['db1_write_tps'] > summary['db2_write_tps']:
            perf_improvement = ((summary['db1_write_tps'] - summary['db2_write_tps']) / summary['db2_write_tps'] * 100)
            output.append(f"WINNER: {self.label1} has BETTER WRITE PERFORMANCE by {perf_improvement:.2f}%")
        elif summary['write_tests']:
            perf_improvement = ((summary['db2_write_tps'] - summary['db1_write_tps']) / summary['db1_write_tps'] * 100)
            output.append(f"WINNER: {self.label2} has BETTER WRITE PERFORMANCE by {perf_improvement:.2f}%")

        if summary['read_tests'] and summary['db1_read_qps'] > summary['db2_read_qps']:
            perf_improvement = ((summary['db1_read_qps'] - summary['db2_read_qps']) / summary['db2_read_qps'] * 100)
            output.append(f"WINNER: {self.label1} has BETTER READ PERFORMANCE by {perf_improvement:.2f}%")
        elif summary['read_tests']:
            perf_improvement = ((summary['db2_read_qps'] - summary['db1_read_qps']) / summary['db1_read_qps'] * 100)
            output.append(f"WINNER: {self.label2} has BETTER READ PERFORMANCE by {perf_improvement:.2f}%")

        output.append(f"{'=' * 90}")

        # Key takeaways
        output.append(f"\n📊 KEY TAKEAWAYS:")
        output.extend(self._generate_key_takeaways())

        return "\n".join(output)

    def compare_markdown(self) -> str:
        """
        Generate markdown format comparison

        Returns:
            String containing markdown formatted comparison
        """
        output = []
        output.append("# MySQL Performance Comparison\n")

        # Metadata
        output.append("## Test Information\n")
        output.append(f"**Database 1:** {self.label1} (`{self.result1['host']}`)")
        output.append(f"- Database: `{self.result1['database']}`")
        output.append(f"- Tested: {self.result1['timestamp']}\n")

        output.append(f"**Database 2:** {self.label2} (`{self.result2['host']}`)")
        output.append(f"- Database: `{self.result2['database']}`")
        output.append(f"- Tested: {self.result2['timestamp']}\n")

        # Compare each test type
        for test_key, test_def in self.test_definitions.items():
            if test_key not in self.result1['results'] or test_key not in self.result2['results']:
                continue

            output.append(f"## {test_def['name']}\n")

            r1 = self.result1['results'][test_key]
            r2 = self.result2['results'][test_key]

            # Markdown table
            output.append(f"| Metric | {self.label1} | {self.label2} | Difference | Winner |")
            output.append("|--------|" + "----------|" * 4)

            for metric in test_def['metrics']:
                if metric not in r1 or metric not in r2:
                    continue

                val1 = r1[metric]
                val2 = r2[metric]
                lower_is_better = self.is_latency_metric(metric)
                diff_pct, winner = self.calculate_difference(val1, val2, lower_is_better)

                metric_name = self.metric_names.get(metric, metric)
                output.append(f"| {metric_name} | {val1:.2f} | {val2:.2f} | {diff_pct:.2f}% | {winner} |")

            output.append("")

        # Summary
        output.append("## Overall Summary\n")
        summary = self._calculate_summary()

        if summary['write_tests']:
            output.append("### Write Performance\n")
            output.append(f"- **{self.label1}:** {summary['db1_write_tps']:.2f} TPS")
            output.append(f"- **{self.label2}:** {summary['db2_write_tps']:.2f} TPS")
            diff = abs((summary['db1_write_tps'] - summary['db2_write_tps']) / summary['db2_write_tps'] * 100)
            output.append(f"- **Difference:** {diff:.2f}%\n")

        if summary['read_tests']:
            output.append("### Read Performance\n")
            output.append(f"- **{self.label1}:** {summary['db1_read_qps']:.2f} QPS")
            output.append(f"- **{self.label2}:** {summary['db2_read_qps']:.2f} QPS")
            diff = abs((summary['db1_read_qps'] - summary['db2_read_qps']) / summary['db2_read_qps'] * 100)
            output.append(f"- **Difference:** {diff:.2f}%\n")

        # Winner
        output.append("## Winner\n")
        if summary['write_tests'] and summary['db1_write_tps'] > summary['db2_write_tps']:
            perf = ((summary['db1_write_tps'] - summary['db2_write_tps']) / summary['db2_write_tps'] * 100)
            output.append(f"**{self.label1}** has better write performance by **{perf:.2f}%**\n")
        elif summary['write_tests']:
            perf = ((summary['db2_write_tps'] - summary['db1_write_tps']) / summary['db1_write_tps'] * 100)
            output.append(f"**{self.label2}** has better write performance by **{perf:.2f}%**\n")

        if summary['read_tests'] and summary['db1_read_qps'] > summary['db2_read_qps']:
            perf = ((summary['db1_read_qps'] - summary['db2_read_qps']) / summary['db2_read_qps'] * 100)
            output.append(f"**{self.label1}** has better read performance by **{perf:.2f}%**\n")
        elif summary['read_tests']:
            perf = ((summary['db2_read_qps'] - summary['db1_read_qps']) / summary['db1_read_qps'] * 100)
            output.append(f"**{self.label2}** has better read performance by **{perf:.2f}%**\n")

        return "\n".join(output)

    def compare_json(self) -> Dict:
        """
        Generate JSON format comparison

        Returns:
            Dictionary containing structured comparison data
        """
        comparison = {
            'metadata': {
                'comparison_date': datetime.now().isoformat(),
                'threshold': self.threshold
            },
            'database1': {
                'label': self.label1,
                'host': self.result1['host'],
                'database': self.result1['database'],
                'timestamp': self.result1['timestamp']
            },
            'database2': {
                'label': self.label2,
                'host': self.result2['host'],
                'database': self.result2['database'],
                'timestamp': self.result2['timestamp']
            },
            'comparisons': {},
            'summary': self._calculate_summary()
        }

        # Compare each test
        for test_key, test_def in self.test_definitions.items():
            if test_key not in self.result1['results'] or test_key not in self.result2['results']:
                continue

            r1 = self.result1['results'][test_key]
            r2 = self.result2['results'][test_key]

            test_comparison = {}
            for metric in test_def['metrics']:
                if metric not in r1 or metric not in r2:
                    continue

                val1 = r1[metric]
                val2 = r2[metric]
                lower_is_better = self.is_latency_metric(metric)
                diff_pct, winner = self.calculate_difference(val1, val2, lower_is_better)

                # Determine winner: 1 = db1 wins, 2 = db2 wins, 0 = no significant difference
                if abs(diff_pct) >= self.threshold:
                    if lower_is_better:
                        winner_id = 1 if val1 < val2 else 2
                    else:
                        winner_id = 1 if val1 > val2 else 2
                else:
                    winner_id = 0

                test_comparison[metric] = {
                    'database1_value': val1,
                    'database2_value': val2,
                    'difference_pct': round(diff_pct, 2),
                    'winner': winner_id
                }

            comparison['comparisons'][test_key] = {
                'name': test_def['name'],
                'metrics': test_comparison
            }

        return comparison

    def _calculate_summary(self) -> Dict:
        """Calculate summary statistics"""
        summary = {
            'write_tests': [],
            'read_tests': [],
            'db1_write_tps': 0.0,
            'db2_write_tps': 0.0,
            'db1_read_qps': 0.0,
            'db2_read_qps': 0.0
        }

        write_tests = ['single_inserts', 'batch_inserts', 'concurrent_writes', 'updates']
        read_tests = ['point_reads', 'range_reads']

        # Calculate write averages
        write_tps_1 = []
        write_tps_2 = []
        for test in write_tests:
            if test in self.result1['results'] and test in self.result2['results']:
                summary['write_tests'].append(test)
                write_tps_1.append(self.result1['results'][test]['tps'])
                write_tps_2.append(self.result2['results'][test]['tps'])

        if write_tps_1:
            summary['db1_write_tps'] = sum(write_tps_1) / len(write_tps_1)
            summary['db2_write_tps'] = sum(write_tps_2) / len(write_tps_2)

        # Calculate read averages
        read_qps_1 = []
        read_qps_2 = []
        for test in read_tests:
            if test in self.result1['results'] and test in self.result2['results']:
                summary['read_tests'].append(test)
                read_qps_1.append(self.result1['results'][test]['qps'])
                read_qps_2.append(self.result2['results'][test]['qps'])

        if read_qps_1:
            summary['db1_read_qps'] = sum(read_qps_1) / len(read_qps_1)
            summary['db2_read_qps'] = sum(read_qps_2) / len(read_qps_2)

        return summary

    def _generate_key_takeaways(self) -> List[str]:
        """Generate key takeaway messages"""
        takeaways = []

        # Single inserts
        if 'single_inserts' in self.result1['results'] and 'single_inserts' in self.result2['results']:
            r1 = self.result1['results']['single_inserts']
            r2 = self.result2['results']['single_inserts']
            takeaways.append(f"\n1. Single Insert Performance:")
            takeaways.append(f"   {self.label1}: {r1['tps']:.2f} TPS, {r1['avg_latency_ms']:.2f} ms avg")
            takeaways.append(f"   {self.label2}: {r2['tps']:.2f} TPS, {r2['avg_latency_ms']:.2f} ms avg")

        # Batch inserts
        if 'batch_inserts' in self.result1['results'] and 'batch_inserts' in self.result2['results']:
            r1 = self.result1['results']['batch_inserts']
            r2 = self.result2['results']['batch_inserts']
            takeaways.append(f"\n2. Batch Insert Performance:")
            takeaways.append(f"   {self.label1}: {r1['tps']:.2f} TPS")
            takeaways.append(f"   {self.label2}: {r2['tps']:.2f} TPS")
            diff = ((r1['tps'] - r2['tps']) / r2['tps'] * 100)
            if abs(diff) >= self.threshold:
                winner = self.label1 if diff > 0 else self.label2
                takeaways.append(f"   → {winner} is {abs(diff):.1f}% faster")

        # Concurrent writes
        if 'concurrent_writes' in self.result1['results'] and 'concurrent_writes' in self.result2['results']:
            r1 = self.result1['results']['concurrent_writes']
            r2 = self.result2['results']['concurrent_writes']
            takeaways.append(f"\n3. Concurrent Write Performance:")
            takeaways.append(f"   {self.label1}: {r1['tps']:.2f} TPS, P95: {r1['p95_latency_ms']:.2f} ms")
            takeaways.append(f"   {self.label2}: {r2['tps']:.2f} TPS, P95: {r2['p95_latency_ms']:.2f} ms")

        # Point reads
        if 'point_reads' in self.result1['results'] and 'point_reads' in self.result2['results']:
            r1 = self.result1['results']['point_reads']
            r2 = self.result2['results']['point_reads']
            takeaways.append(f"\n4. Point Read Performance:")
            takeaways.append(f"   {self.label1}: {r1['qps']:.2f} QPS, {r1['avg_latency_ms']:.2f} ms avg")
            takeaways.append(f"   {self.label2}: {r2['qps']:.2f} QPS, {r2['avg_latency_ms']:.2f} ms avg")

        # Range reads
        if 'range_reads' in self.result1['results'] and 'range_reads' in self.result2['results']:
            r1 = self.result1['results']['range_reads']
            r2 = self.result2['results']['range_reads']
            takeaways.append(f"\n5. Range Read Performance:")
            takeaways.append(f"   {self.label1}: {r1['qps']:.2f} QPS")
            takeaways.append(f"   {self.label2}: {r2['qps']:.2f} QPS")

        return takeaways

def load_result(filename: str) -> Dict:
    """
    Load a JSON result file

    Args:
        filename: Path to JSON result file

    Returns:
        Dictionary containing test results

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    with open(filename, 'r') as f:
        return json.load(f)

def main():
    """
    Main function for command-line interface

    Parses arguments, loads result files, and generates comparison report
    in the specified format.
    """
    parser = argparse.ArgumentParser(
        description='Compare two MySQL performance test results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic comparison
  python3 compare-results.py output/ec2.json output/rds.json

  # Export to markdown
  python3 compare-results.py result1.json result2.json --format markdown --output comparison.md

  # Export to JSON
  python3 compare-results.py result1.json result2.json --format json --output comparison.json

  # Custom labels
  python3 compare-results.py db1.json db2.json --label1 "Production" --label2 "Staging"

  # Show only significant differences (>20%)
  python3 compare-results.py result1.json result2.json --threshold 20
        """
    )

    parser.add_argument('file1', help='First JSON result file')
    parser.add_argument('file2', help='Second JSON result file')
    parser.add_argument('--format', choices=['table', 'markdown', 'json'],
                       default='table', help='Output format (default: table)')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--label1', help='Custom label for first database')
    parser.add_argument('--label2', help='Custom label for second database')
    parser.add_argument('--threshold', type=float, default=10.0,
                       help='Significance threshold percentage (default: 10.0)')

    args = parser.parse_args()

    try:
        # Load results
        result1 = load_result(args.file1)
        result2 = load_result(args.file2)

        # Create comparator
        comparator = ResultComparator(
            result1, result2,
            label1=args.label1,
            label2=args.label2,
            threshold=args.threshold
        )

        # Generate comparison
        if args.format == 'table':
            output_text = comparator.compare_table()
        elif args.format == 'markdown':
            output_text = comparator.compare_markdown()
        elif args.format == 'json':
            output_data = comparator.compare_json()
            output_text = json.dumps(output_data, indent=2)

        # Output results
        if args.output:
            # Auto-prepend output/ directory if no path specified
            output_path = args.output
            if not os.path.dirname(output_path):
                output_dir = "output"
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, output_path)

            with open(output_path, 'w') as f:
                f.write(output_text)
            print(f"✓ Comparison saved to: {output_path}")
        else:
            print(output_text)

    except FileNotFoundError as e:
        print(f"✗ Error: Could not find file - {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ Error: Invalid JSON file - {e}", file=sys.stderr)
        sys.exit(1)
    except KeyError as e:
        print(f"✗ Error: Missing required field in result file - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
