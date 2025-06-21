"""
Teradata SQL Query Template Generator

This module provides utilities for generating Teradata SQL query templates,
including date filters and volatile table creation.
"""
import re


def create_date_filtered_query(base_query, date_column, start_date=None, end_date=None, keyword_case='upper'):
    """
    Add date range filters to a Teradata SQL query.

    Args:
        base_query (str): The base SQL query to add date filters to
        date_column (str): The column name to apply date filters on
        start_date (str, optional): Start date in 'YYYY-MM-DD' format
        end_date (str, optional): End date in 'YYYY-MM-DD' format
        keyword_case (str, optional): Case for SQL keywords ('upper' or 'lower'). Defaults to 'upper'.

    Returns:
        str: SQL query with date filters applied
    """
    kw_where = "WHERE" if keyword_case == 'upper' else "where"
    kw_and = "AND" if keyword_case == 'upper' else "and"
    kw_group_by = "GROUP BY" if keyword_case == 'upper' else "group by"

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
    date_filter_str = f" {kw_and} ".join(date_filters)

    # Use regex to handle different SQL formatting for WHERE and GROUP BY
    # Regex searches remain case-insensitive to find the clauses regardless of original casing
    where_match = re.search(r"\bWHERE\b", filtered_query, re.IGNORECASE)
    group_by_match = re.search(r"\bGROUP BY\b", filtered_query, re.IGNORECASE)

    if where_match:
        # Add to existing WHERE clause
        # Insert after the WHERE keyword
        insert_pos = where_match.end()
        # The part before the original WHERE's content, then new filters, then original content
        filtered_query = f"{filtered_query[:insert_pos]} {date_filter_str} {kw_and}{filtered_query[insert_pos:]}"
    elif group_by_match:
        # Insert WHERE before GROUP BY
        insert_pos = group_by_match.start()
        filtered_query = f"{filtered_query[:insert_pos]}{kw_where} {date_filter_str} {filtered_query[insert_pos:]}"
    else:
        # Add WHERE clause at the end
        # Check for existing semicolons
        if filtered_query.endswith(";"):
            filtered_query = filtered_query[:-1] + f" {kw_where} {date_filter_str};"
        else:
            filtered_query += f" {kw_where} {date_filter_str}"

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
    keyword_case='upper'
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
        keyword_case (str, optional): Case for SQL keywords ('upper' or 'lower'). Defaults to 'upper'.

    Returns:
        str: Complete SQL for creating the volatile table
    """
    # Define keywords based on keyword_case
    kw_begin = "BEGIN" if keyword_case == 'upper' else "begin"
    kw_declare = "DECLARE" if keyword_case == 'upper' else "declare"
    kw_continue = "CONTINUE" if keyword_case == 'upper' else "continue"
    kw_handler = "HANDLER" if keyword_case == 'upper' else "handler"
    kw_for = "FOR" if keyword_case == 'upper' else "for"
    kw_sqlstate = "SQLSTATE" if keyword_case == 'upper' else "sqlstate"
    kw_drop_table = "DROP TABLE" if keyword_case == 'upper' else "drop table"
    kw_end = "END" if keyword_case == 'upper' else "end"
    kw_create_volatile_table = "CREATE VOLATILE TABLE" if keyword_case == 'upper' else "create volatile table"
    kw_as = "AS" if keyword_case == 'upper' else "as"
    kw_select = "SELECT" if keyword_case == 'upper' else "select"
    kw_from = "FROM" if keyword_case == 'upper' else "from"
    kw_execute_immediate = "EXECUTE IMMEDIATE" if keyword_case == 'upper' else "execute immediate"
    kw_on = "ON" if keyword_case == 'upper' else "on"
    kw_with_data = "WITH DATA" if keyword_case == 'upper' else "with data"
    kw_primary_index = "PRIMARY INDEX" if keyword_case == 'upper' else "primary index"
    kw_no_primary_index = "NO PRIMARY INDEX" if keyword_case == 'upper' else "no primary index"
    kw_on_commit_preserve_rows = "ON COMMIT PRESERVE ROWS" if keyword_case == 'upper' else "on commit preserve rows"
    kw_on_commit_delete_rows = "ON COMMIT DELETE ROWS" if keyword_case == 'upper' else "on commit delete rows"
    kw_collect_statistics = "COLLECT STATISTICS" if keyword_case == 'upper' else "collect statistics"
    kw_column = "COLUMN" if keyword_case == 'upper' else "column"


    sql_parts = []

    # Drop existing table if needed
    if check_exists:
        # Using f-string directly for BEGIN/END block as it's more of a control structure
        # and less about keywords that users might want to see in a specific case from the query itself.
        # However, internal keywords like DROP TABLE are cased.
        sql_parts.append(f"""
