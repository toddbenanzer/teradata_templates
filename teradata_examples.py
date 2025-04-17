"""
Teradata SQL Query Template Generator

This module provides utilities for generating Teradata SQL query templates,
including date filters and volatile table creation.
"""


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

    # Check if the query already has a WHERE clause
    has_where = "WHERE" in filtered_query.upper()

    date_filters = []

    # Add start date filter if provided
    if start_date:
        date_filters.append(f"{date_column} >= '{start_date}'")

    # Add end date filter if provided
    if end_date:
        date_filters.append(f"{date_column} <= '{end_date}'")

    # Combine date filters
    date_filter_str = " AND ".join(date_filters)

    # Add filters to query
    if has_where:
        # Add to existing WHERE clause
        filtered_query = filtered_query.replace(
            "WHERE", f"WHERE {date_filter_str} AND ", 1
        )
    else:
        # Check if the query has a GROUP BY clause
        group_by_pos = filtered_query.upper().find("GROUP BY")
        if group_by_pos > -1:
            # Insert WHERE before GROUP BY
            filtered_query = (
                filtered_query[:group_by_pos]
                + f"WHERE {date_filter_str} "
                + filtered_query[group_by_pos:]
            )
        else:
            # Add WHERE clause at the end
            filtered_query += f" WHERE {date_filter_str}"

    return filtered_query


def create_volatile_table_sql(
    table_name,
    query,
    primary_index_cols=None,
    check_exists=True,
    collect_stats=True,
    is_querygrid=False,
    target_database=None,
):
    """
    Generate SQL to create a volatile table from a query with proper best practices.

    Args:
        table_name (str): Name for the volatile table
        query (str): SQL query that will populate the table
        primary_index_cols (list/str, optional): Column(s) to use as primary index
        check_exists (bool): Whether to check if table exists and drop it first
        collect_stats (bool): Whether to collect statistics on the new table
        is_querygrid (bool): Whether this involves a QueryGrid query
        target_database (str, optional): Target database for QueryGrid queries

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
END;
""")

    # Format primary index string
    if primary_index_cols:
        if isinstance(primary_index_cols, str):
            primary_index_str = primary_index_cols
        else:
            primary_index_str = ", ".join(primary_index_cols)
    else:
        # Default to no primary index if none specified
        primary_index_str = "NO PRIMARY INDEX"

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
) WITH DATA PRIMARY INDEX ({primary_index_str})
ON COMMIT PRESERVE ROWS;
"""
    else:
        # Standard volatile table creation
        create_stmt = f"""
-- Create volatile table
CREATE VOLATILE TABLE {table_name} AS (
    {query}
) WITH DATA PRIMARY INDEX ({primary_index_str})
ON COMMIT PRESERVE ROWS;
"""

    sql_parts.append(create_stmt)

    # Add stats collection if requested
    if collect_stats:
        sql_parts.append(f"""
-- Collect statistics for query optimization
COLLECT STATISTICS ON {table_name};
""")

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
    if partition_by.lower() == "day":
        partition_func = f"CAST({date_column} AS DATE)"
    elif partition_by.lower() == "month":
        partition_func = f"EXTRACT(YEAR FROM {date_column}) * 100 + EXTRACT(MONTH FROM {date_column})"
    elif partition_by.lower() == "year":
        partition_func = f"EXTRACT(YEAR FROM {date_column})"
    else:
        # Default to month if invalid granularity
        partition_func = f"EXTRACT(YEAR FROM {date_column}) * 100 + EXTRACT(MONTH FROM {date_column})"

    # Check if query already has a GROUP BY
    if "GROUP BY" in filtered_query.upper():
        # Add to existing GROUP BY
        partitioned_query = filtered_query.replace(
            "GROUP BY", f"GROUP BY {partition_func}, ", 1
        )
    else:
        # Add new GROUP BY clause
        partitioned_query = f"{filtered_query} GROUP BY {partition_func}"

    return partitioned_query
