"""
Teradata SQL Query Template Generator

This module provides utilities for generating Teradata SQL query templates,
including date filters and volatile table creation.
"""
import re
import sqlparse
from sql_formatter.core import format_sql # Reverted to this import


def create_date_filtered_query(base_query, date_column, start_date=None, end_date=None, keyword_case='upper', format_sql_output=False):
    """
    Add date range filters to a Teradata SQL query.

    Args:
        base_query (str): The base SQL query to add date filters to
        date_column (str): The column name to apply date filters on
        start_date (str, optional): Start date in 'YYYY-MM-DD' format
        end_date (str, optional): End date in 'YYYY-MM-DD' format
        keyword_case (str, optional): Case for SQL keywords ('upper' or 'lower'). Defaults to 'upper'.
        format_sql_output (bool, optional): If True, format the output SQL. Defaults to False.

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
    date_filter_str = f" {kw_and} ".join(date_filters) # This will be a complete condition string

    parsed = sqlparse.parse(filtered_query)
    if not parsed:
        # Should not happen with valid SQL, but as a fallback:
        return filtered_query + f" {kw_where} {date_filter_str}"

    stmt = parsed[0]

    # Reconstruct the query token by token
    new_tokens = []
    where_found = False
    group_by_found = False
    # Used to find the correct insertion point for a new WHERE clause if no WHERE exists but GROUP BY does
    # or if neither exists, it will be the end of the statement (before a potential semicolon).
    insertion_point_idx = -1
    potential_semicolon_token = None

    # Scan for top-level WHERE and GROUP BY
    # We are interested in the *last* SELECT statement's WHERE/GROUP BY in case of CTEs.
    # sqlparse breaks statements by ';'. We operate on the first (assumed to be only, or main) statement.

    where_clause_idx = -1
    group_by_clause_idx = -1 # Index of the 'GROUP BY' keyword token itself

    # Find the main SELECT statement block to avoid modifying CTEs' clauses incorrectly
    # This is a simplified approach: find the last SELECT and work from there.
    # A truly robust solution for complex CTEs/subqueries might require deeper tree traversal.

    # Find tokens belonging to the last SELECT query block
    # For simplicity, we'll iterate tokens and find the *last* top-level WHERE or GROUP BY
    # This might not be perfect for deeply nested structures but should work for common CTE patterns.

    last_where_token_idx = -1
    last_group_by_token_idx = -1

    # stmt.get_type() can be 'SELECT', 'INSERT', 'CREATE', 'WITH' (for CTEs)
    # If it's a 'WITH' statement, the actual SELECT is usually the last major token group.

    tokens_to_search = stmt.tokens

    # Attempt to find the main SELECT statement part if it's a CTE
    if stmt.get_type() == 'WITH':
        # Find the token that starts the main query (usually a SELECT keyword after the CTE part)
        # This is heuristic: assumes CTE definition `WITH ... AS (...) SELECT ...`
        cte_definitions_ended = False
        main_query_start_idx = -1
        for i, token in enumerate(stmt.tokens):
            if isinstance(token, sqlparse.sql.Parenthesis): # End of CTE definition AS (...)
                # Check if the next non-whitespace token is SELECT
                for next_token_idx in range(i + 1, len(stmt.tokens)):
                    next_token = stmt.tokens[next_token_idx]
                    if next_token.is_whitespace:
                        continue
                    if next_token.is_keyword and next_token.normalized == 'SELECT':
                        main_query_start_idx = next_token_idx
                        break
                    else: # Not a SELECT immediately after CTE, structure is different
                        main_query_start_idx = -1 # Reset
                        break
                if main_query_start_idx != -1:
                    break

        if main_query_start_idx != -1:
            tokens_to_search = stmt.tokens[main_query_start_idx:]
        # else: search all tokens if main SELECT not clearly isolated (fallback)

    # Find the relevant WHERE or GROUP BY in the selected tokens_to_search
    # We are looking for the first WHERE or GROUP BY in this part of the query.
    current_where_idx_in_search_tokens = -1
    current_group_by_idx_in_search_tokens = -1

    for i, token in enumerate(tokens_to_search):
        if isinstance(token, sqlparse.sql.Where):
            current_where_idx_in_search_tokens = i
            break # Found the main WHERE for this segment
        # Fallback for simple WHERE keyword not wrapped in Where object
        elif token.is_keyword and token.normalized == 'WHERE' and current_where_idx_in_search_tokens == -1 :
             current_where_idx_in_search_tokens = i # Mark the keyword itself
             break

    # If no WHERE, check for GROUP BY in the same tokens_to_search
    if current_where_idx_in_search_tokens == -1:
        for i, token in enumerate(tokens_to_search):
            if token.is_keyword and token.normalized == 'GROUP BY':
                current_group_by_idx_in_search_tokens = i
                break

    # Adjust indices to be relative to the original stmt.tokens if we searched a sub-segment
    if stmt.get_type() == 'WITH' and main_query_start_idx != -1:
        if current_where_idx_in_search_tokens != -1:
            where_clause_idx = main_query_start_idx + current_where_idx_in_search_tokens
        if current_group_by_idx_in_search_tokens != -1:
            group_by_clause_idx = main_query_start_idx + current_group_by_idx_in_search_tokens
    else: # Searched all tokens
        where_clause_idx = current_where_idx_in_search_tokens
        group_by_clause_idx = current_group_by_idx_in_search_tokens


    processed_tokens = []
    if where_clause_idx != -1:
        # An existing WHERE clause was found (either as Where object or keyword)
        # Iterate through all original tokens and rebuild, modifying the found WHERE clause
        for i, token in enumerate(stmt.tokens):
            if i == where_clause_idx: # This is the Where object or WHERE keyword
                if isinstance(token, sqlparse.sql.Where):
                    # It's a Where object, modify its internal tokens
                    where_obj = token
                    new_where_tokens = []
                    # First token of Where object is the 'WHERE' keyword
                    new_where_tokens.append(where_obj.tokens[0])
                    new_where_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
                    new_where_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Text, date_filter_str))
                    new_where_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
                    new_where_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Keyword, kw_and))
                    # Append rest of original WHERE clause tokens (original conditions)
                    # Need to ensure a space if the original conditions don't start with one.
                    if len(where_obj.tokens) > 1 and not where_obj.tokens[1].is_whitespace:
                         new_where_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
                    new_where_tokens.extend(where_obj.tokens[1:]) # Add original conditions
                    processed_tokens.append(sqlparse.sql.Where(new_where_tokens))
                else: # It's just a WHERE keyword token
                    processed_tokens.append(token) # The WHERE keyword
                    processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
                    processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Text, date_filter_str))
                    processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
                    # Assume original conditions followed, so add AND.
                    # This path is less robust than modifying a Where object.
                    # The next tokens in stmt.tokens should be the original conditions.
                    processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Keyword, kw_and))
                    # A space will be added if the next token isn't already whitespace by the loop.
            else:
                processed_tokens.append(token)
    elif group_by_clause_idx != -1:
        # No WHERE, but GROUP BY exists. Insert new WHERE clause before GROUP BY.
        for i, token in enumerate(stmt.tokens):
            if i == group_by_clause_idx: # This is the 'GROUP BY' keyword
                processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Keyword, kw_where))
                processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
                processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Text, date_filter_str))
                processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
            processed_tokens.append(token)
    else:
        # No WHERE and no GROUP BY. Add new WHERE at the end (before semicolon if any).
        temp_tokens = list(stmt.tokens)
        semicolon_token = None
        if temp_tokens and temp_tokens[-1].ttype is sqlparse.tokens.Punctuation and temp_tokens[-1].value == ';':
            semicolon_token = temp_tokens.pop()

        processed_tokens.extend(temp_tokens)
        if processed_tokens and not processed_tokens[-1].is_whitespace:
            processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
        processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Keyword, kw_where))
        processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
        processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Text, date_filter_str))
        if semicolon_token:
            processed_tokens.append(semicolon_token)

    final_sql = str(sqlparse.sql.Statement(processed_tokens)).strip()

    if format_sql_output:
        # Reverting to call without uppercase, as it's causing TypeError.
        # This means sql-formatter will use its default keyword casing.
        return format_sql(final_sql)
    else:
        return final_sql


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
    keyword_case='upper',
    format_sql_output=False
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
        format_sql_output (bool, optional): If True, format the output SQL. Defaults to False.

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

    final_sql = "\n".join(sql_parts)

    if format_sql_output:
        # Reverting to call without uppercase.
        # Note: sql-formatter might struggle with multi-statement SQL like the BEGIN/END block
        # for DROP TABLE. We'll format the whole thing, but it might not be perfect for that part.
        # The primary benefit will be for the CREATE TABLE statement itself.
        return format_sql(final_sql)
    else:
        return final_sql


def create_date_partitioned_query(
    base_query, date_column, partition_by="month", start_date=None, end_date=None, keyword_case='upper', format_sql_output=False
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
        format_sql_output (bool, optional): If True, format the output SQL. Defaults to False.

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

    parsed_filtered_query = sqlparse.parse(filtered_query)
    if not parsed_filtered_query:
        # Fallback, should not happen with valid SQL
        return f"{filtered_query} {kw_group_by} {partition_func}"

    stmt = parsed_filtered_query[0]

    processed_tokens = []
    group_by_found = False

    # Check if GROUP BY clause exists and if partition_func is already in it
    original_tokens_str_lower = stmt.value.lower() # For checking existence of partition_func

    # Iterate once to find if GROUP BY exists and if function is already part of it
    # This is a simplified check; truly robust checking would involve parsing expressions within GROUP BY
    # For now, we check if the string representation of partition_func (lower case) is in the query part after GROUP BY
    idx_group_by = -1
    for i, token in enumerate(stmt.tokens):
        if token.is_keyword and token.normalized == 'GROUP BY':
            idx_group_by = i
            group_by_found = True
            break # Found the primary GROUP BY

    if group_by_found:
        # Check if partition_func (case insensitive) is already in the existing GROUP BY clause
        # Reconstruct the string of clauses after "GROUP BY"
        group_by_content_tokens = stmt.tokens[idx_group_by + 1:]
        group_by_content_str = "".join(str(t) for t in group_by_content_tokens).lower()
        if partition_func.lower() in group_by_content_str:
            return filtered_query # Already partitioned, return original filtered query

        # If not found, insert it
        inserted_partition_func = False
        for i, token in enumerate(stmt.tokens):
            if i == idx_group_by: # At the GROUP BY keyword
                processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Keyword, kw_group_by)) # Use cased keyword
                processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
                processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Text, partition_func))
                processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Punctuation, ','))
                processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
                inserted_partition_func = True
            elif inserted_partition_func and token.is_whitespace:
                # Avoid adding double spaces if original GROUP BY was followed by a space
                # This token (original whitespace after GROUP BY) is skipped as we added our own.
                continue
            elif inserted_partition_func and i == idx_group_by + 1:
                # This is the token immediately after original "GROUP BY".
                # We've already added partition_func, comma, space. Now add this token.
                processed_tokens.append(token)
                # Reset flag so we don't skip subsequent whitespaces unnecessarily
                # This logic path (i == idx_group_by + 1) is primarily for the first item of the original group by
                # inserted_partition_func = False # No, keep true to indicate we are past the insertion point
            elif i > idx_group_by and not inserted_partition_func:
                 # This case should not be hit if idx_group_by is correct.
                 # This means we are past the original GROUP BY keyword, but haven't inserted.
                 # This implies we are iterating over original GROUP BY content tokens.
                 processed_tokens.append(token)
            elif i < idx_group_by:
                processed_tokens.append(token) # Tokens before GROUP BY
            elif i > idx_group_by and inserted_partition_func: # Tokens after original GROUP BY items start
                processed_tokens.append(token)


        if not inserted_partition_func: # Should not happen if group_by_found is true
             processed_tokens.extend(stmt.tokens) # Fallback

    else:
        # No GROUP BY clause, add one at the end (before semicolon if any)
        has_semicolon = False
        temp_tokens = list(stmt.tokens)
        if temp_tokens and temp_tokens[-1].ttype is sqlparse.tokens.Punctuation and temp_tokens[-1].value == ';':
            has_semicolon = True
            semicolon_token = temp_tokens.pop()

        processed_tokens.extend(temp_tokens)
        if processed_tokens and not processed_tokens[-1].is_whitespace:
            processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
        processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Keyword, kw_group_by))
        processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Whitespace, ' '))
        processed_tokens.append(sqlparse.sql.Token(sqlparse.tokens.Text, partition_func))
        if has_semicolon:
            processed_tokens.append(semicolon_token)

    final_sql = str(sqlparse.sql.Statement(processed_tokens)).strip()

    if format_sql_output:
        # Reverting to call without uppercase.
        return format_sql(final_sql)
    else:
        return final_sql


def create_in_clause(column_name, values_list, chunk_size=1000, format_sql_output=False):
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
        format_sql_output (bool, optional): If True, format the output SQL. Defaults to False.
    """
    # Keywords used by this function are IN, OR.
    # These are not currently managed by keyword_case, but could be if needed.
    # For now, they will be uppercase as written.

    kw_in = "IN" # Assuming IN and OR keywords remain uppercase for this function for now
    kw_or = "OR"

    if not values_list:
        # '1=0' is simple enough not to need formatting.
        return "1=0"

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

    raw_sql = ""
    if len(formatted_values) <= chunk_size:
        raw_sql = f"{column_name} {kw_in} ({', '.join(formatted_values)})"
    else:
        chunks = []
        for i in range(0, len(formatted_values), chunk_size):
            chunk = formatted_values[i:i + chunk_size]
            chunks.append(f"{column_name} {kw_in} ({', '.join(chunk)})")
        raw_sql = f"({ f' {kw_or} '.join(chunks) })"

    if format_sql_output:
        # Reverting to call without uppercase for create_in_clause as well.
        # It will use sql-formatter's default casing for IN/OR.
        return format_sql(raw_sql)
    else:
        return raw_sql
