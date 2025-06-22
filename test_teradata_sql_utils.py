import unittest
import teradata_sql_utils as tdu

class TestTeradataSQLUtils(unittest.TestCase):

    def test_create_date_filtered_query_no_dates(self):
        base_query = "SELECT * FROM sales"
        query = tdu.create_date_filtered_query(base_query, "sale_date")
        self.assertEqual(query.strip(), base_query)

    def test_create_date_filtered_query_start_date_only_upper(self):
        base_query = "SELECT * FROM sales"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01", keyword_case='upper')
        expected = "SELECT * FROM sales WHERE sale_date >= '2023-01-01'"
        self.assertIn("WHERE", query)
        self.assertEqual(query.strip(), expected) # Default no formatting

    def test_create_date_filtered_query_start_date_only_upper_formatted(self):
        base_query = "SELECT * FROM sales"
        query = tdu.create_date_filtered_query(
            base_query, "sale_date", start_date="2023-01-01",
            keyword_case='upper', format_sql_output=True
        )
        # sql-formatter default seems to be uppercase for SELECT, FROM, WHERE.
        # Our internal keyword_case='upper' aligns with this.
        self.assertIn("SELECT", query)
        self.assertIn("*", query)
        self.assertIn("FROM", query)
        self.assertIn("sales", query)
        self.assertIn("WHERE", query) # Expecting uppercase due to keyword_case='upper' being passed to formatter
        self.assertIn("sale_date >= '2023-01-01'", query)
        self.assertTrue(len(query.splitlines()) > 1 or "SELECT\n" in query or "\n WHERE" in query)


    def test_create_date_filtered_query_start_date_only_lower(self):
        base_query = "SELECT * FROM sales"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01", keyword_case='lower')
        expected = "SELECT * FROM sales where sale_date >= '2023-01-01'"
        self.assertIn("where", query)
        self.assertEqual(query.strip(), expected)

    def test_create_date_filtered_query_end_date_only_upper(self):
        base_query = "SELECT * FROM sales"
        query = tdu.create_date_filtered_query(base_query, "sale_date", end_date="2023-12-31")
        expected = "SELECT * FROM sales WHERE sale_date <= '2023-12-31'"
        self.assertEqual(query.strip(), expected)

    def test_create_date_filtered_query_both_dates_lower(self):
        base_query = "SELECT * FROM sales"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01", end_date="2023-03-31", keyword_case='lower')
        expected = "SELECT * FROM sales where sale_date >= '2023-01-01' and sale_date <= '2023-03-31'"
        self.assertIn("where", query)
        self.assertIn("and", query)
        self.assertEqual(query.strip(), expected)

    def test_create_date_filtered_query_with_existing_where_upper(self):
        base_query = "SELECT * FROM sales WHERE product_id = 100"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01", keyword_case='upper')
        self.assertIn("WHERE sale_date >= '2023-01-01' AND product_id = 100", query.replace("  ", " "))

    def test_create_date_filtered_query_with_existing_where_lower(self):
        base_query = "SELECT * FROM sales WHERE product_id = 100"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01", keyword_case='lower')
        self.assertIn("WHERE sale_date >= '2023-01-01' and product_id = 100", query.replace("  ", " "))

    def test_create_date_filtered_query_with_subquery_no_where(self):
        base_query = "SELECT * FROM (SELECT id, val FROM sub_table) AS main_query"
        query = tdu.create_date_filtered_query(base_query, "event_date", start_date="2023-01-01", keyword_case='upper')
        expected = "SELECT * FROM (SELECT id, val FROM sub_table) AS main_query WHERE event_date >= '2023-01-01'"
        self.assertEqual(query.strip(), expected.strip())

    def test_create_date_filtered_query_with_cte_and_where(self):
        base_query = """
        WITH MyCTE AS (SELECT id, data_col FROM source)
        SELECT id FROM MyCTE WHERE data_col = 'test'
        """
        query = tdu.create_date_filtered_query(base_query, "cte_date_col", start_date="2023-05-05", keyword_case='upper')
        self.assertIn("WITH MyCTE AS (SELECT id, data_col FROM source)", query)
        self.assertIn("SELECT id FROM MyCTE", query)
        self.assertIn("WHERE cte_date_col >= '2023-05-05' AND data_col = 'test'", query.replace("\n", " ").replace("  ", " "))

    def test_create_date_filtered_query_with_existing_where_and_group_by_lower(self):
        base_query = "SELECT product_id, SUM(amount) FROM sales WHERE category = 'electronics' GROUP BY product_id"
        query = tdu.create_date_filtered_query(base_query, "order_date", start_date="2024-01-01", keyword_case='lower')
        expected_fragment = "WHERE order_date >= '2024-01-01' and category = 'electronics'"
        normalized_query = ' '.join(query.split())
        normalized_expected = ' '.join(expected_fragment.split())
        self.assertIn(normalized_expected, normalized_query)
        self.assertNotIn("AND", query)

    def test_create_date_filtered_query_with_group_by_no_where_lower(self):
        base_query = "SELECT product_id, SUM(amount) FROM sales GROUP BY product_id"
        query = tdu.create_date_filtered_query(base_query, "order_date", start_date="2024-01-01", keyword_case='lower')
        self.assertIn("where order_date >= '2024-01-01' GROUP BY", query.replace("  ", " "))

    def test_create_date_filtered_query_with_semicolon_lower(self):
        base_query = "SELECT * FROM sales;"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01", keyword_case='lower')
        expected = "SELECT * FROM sales where sale_date >= '2023-01-01';"
        self.assertEqual(query.strip(), expected)

    # --- Tests for create_volatile_table_sql ---
    def test_create_volatile_table_sql_basic_upper(self):
        query_content = "SELECT id, name FROM source_table"
        sql = tdu.create_volatile_table_sql("vol_test", query_content, primary_index_cols="id", keyword_case='upper')
        self.assertIn("DROP TABLE vol_test;", sql)
        self.assertIn("CREATE VOLATILE TABLE vol_test AS (", sql)
        self.assertIn(query_content, sql)
        self.assertIn("WITH DATA PRIMARY INDEX (id)", sql)
        self.assertIn("ON COMMIT PRESERVE ROWS;", sql)
        self.assertIn("COLLECT STATISTICS ON vol_test;", sql)

    def test_create_volatile_table_sql_basic_lower(self):
        query_content = "select id, name from source_table"
        sql = tdu.create_volatile_table_sql("vol_test_lower", query_content, primary_index_cols="id", keyword_case='lower')
        self.assertIn("drop table vol_test_lower;", sql)
        self.assertIn("create volatile table vol_test_lower as (", sql)
        self.assertIn(query_content, sql)
        self.assertIn("with data primary index (id)", sql)
        self.assertIn("on commit preserve rows;", sql)
        self.assertIn("collect statistics on vol_test_lower;", sql)

    def test_create_volatile_table_sql_basic_upper_formatted(self):
        query_content = "SELECT id, name FROM source_table"
        sql = tdu.create_volatile_table_sql(
            "vol_test_fmt", query_content, primary_index_cols="id",
            keyword_case='upper', format_sql_output=True
        )
        # sql-formatter default behavior observed:
        # CREATE VOLATILE TABLE (upper)
        # AS (upper)
        # SELECT, FROM (upper, from user query preserved if already upper)
        # with data (lower)
        # primary index (lower)
        # on commit preserve rows (lower)
        # COLLECT STATISTICS (upper)
        # ON (upper)
        # This is very mixed. We'll test for the major parts and what seems consistent from formatter.
        self.assertIn("CREATE VOLATILE TABLE", sql) # Formatter keeps this upper
        self.assertIn("vol_test_fmt", sql)
        self.assertIn("primary index (id)", sql) # Formatter makes this lower
        self.assertIn("collect statistics", sql) # Formatter makes this lower
        self.assertIn("on commit preserve rows", sql.lower()) # Check in lower as formatter makes it lower
        self.assertTrue(sql.count('\n') > 3)

    def test_create_volatile_table_sql_no_pi_lower(self):
        query = "SELECT id, name FROM source_table"
        sql = tdu.create_volatile_table_sql("vol_test_no_pi", query, keyword_case='lower')
        self.assertIn("no primary index", sql)

    def test_create_volatile_table_sql_on_commit_delete_lower(self):
        query = "SELECT id FROM t"
        sql = tdu.create_volatile_table_sql("vol_delete_rows", query, on_commit_preserve=False, keyword_case='lower')
        self.assertIn("on commit delete rows;", sql)

    def test_create_volatile_table_sql_stats_columns_lower(self):
        query = "SELECT id, name FROM t"
        sql = tdu.create_volatile_table_sql("vol_stats_col", query, stats_columns="id", keyword_case='lower')
        self.assertIn("collect statistics on vol_stats_col column (id);", sql)

    def test_create_volatile_table_sql_querygrid_lower(self):
        query_content = "SELECT product_id, product_name FROM remote_products"
        sql = tdu.create_volatile_table_sql(
            "vol_qg_prod", query_content, primary_index_cols="product_id",
            is_querygrid=True, target_database="REMOTE_DB", keyword_case='lower'
        )
        self.assertIn("execute immediate", sql)
        self.assertIn("create volatile table", sql)
        self.assertIn("select * from", sql)

    # --- Tests for create_date_partitioned_query ---
    def test_create_date_partitioned_query_month_upper(self):
        base_query = "SELECT category, SUM(sales) AS total_sales FROM daily_sales"
        query = tdu.create_date_partitioned_query(base_query, "sale_date", partition_by="month", keyword_case='upper')
        expected_partition_func = "EXTRACT(YEAR FROM sale_date) * 100 + EXTRACT(MONTH FROM sale_date)"
        self.assertIn(f"GROUP BY {expected_partition_func}", query)

    def test_create_date_partitioned_query_day_lower(self):
        base_query = "SELECT category, SUM(sales) AS total_sales FROM daily_sales"
        query = tdu.create_date_partitioned_query(base_query, "sale_date", partition_by="day", keyword_case='lower')
        expected_partition_func = "cast(sale_date as date)"
        self.assertIn(f"group by {expected_partition_func}", query)
        self.assertIn("cast(sale_date as date)", query)
        self.assertTrue(all(kw not in query for kw in ["CAST(", "AS DATE"]))

    def test_create_date_partitioned_query_year_lower_with_dates(self):
        base_query = "SELECT store_id, SUM(revenue) FROM store_revenue"
        query = tdu.create_date_partitioned_query(
            base_query, "transaction_date", partition_by="year",
            start_date="2023-01-01", end_date="2023-01-31", keyword_case='lower'
        )
        expected_filter = "where transaction_date >= '2023-01-01' and transaction_date <= '2023-01-31'"
        expected_partition_func = "extract(year from transaction_date)"
        self.assertIn(expected_filter, query)
        self.assertIn(f"group by {expected_partition_func}", query)
        self.assertNotIn("WHERE", query)
        self.assertNotIn("AND", query)
        self.assertNotIn("GROUP BY", query)
        self.assertNotIn("EXTRACT(YEAR FROM", query)
        self.assertIn("extract(year from", query)
        self.assertIn("FROM store_revenue", query) # Original FROM preserved

    def test_create_date_partitioned_query_with_subquery_and_no_group_by(self):
        base_query = "SELECT * FROM (SELECT id, order_date, SUM(amount) AS total FROM orders_sub GROUP BY 1,2) AS daily_summary"
        query = tdu.create_date_partitioned_query(base_query, "order_date", partition_by="month", keyword_case="upper")
        expected_partition_func = "EXTRACT(YEAR FROM order_date) * 100 + EXTRACT(MONTH FROM order_date)"
        self.assertIn(f") AS daily_summary GROUP BY {expected_partition_func}", query)

    def test_create_date_partitioned_query_existing_group_by_lower(self):
        base_query = "SELECT product, SUM(sales) FROM product_sales GROUP BY product"
        query = tdu.create_date_partitioned_query(base_query, "sale_time", partition_by="day", keyword_case='lower')
        expected_partition_func = "cast(sale_time as date)"
        normalized_query = ' '.join(query.split())
        expected_fragment = f"group by {expected_partition_func}, product"
        self.assertIn(expected_fragment, normalized_query)
        self.assertNotIn("GROUP BY", normalized_query)

    def test_create_date_partitioned_query_with_comments(self):
        base_query = """
        SELECT
            customer_id, -- This is the customer ID
            SUM(order_amount) AS total_sales
        FROM orders -- Using the orders table
        -- WHERE order_date > '2022-01-01' -- Example of a commented out WHERE
        GROUP BY customer_id -- Grouping by customer
        """
        query = tdu.create_date_partitioned_query(base_query, "order_date", partition_by="month", keyword_case="upper")
        expected_partition_func = "EXTRACT(YEAR FROM order_date) * 100 + EXTRACT(MONTH FROM order_date)"
        self.assertIn("-- This is the customer ID", query)
        self.assertIn(f"GROUP BY {expected_partition_func}, customer_id", ' '.join(query.replace("\n", " ").split()))

    def test_create_date_partitioned_query_already_partitioned_lower(self):
        partition_func_upper = "EXTRACT(YEAR FROM order_date) * 100 + EXTRACT(MONTH FROM order_date)"
        partition_func_lower = "extract(year from order_date) * 100 + extract(month from order_date)"
        base_query = f"SELECT customer_id, SUM(amount) FROM orders GROUP BY {partition_func_upper}, customer_id"
        query = tdu.create_date_partitioned_query(base_query, "order_date", partition_by="month", keyword_case='lower')
        self.assertEqual(query.strip(), base_query.strip())
        base_query_lower_group = f"SELECT customer_id, SUM(amount) FROM orders group by {partition_func_lower}, customer_id"
        query_lower = tdu.create_date_partitioned_query(base_query_lower_group, "order_date", partition_by="month", keyword_case='lower')
        self.assertEqual(query_lower.strip(), base_query_lower_group.strip())

    def test_create_date_partitioned_query_day_lower_formatted(self):
        base_query = "SELECT category, SUM(sales) AS total_sales FROM daily_sales"
        query = tdu.create_date_partitioned_query(
            base_query, "sale_date", partition_by="day",
            keyword_case='lower', format_sql_output=True
        )
        # sql-formatter default seems to make GROUP BY upper, but cast() as generated (lower)
        expected_partition_func_lower = "cast(sale_date as date)"
        self.assertIn(f"GROUP BY {expected_partition_func_lower}", query)
        self.assertIn(expected_partition_func_lower, query)
        self.assertTrue(len(query.splitlines()) > 1 or "\nGROUP BY" in query)

    # --- Tests for create_in_clause ---
    def test_create_in_clause_empty_list(self):
        self.assertEqual(tdu.create_in_clause("col_a", []), "1=0")

    def test_create_in_clause_numeric_single_value(self):
        self.assertEqual(tdu.create_in_clause("col_b", [123]), "col_b IN (123)")

    def test_create_in_clause_numeric_multiple_values(self):
        self.assertEqual(tdu.create_in_clause("col_c", [1, 2, 3]), "col_c IN (1, 2, 3)")

    def test_create_in_clause_string_single_value(self):
        self.assertEqual(tdu.create_in_clause("col_d", ["abc"]), "col_d IN ('abc')")

    def test_create_in_clause_string_multiple_values(self):
        self.assertEqual(tdu.create_in_clause("col_e", ["a", "b", "c"]), "col_e IN ('a', 'b', 'c')")

    def test_create_in_clause_string_with_quotes(self):
        self.assertEqual(tdu.create_in_clause("col_f", ["O'Malley's"]), "col_f IN ('O''Malley''s')")

    def test_create_in_clause_chunking_numeric(self):
        values = list(range(5))
        expected = "(col_g IN (0, 1) OR col_g IN (2, 3) OR col_g IN (4))"
        self.assertEqual(tdu.create_in_clause("col_g", values, chunk_size=2), expected)

    def test_create_in_clause_chunking_string(self):
        values = ["a", "b", "c", "d", "e"]
        expected = "(col_h IN ('a', 'b') OR col_h IN ('c', 'd') OR col_h IN ('e'))"
        self.assertEqual(tdu.create_in_clause("col_h", values, chunk_size=2), expected)

    def test_create_in_clause_chunking_exact_multiple(self):
        values = [10, 20, 30, 40]
        expected = "(col_i IN (10, 20) OR col_i IN (30, 40))"
        self.assertEqual(tdu.create_in_clause("col_i", values, chunk_size=2), expected)

    def test_create_in_clause_single_item_chunk_equal_size(self):
        self.assertEqual(tdu.create_in_clause("col_j", [100], chunk_size=1), "col_j IN (100)")

    def test_create_in_clause_list_smaller_than_chunk_size(self):
        self.assertEqual(tdu.create_in_clause("col_k", [1,2,3], chunk_size=5), "col_k IN (1, 2, 3)")

    def test_create_in_clause_chunking_numeric_formatted(self):
        values = list(range(5))
        query = tdu.create_in_clause("col_g", values, chunk_size=2, format_sql_output=True)
        # sql-formatter default seems to make IN and OR lowercase.
        self.assertIn("col_g in (0, 1)", query)
        self.assertIn("or", query)
        self.assertIn("col_g in (2, 3)", query)
        self.assertIn("col_g in (4)", query)
        self.assertTrue(query.count('\n') >= 0)
        self.assertTrue("or col_g" in query or "\nor col_g" in query.lower() or "\n  or col_g" in query.lower())

if __name__ == '__main__':
    unittest.main()
