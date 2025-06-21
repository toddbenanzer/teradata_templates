"""
Teradata SQL Query Template Generator

This module provides utilities for generating Teradata SQL query templates,
including date filters and volatile table creation.
"""
import re


def create_date_filtered_query(base_query, date_column, start_date=None, end_date=None):
    """
    Add date range filters to a Teradata SQL query.

    Args:
        base_query (str): The base SQL query to add date filters to
        date_column (str): The column name to apply date filters on
        start_date (str, optional): Start date in 'YYYY-MM-DD' format
        end_date (str, optional): End date in 'YYYY-MM-DD' format

    Returns:
        str: SQL query with date filters applied
    """
    # Create a copy of the original query
    filtered_query = base_query.strip()

    # Check if we have any date filters to apply
    if not (start_date or end_date):
        return filtered_query

    date_filters = []

    # Add start date filter if provided
    if start_date:
        date_filters.append(f"{date_column} >= '{start_date}'")

    # Add end date filter if provided
    if end_date:
        date_filters.append(f"{date_column} <= '{end_date}'")

    # Combine date filters
    date_filter_str = " AND ".join(date_filters)

    # Use regex to handle different SQL formatting for WHERE and GROUP BY
    where_match = re.search(r"\bWHERE\b", filtered_query, re.IGNORECASE)
    group_by_match = re.search(r"\bGROUP BY\b", filtered_query, re.IGNORECASE)

    if where_match:
        # Add to existing WHERE clause
        # Insert after the WHERE keyword
        insert_pos = where_match.end()
        filtered_query = f"{filtered_query[:insert_pos]} {date_filter_str} AND{filtered_query[insert_pos:]}"
    elif group_by_match:
        # Insert WHERE before GROUP BY
        insert_pos = group_by_match.start()
        filtered_query = f"{filtered_query[:insert_pos]}WHERE {date_filter_str} {filtered_query[insert_pos:]}"
    else:
        # Add WHERE clause at the end
        # Check for existing semicolons
        if filtered_query.endswith(";"):
            filtered_query = filtered_query[:-1] + f" WHERE {date_filter_str};"
        else:
            filtered_query += f" WHERE {date_filter_str}"

    return filtered_query


def create_volatile_table_sql(
    table_name,
    query,
    primary_index_cols=None,
    check_exists=True,
    collect_stats=True,
    stats_columns=None,
    on_commit_preserve=True,
    is_querygrid=False,
    target_database=None,
):
    """
    Generate SQL to create a volatile table from a query with proper best practices.

    Args:
        table_name (str): Name for the volatile table
        query (str): SQL query that will populate the table
        primary_index_cols (list/str, optional): Column(s) to use as primary index.
        check_exists (bool): Whether to check if table exists and drop it first.
        collect_stats (bool): Whether to collect statistics on the new table.
        stats_columns (list/str, optional): Specific column(s) to collect statistics on.
                                           If None, statistics are collected on the table.
        on_commit_preserve (bool): If True, use ON COMMIT PRESERVE ROWS.
                                   If False, use ON COMMIT DELETE ROWS.
        is_querygrid (bool): Whether this involves a QueryGrid query.
        target_database (str, optional): Target database for QueryGrid queries.

    Returns:
        str: Complete SQL for creating the volatile table
    """
    sql_parts = []

    # Drop existing table if needed
    if check_exists:
        sql_parts.append(f"""
-- Check if table exists and drop it
BEGIN
    DECLARE CONTINUE HANDLER FOR SQLSTATE '42000' BEGIN END;
    DROP TABLE {table_name};
END;""")

    # Format primary index string
    if primary_index_cols:
        if isinstance(primary_index_cols, str):
            primary_index_str = primary_index_cols
        else:
            primary_index_str = ", ".join(primary_index_cols)
        primary_index_clause = f"PRIMARY INDEX ({primary_index_str})"
    else:
        # Default to no primary index if none specified
        primary_index_clause = "NO PRIMARY INDEX"

    on_commit_clause = "ON COMMIT PRESERVE ROWS" if on_commit_preserve else "ON COMMIT DELETE ROWS"

    # Handle QueryGrid if needed
    if is_querygrid and target_database:
        # Add QueryGrid wrapper
        create_stmt = f"""
-- Create volatile table using QueryGrid
CREATE VOLATILE TABLE {table_name} AS (
    SELECT * FROM (
        EXECUTE IMMEDIATE
        $$
            {query}
        $$
        ON {target_database}
    ) AS QueryGridResult
) WITH DATA {primary_index_clause}
{on_commit_clause};"""
    else:
        # Standard volatile table creation
        create_stmt = f"""
-- Create volatile table
CREATE VOLATILE TABLE {table_name} AS (
    {query}
) WITH DATA {primary_index_clause}
{on_commit_clause};"""

    sql_parts.append(create_stmt.strip())

    # Add stats collection if requested
    if collect_stats:
        if stats_columns:
            if isinstance(stats_columns, str):
                stats_cols_str = stats_columns
            else:
                stats_cols_str = ", ".join(stats_columns)
            stats_statement = f"COLLECT STATISTICS ON {table_name} COLUMN ({stats_cols_str});"
        else:
            stats_statement = f"COLLECT STATISTICS ON {table_name};"
        sql_parts.append(f"""
-- Collect statistics for query optimization
{stats_statement}""")

    # Join all parts and return
    return "\n".join(sql_parts)