-- Check if table exists and drop it
{kw_begin}
    {kw_declare} {kw_continue} {kw_handler} {kw_for} {kw_sqlstate} '42000' {kw_begin} {kw_end};
    {kw_drop_table} {table_name};
{kw_end};""")

    # Format primary index string
    if primary_index_cols:
        if isinstance(primary_index_cols, str):
            primary_index_str = primary_index_cols
        else:
            primary_index_str = ", ".join(primary_index_cols)
        primary_index_clause = f"{kw_primary_index} ({primary_index_str})"
    else:
        # Default to no primary index if none specified
        primary_index_clause = kw_no_primary_index

    on_commit_clause = kw_on_commit_preserve_rows if on_commit_preserve else kw_on_commit_delete_rows

    # Handle QueryGrid if needed
    if is_querygrid and target_database:
        # Add QueryGrid wrapper
        create_stmt = f"""
-- Create volatile table using QueryGrid
{kw_create_volatile_table} {table_name} {kw_as} (
    {kw_select} * {kw_from} (
        {kw_execute_immediate}
        $$
            {query}
        $$
        {kw_on} {target_database}
    ) {kw_as} QueryGridResult
) {kw_with_data} {primary_index_clause}
{on_commit_clause};"""
    else:
        # Standard volatile table creation
        create_stmt = f"""
-- Create volatile table
{kw_create_volatile_table} {table_name} {kw_as} (
    {query}
) {kw_with_data} {primary_index_clause}
{on_commit_clause};"""

    sql_parts.append(create_stmt.strip())

    # Add stats collection if requested
    if collect_stats:
        if stats_columns:
            if isinstance(stats_columns, str):
                stats_cols_str = stats_columns
            else:
                stats_cols_str = ", ".join(stats_columns)
            stats_statement = f"{kw_collect_statistics} {kw_on} {table_name} {kw_column} ({stats_cols_str});"
        else:
            stats_statement = f"{kw_collect_statistics} {kw_on} {table_name};"
        sql_parts.append(f"""
