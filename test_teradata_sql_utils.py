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
        self.assertEqual(query.strip(), expected)

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
        # Regex is case insensitive for finding WHERE, but our new AND should be upper
        # Expected: SELECT * FROM sales WHERE sale_date >= '2023-01-01' AND product_id = 100
        # Actual logic inserts " sale_date >= '2023-01-01' AND" after original WHERE
        self.assertIn("WHERE sale_date >= '2023-01-01' AND product_id = 100", query.replace("  ", " "))

    def test_create_date_filtered_query_with_existing_where_lower(self):
        base_query = "SELECT * FROM sales WHERE product_id = 100" # Original WHERE is upper
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01", keyword_case='lower')
        # Expected: SELECT * FROM sales where sale_date >= '2023-01-01' and product_id = 100
        # The original WHERE is preserved, new keywords are lower.
        self.assertIn("WHERE sale_date >= '2023-01-01' and product_id = 100", query.replace("  ", " "))


    def test_create_date_filtered_query_with_existing_where_and_group_by_lower(self):
        base_query = "SELECT product_id, SUM(amount) FROM sales WHERE category = 'electronics' GROUP BY product_id"
        query = tdu.create_date_filtered_query(base_query, "order_date", start_date="2024-01-01", keyword_case='lower')
        expected_core = "WHERE order_date >= '2024-01-01' and category = 'electronics'"
        self.assertIn(expected_core, query.replace("  ", " "))
        self.assertNotIn("AND", query) # The new 'and' should be lowercase.


    def test_create_date_filtered_query_with_group_by_no_where_lower(self):
        base_query = "SELECT product_id, SUM(amount) FROM sales GROUP BY product_id"
        query = tdu.create_date_filtered_query(base_query, "order_date", start_date="2024-01-01", keyword_case='lower')
        expected = "SELECT product_id, SUM(amount) FROM sales where order_date >= '2024-01-01' GROUP BY product_id"
        self.assertIn("where order_date >= '2024-01-01' GROUP BY", query.replace("  ", " "))

    def test_create_date_filtered_query_with_semicolon_lower(self):
        base_query = "SELECT * FROM sales;"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01", keyword_case='lower')
        expected = "SELECT * FROM sales where sale_date >= '2023-01-01';"
        self.assertEqual(query.strip(), expected)

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
        query_content = "select id, name from source_table" # inner query can be any case
        sql = tdu.create_volatile_table_sql("vol_test_lower", query_content, primary_index_cols="id", keyword_case='lower')
        self.assertIn("drop table vol_test_lower;", sql)
        self.assertIn("create volatile table vol_test_lower as (", sql)
        self.assertIn(query_content, sql) # Check that original query is preserved
        self.assertIn("with data primary index (id)", sql)
        self.assertIn("on commit preserve rows;", sql)
        self.assertIn("collect statistics on vol_test_lower;", sql)
        self.assertIn("begin", sql)
        self.assertIn("declare continue handler for sqlstate", sql)
        self.assertIn("end;", sql)


    def test_create_volatile_table_sql_no_pi_lower(self):
        query = "SELECT id, name FROM source_table"
        sql = tdu.create_volatile_table_sql("vol_test_no_pi", query, keyword_case='lower')
        self.assertIn("no primary index", sql)

    def test_create_volatile_table_sql_on_commit_delete_lower(self):
        query = "SELECT id FROM t"
        sql = tdu.create_volatile_table_sql("vol_delete_rows", query, on_commit_preserve=False, keyword_case='lower')
        self.assertIn("on commit delete rows;", sql)
        self.assertNotIn("on commit preserve rows;", sql.lower()) # Check against lower to be sure

    def test_create_volatile_table_sql_stats_columns_lower(self):
        query = "SELECT id, name FROM t"
        sql = tdu.create_volatile_table_sql("vol_stats_col", query, stats_columns="id", keyword_case='lower')
        self.assertIn("collect statistics on vol_stats_col column (id);", sql)

    def test_create_volatile_table_sql_querygrid_lower(self):
        query_content = "SELECT product_id, product_name FROM remote_products"
        sql = tdu.create_volatile_table_sql(
            "vol_qg_prod",
            query_content,
            primary_index_cols="product_id",
            is_querygrid=True,
            target_database="REMOTE_DB",
            keyword_case='lower'
        )
        self.assertIn("execute immediate", sql)
        self.assertIn(query_content, sql)
        self.assertIn("on REMOTE_DB", sql) # Target DB name case preserved
        self.assertIn("as QueryGridResult", sql) # Alias preserved
        self.assertIn("create volatile table", sql)
        self.assertIn("select * from", sql)


    def test_create_date_partitioned_query_month_upper(self):
        base_query = "SELECT category, SUM(sales) AS total_sales FROM daily_sales"
        query = tdu.create_date_partitioned_query(base_query, "sale_date", partition_by="month", keyword_case='upper')
        expected_partition_func = "EXTRACT(YEAR FROM sale_date) * 100 + EXTRACT(MONTH FROM sale_date)"
        expected = f"{base_query} GROUP BY {expected_partition_func}"
        self.assertIn(f"GROUP BY {expected_partition_func}", query)

    def test_create_date_partitioned_query_day_lower(self):
        base_query = "SELECT category, SUM(sales) AS total_sales FROM daily_sales"
        query = tdu.create_date_partitioned_query(base_query, "sale_date", partition_by="day", keyword_case='lower')
        expected_partition_func = "cast(sale_date as date)"
        self.assertIn(f"group by {expected_partition_func}", query)
        self.assertIn("cast(sale_date as date)", query) # Check function itself
        # Check that keywords *within the generated partition function* are lowercase
        self.assertTrue(all(kw not in query for kw in ["CAST(", "AS DATE"]))


    def test_create_date_partitioned_query_year_lower_with_dates(self):
        base_query = "SELECT store_id, SUM(revenue) FROM store_revenue" # User query has uppercase FROM
        query = tdu.create_date_partitioned_query(
            base_query, "transaction_date", partition_by="year",
            start_date="2023-01-01", end_date="2023-01-31", keyword_case='lower'
        )
        expected_filter = "where transaction_date >= '2023-01-01' and transaction_date <= '2023-01-31'"
        expected_partition_func = "extract(year from transaction_date)"

        self.assertIn(expected_filter, query) # Check generated where/and
        self.assertIn(f"group by {expected_partition_func}", query) # Check generated group by

        # Check keywords from the utility are lowercase
        self.assertNotIn("WHERE", query) # Util-generated WHERE should be lower
        self.assertNotIn("AND", query)   # Util-generated AND should be lower
        self.assertNotIn("GROUP BY", query) # Util-generated GROUP BY should be lower

        # Check keywords *within the generated partition function* are lowercase
        # e.g. extract(year from transaction_date)
        # We should not find "EXTRACT(", "YEAR ", "FROM " if they were cased by util
        self.assertNotIn("EXTRACT(YEAR FROM", query) # More specific check for generated part
        self.assertIn("extract(year from", query)

        # Ensure user's original FROM (from base_query) is preserved
        self.assertIn("FROM store_revenue", query)


    def test_create_date_partitioned_query_existing_group_by_lower(self):
        base_query = "SELECT product, SUM(sales) FROM product_sales GROUP BY product" # Original GROUP BY is upper
        query = tdu.create_date_partitioned_query(base_query, "sale_time", partition_by="day", keyword_case='lower')
        expected_partition_func = "cast(sale_time as date)"
        normalized_query = ' '.join(query.split())
        # The new GROUP BY keyword should be lower, existing content follows.
        expected_fragment = f"group by {expected_partition_func}, product"
        self.assertIn(expected_fragment, normalized_query)
        self.assertNotIn("GROUP BY", normalized_query) # Ensure original GROUP BY was replaced/formatted

    def test_create_date_partitioned_query_already_partitioned_lower(self):
        # Test that if the exact partition function is already in GROUP BY, it's not added again
        # and keyword case of original query is preserved if no changes made to that part.
        partition_func_upper = "EXTRACT(YEAR FROM order_date) * 100 + EXTRACT(MONTH FROM order_date)"
        partition_func_lower = "extract(year from order_date) * 100 + extract(month from order_date)"
        base_query = f"SELECT customer_id, SUM(amount) FROM orders GROUP BY {partition_func_upper}, customer_id"
        query = tdu.create_date_partitioned_query(base_query, "order_date", partition_by="month", keyword_case='lower')
        # Since the function is already there (checked case-insensitively), the query should be unchanged.
        # The check for `partition_func.lower() not in existing_group_by_clauses.lower()` should prevent modification.
        self.assertEqual(query.strip(), base_query.strip())
        # Also test if the base query had it in lower, it should also be unchanged.
        base_query_lower_group = f"SELECT customer_id, SUM(amount) FROM orders group by {partition_func_lower}, customer_id"
        query_lower = tdu.create_date_partitioned_query(base_query_lower_group, "order_date", partition_by="month", keyword_case='lower')
        self.assertEqual(query_lower.strip(), base_query_lower_group.strip())

    # Tests for create_in_clause (These should not be affected by keyword_case, but good to keep them separate)
    def test_create_in_clause_empty_list(self):
        # Count occurrences of the partition function string
        self.assertEqual(query.count(partition_func), 1, "Partition function should not be duplicated in GROUP BY")

    # Tests for create_in_clause
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
        # chunk_size of 2 should create 3 chunks: (0,1), (2,3), (4)
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


if __name__ == '__main__':
    unittest.main()