def create_date_partitioned_query(
    base_query, date_column, partition_by="month", start_date=None, end_date=None
):
    """
    Create a date-partitioned query for more efficient processing.

    Args:
        base_query (str): Base SQL query to partition
        date_column (str): Column name to partition on
        partition_by (str): Partition granularity ('day', 'month', 'year')
        start_date (str, optional): Start date in 'YYYY-MM-DD' format
        end_date (str, optional): End date in 'YYYY-MM-DD' format

    Returns:
        str: SQL query with date partitioning
    """
    # First apply date filters
    filtered_query = create_date_filtered_query(
        base_query, date_column, start_date, end_date
    )

    # Determine date extraction function based on partition granularity
    valid_partition_by = partition_by.lower()
    if valid_partition_by == "day":
        partition_func = f"CAST({date_column} AS DATE)"
    elif valid_partition_by == "month":
        partition_func = f"EXTRACT(YEAR FROM {date_column}) * 100 + EXTRACT(MONTH FROM {date_column})"
    elif valid_partition_by == "year":
        partition_func = f"EXTRACT(YEAR FROM {date_column})"
    else:
        raise ValueError(f"Invalid partition_by value: '{partition_by}'. Must be 'day', 'month', or 'year'.")

    # Use regex to handle different SQL formatting for GROUP BY
    group_by_match = re.search(r"\bGROUP BY\b", filtered_query, re.IGNORECASE)

    if group_by_match:
        # Check if the partition function is already in the GROUP BY
        # This is a simple check and might need to be more robust for complex aliases
        if partition_func not in filtered_query[group_by_match.end():]:
            # Add to existing GROUP BY
            # Ensure correct spacing around the newly added partition function
            # group_by_keyword = group_by_match.group(0) # "GROUP BY" or "group by" etc.
            # before_group_by = filtered_query[:group_by_match.start()]
            # after_group_by = filtered_query[group_by_match.end():].lstrip()
            # partitioned_query = f"{before_group_by}{group_by_keyword} {partition_func}, {after_group_by}"

            # Simpler approach: replace "GROUP BY" with "GROUP BY new_col,"
            # This handles varying spaces after GROUP BY in the original query.
            # We need to be careful if other parts of the query contain "GROUP BY" in comments or strings.
            # For now, assume it's the actual clause.

            # Use re.sub for a more robust replacement
            original_group_by_clause = group_by_match.group(0) # This gets the exact "GROUP BY" text matched
            replacement = f"{original_group_by_clause} {partition_func},"

            # We need to replace only the first occurrence after the initial part of the query
            # This is tricky if GROUP BY appears multiple times.
            # The current logic inserts at group_by_match.end()

            # Let's stick to insertion, but fix spacing

            # query_part_before_group_by_keyword = filtered_query[:group_by_match.start()]
            # group_by_keyword_itself = group_by_match.group(0) # e.g. "GROUP BY"
            # query_part_after_group_by_keyword = filtered_query[group_by_match.end():]

            # partitioned_query = f"{query_part_before_group_by_keyword}{group_by_keyword_itself} {partition_func}, {query_part_after_group_by_keyword.lstrip()}"

            # Corrected logic:
            start_of_group_by_keyword = group_by_match.start()
            end_of_group_by_keyword = group_by_match.end()

            query_before = filtered_query[:end_of_group_by_keyword] # Includes "GROUP BY"
            query_after = filtered_query[end_of_group_by_keyword:].lstrip() # The rest of the clause, stripped

            partitioned_query = f"{query_before} {partition_func}, {query_after}"

        else:
            # Already partitioned by this column/expression
            partitioned_query = filtered_query
    else:
        # Add new GROUP BY clause
        # Check for existing semicolons
        if filtered_query.endswith(";"):
            partitioned_query = filtered_query[:-1] + f" GROUP BY {partition_func};"
        else:
            partitioned_query = f"{filtered_query} GROUP BY {partition_func}"

    return partitioned_query