-- Collect statistics for query optimization
{stats_statement}""")

    # Join all parts and return
    return "\n".join(sql_parts)


def create_date_partitioned_query(
    base_query, date_column, partition_by="month", start_date=None, end_date=None, keyword_case='upper'
):
    """
    Create a date-partitioned query for more efficient processing.

    Args:
        base_query (str): Base SQL query to partition
        date_column (str): Column name to partition on
        partition_by (str): Partition granularity ('day', 'month', 'year')
        start_date (str, optional): Start date in 'YYYY-MM-DD' format
        end_date (str, optional): End date in 'YYYY-MM-DD' format
        keyword_case (str, optional): Case for SQL keywords ('upper' or 'lower'). Defaults to 'upper'.

    Returns:
        str: SQL query with date partitioning
    """
    kw_cast = "CAST" if keyword_case == 'upper' else "cast"
    kw_as = "AS" if keyword_case == 'upper' else "as"
    kw_date = "DATE" if keyword_case == 'upper' else "date"
    kw_extract = "EXTRACT" if keyword_case == 'upper' else "extract"
    kw_year = "YEAR" if keyword_case == 'upper' else "year"
    kw_from = "FROM" if keyword_case == 'upper' else "from"
    kw_month = "MONTH" if keyword_case == 'upper' else "month"
    kw_group_by = "GROUP BY" if keyword_case == 'upper' else "group by"

    # First apply date filters, passing through the keyword_case
    filtered_query = create_date_filtered_query(
        base_query, date_column, start_date, end_date, keyword_case=keyword_case
    )

    # Determine date extraction function based on partition granularity
    valid_partition_by = partition_by.lower()
    if valid_partition_by == "day":
        partition_func = f"{kw_cast}({date_column} {kw_as} {kw_date})"
    elif valid_partition_by == "month":
        partition_func = f"{kw_extract}({kw_year} {kw_from} {date_column}) * 100 + {kw_extract}({kw_month} {kw_from} {date_column})"
    elif valid_partition_by == "year":
        partition_func = f"{kw_extract}({kw_year} {kw_from} {date_column})"
    else:
        raise ValueError(f"Invalid partition_by value: '{partition_by}'. Must be 'day', 'month', or 'year'.")

    # Use regex to handle different SQL formatting for GROUP BY
    # Regex search remains case-insensitive
    group_by_match = re.search(r"\bGROUP BY\b", filtered_query, re.IGNORECASE)

    if group_by_match:
        # Check if the partition function (case-insensitive for the check) is already in the GROUP BY
        # This is a simple check and might need to be more robust for complex aliases
        # For checking, we can normalize the case of the relevant part of the query and the function itself
        existing_group_by_clauses = filtered_query[group_by_match.end():]
        if partition_func.lower() not in existing_group_by_clauses.lower(): # Case-insensitive check
            # Add to existing GROUP BY
            start_of_group_by_keyword = group_by_match.start() # e.g. index of 'G' in "GROUP BY"
            original_group_by_keyword = group_by_match.group(0) # e.g. "GROUP BY" or "group by"

            query_before_keyword = filtered_query[:start_of_group_by_keyword]
            query_after_keyword_content = filtered_query[group_by_match.end():].lstrip()

            # Use the keyword_case for the "GROUP BY" being inserted/modified
            partitioned_query = f"{query_before_keyword}{kw_group_by} {partition_func}, {query_after_keyword_content}"
        else:
            # Already partitioned by this column/expression
            partitioned_query = filtered_query
    else:
        # Add new GROUP BY clause
        # Check for existing semicolons
        if filtered_query.endswith(";"):
            partitioned_query = filtered_query[:-1] + f" {kw_group_by} {partition_func};"
        else:
            partitioned_query = f"{filtered_query} {kw_group_by} {partition_func}"

    return partitioned_query


def create_in_clause(column_name, values_list, chunk_size=1000):
    """
    Create a SQL IN clause, handling chunking for large lists.

    Args:
        column_name (str): The name of the column for the IN clause.
        values_list (list): A list of values for the IN clause.
                            Values will be quoted if they are strings.
        chunk_size (int): The maximum number of values in a single IN operator.
                          Teradata typically has a limit (e.g., around 2000-4000 items
                          depending on system settings and data types).

    Returns:
        str: A SQL string for the IN clause condition.
             Returns '1=0' if values_list is empty, to ensure a valid
             SQL condition that results in no rows.
    """
    if not values_list:
        return "1=0"  # Condition that is always false

    # Determine if quoting is needed (based on the first item)
    # This assumes homogenous list types; for mixed types, users should pre-format.
    needs_quoting = isinstance(values_list[0], str)

    formatted_values = []
    for v in values_list:
        if needs_quoting:
            # Escape single quotes within the string value
            formatted_values.append(f"'{str(v).replace("'", "''")}'")
        else:
            formatted_values.append(str(v))

    if len(formatted_values) <= chunk_size:
        return f"{column_name} IN ({', '.join(formatted_values)})"
    else:
        chunks = []
        for i in range(0, len(formatted_values), chunk_size):
            chunk = formatted_values[i:i + chunk_size]
            chunks.append(f"{column_name} IN ({', '.join(chunk)})")
        return f"({ ' OR '.join(chunks) })"
