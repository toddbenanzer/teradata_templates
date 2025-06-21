# Teradata SQL Templates Generator

A lightweight Python module for generating Teradata SQL templates with a focus on date filtering and volatile table creation.

## Overview

This module provides utilities for:

1. Adding date range filters to existing SQL queries
2. Creating volatile tables with proper indexing and statistics
3. Supporting QueryGrid for cross-database queries
4. Adding date partitioning to queries for improved performance

## Installation

Simply copy the `teradata_sql_utils.py` file to your project directory.

## Usage

### Date Filtering

```python
import teradata_sql_utils as tdu

# Your base query
base_query = """
SELECT
    customer_id,
    SUM(order_amount) AS total_sales
FROM orders
"""

# Add date filtering
filtered_query = tdu.create_date_filtered_query(
    base_query=base_query,
    date_column="order_date",
    start_date="2023-01-01",
    end_date="2023-03-31"
)

print(filtered_query)
```

### Volatile Table Creation

```python
# Generate SQL for creating a volatile table
volatile_sql = tdu.create_volatile_table_sql(
    table_name="vol_customer_sales",
    query="SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id",
    primary_index_cols=["customer_id"],
    check_exists=True,
    collect_stats=True
)

# Save to a file or execute directly
with open("create_volatile_table.sql", "w") as f:
    f.write(volatile_sql)
```

### QueryGrid Support

```python
# Create a volatile table from a remote database
querygrid_sql = tdu.create_volatile_table_sql(
    table_name="vol_products",
    query="SELECT * FROM product_catalog WHERE active = 'Y'",
    primary_index_cols=["product_id"],
    is_querygrid=True,
    target_database="CENTRAL_EDW"
)

print(querygrid_sql)
```

## Examples

Basic usage examples are provided below. For more detailed examples, refer to the unit tests in `test_teradata_sql_utils.py`.

## Running Tests

To run the unit tests for this module:
```bash
python -m unittest test_teradata_sql_utils.py
```

## Best Practices

1. **Primary Indexes**: Always specify appropriate primary index columns for volatile tables to optimize query performance
2. **Statistics**: Collect statistics on volatile tables to help the optimizer choose efficient execution plans
3. **Table Cleanup**: Use the `check_exists=True` parameter to ensure clean creation by dropping any existing tables with the same name
4. **Date Partitioning**: For large datasets, consider using the `create_date_partitioned_query` function to partition by date

## Function Reference

### `create_date_filtered_query(base_query, date_column, start_date=None, end_date=None)`

Adds date range filters to an existing SQL query.

### `create_volatile_table_sql(table_name, query, primary_index_cols=None, check_exists=True, collect_stats=True, stats_columns=None, on_commit_preserve=True, is_querygrid=False, target_database=None)`

Generates complete SQL for creating a volatile table from a query.
- `table_name` (str): Name for the volatile table.
- `query` (str): SQL query that will populate the table.
- `primary_index_cols` (list/str, optional): Column(s) to use as primary index.
- `check_exists` (bool, default=True): If True, adds SQL to drop the table if it exists.
- `collect_stats` (bool, default=True): If True, adds SQL to collect statistics.
- `stats_columns` (list/str, optional): Specific column(s) to collect statistics on. If None and `collect_stats` is True, statistics are collected on the table.
- `on_commit_preserve` (bool, default=True): If True, uses `ON COMMIT PRESERVE ROWS`. If False, uses `ON COMMIT DELETE ROWS`.
- `is_querygrid` (bool, default=False): Set to True if this involves a QueryGrid query.
- `target_database` (str, optional): Target database for QueryGrid queries.

### `create_date_partitioned_query(base_query, date_column, partition_by="month", start_date=None, end_date=None)`

Creates a date-partitioned query with the specified granularity (day, month, year).
