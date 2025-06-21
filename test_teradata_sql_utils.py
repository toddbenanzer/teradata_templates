import unittest
import teradata_sql_utils as tdu

class TestTeradataSQLUtils(unittest.TestCase):

    def test_create_date_filtered_query_no_dates(self):
        base_query = "SELECT * FROM sales"
        query = tdu.create_date_filtered_query(base_query, "sale_date")
        self.assertEqual(query.strip(), base_query)

    def test_create_date_filtered_query_start_date_only(self):
        base_query = "SELECT * FROM sales"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01")
        expected = "SELECT * FROM sales WHERE sale_date >= '2023-01-01'"
        self.assertEqual(query.strip(), expected)

    def test_create_date_filtered_query_end_date_only(self):
        base_query = "SELECT * FROM sales"
        query = tdu.create_date_filtered_query(base_query, "sale_date", end_date="2023-12-31")
        expected = "SELECT * FROM sales WHERE sale_date <= '2023-12-31'"
        self.assertEqual(query.strip(), expected)

    def test_create_date_filtered_query_both_dates(self):
        base_query = "SELECT * FROM sales"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01", end_date="2023-03-31")
        expected = "SELECT * FROM sales WHERE sale_date >= '2023-01-01' AND sale_date <= '2023-03-31'"
        self.assertEqual(query.strip(), expected)

    def test_create_date_filtered_query_with_existing_where(self):
        base_query = "SELECT * FROM sales WHERE product_id = 100"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01")
        expected = "SELECT * FROM sales WHERE sale_date >= '2023-01-01' AND product_id = 100"
        # Normalize spacing for comparison
        self.assertEqual(query.replace("  ", " ").strip(), expected.replace("  ", " ").strip())


    def test_create_date_filtered_query_with_existing_where_and_group_by(self):
        base_query = "SELECT product_id, SUM(amount) FROM sales WHERE category = 'electronics' GROUP BY product_id"
        query = tdu.create_date_filtered_query(base_query, "order_date", start_date="2024-01-01")
        expected = "SELECT product_id, SUM(amount) FROM sales WHERE order_date >= '2024-01-01' AND category = 'electronics' GROUP BY product_id"
        self.assertEqual(query.replace("  ", " ").strip(), expected.replace("  ", " ").strip())


    def test_create_date_filtered_query_with_group_by_no_where(self):
        base_query = "SELECT product_id, SUM(amount) FROM sales GROUP BY product_id"
        query = tdu.create_date_filtered_query(base_query, "order_date", start_date="2024-01-01")
        expected = "SELECT product_id, SUM(amount) FROM sales WHERE order_date >= '2024-01-01' GROUP BY product_id"
        self.assertEqual(query.replace("  ", " ").strip(), expected.replace("  ", " ").strip())

    def test_create_date_filtered_query_with_semicolon(self):
        base_query = "SELECT * FROM sales;"
        query = tdu.create_date_filtered_query(base_query, "sale_date", start_date="2023-01-01")
        expected = "SELECT * FROM sales WHERE sale_date >= '2023-01-01';"
        self.assertEqual(query.strip(), expected)

    def test_create_volatile_table_sql_basic(self):
        query = "SELECT id, name FROM source_table"
        sql = tdu.create_volatile_table_sql("vol_test", query, primary_index_cols="id")
        self.assertIn("DROP TABLE vol_test;", sql)
        self.assertIn("CREATE VOLATILE TABLE vol_test AS (", sql)
        self.assertIn(query, sql)
        self.assertIn("WITH DATA PRIMARY INDEX (id)", sql)
        self.assertIn("ON COMMIT PRESERVE ROWS;", sql)
        self.assertIn("COLLECT STATISTICS ON vol_test;", sql)

    def test_create_volatile_table_sql_no_pi(self):
        query = "SELECT id, name FROM source_table"
        sql = tdu.create_volatile_table_sql("vol_test_no_pi", query)
        self.assertIn("NO PRIMARY INDEX", sql)

    def test_create_volatile_table_sql_multiple_pi(self):
        query = "SELECT id, name, category FROM source_table"
        sql = tdu.create_volatile_table_sql("vol_test_multi_pi", query, primary_index_cols=["id", "category"])
        self.assertIn("PRIMARY INDEX (id, category)", sql)

    def test_create_volatile_table_sql_no_check_exists(self):
        query = "SELECT id FROM t"
        sql = tdu.create_volatile_table_sql("vol_no_check", query, check_exists=False)
        self.assertNotIn("DROP TABLE vol_no_check;", sql)

    def test_create_volatile_table_sql_no_collect_stats(self):
        query = "SELECT id FROM t"
        sql = tdu.create_volatile_table_sql("vol_no_stats", query, collect_stats=False)
        self.assertNotIn("COLLECT STATISTICS ON vol_no_stats;", sql)

    def test_create_volatile_table_sql_on_commit_delete(self):
        query = "SELECT id FROM t"
        sql = tdu.create_volatile_table_sql("vol_delete_rows", query, on_commit_preserve=False)
        self.assertIn("ON COMMIT DELETE ROWS;", sql)
        self.assertNotIn("ON COMMIT PRESERVE ROWS;", sql)

    def test_create_volatile_table_sql_stats_columns_single(self):
        query = "SELECT id, name FROM t"
        sql = tdu.create_volatile_table_sql("vol_stats_col", query, stats_columns="id")
        self.assertIn("COLLECT STATISTICS ON vol_stats_col COLUMN (id);", sql)

    def test_create_volatile_table_sql_stats_columns_multiple(self):
        query = "SELECT id, name, age FROM t"
        sql = tdu.create_volatile_table_sql("vol_stats_cols", query, stats_columns=["name", "age"])
        self.assertIn("COLLECT STATISTICS ON vol_stats_cols COLUMN (name, age);", sql)

    def test_create_volatile_table_sql_querygrid(self):
        query = "SELECT product_id, product_name FROM remote_products"
        sql = tdu.create_volatile_table_sql(
            "vol_qg_prod",
            query,
            primary_index_cols="product_id",
            is_querygrid=True,
            target_database="REMOTE_DB"
        )
        self.assertIn("EXECUTE IMMEDIATE", sql)
        self.assertIn(query, sql)
        self.assertIn("ON REMOTE_DB", sql)
        self.assertIn("AS QueryGridResult", sql)

    def test_create_date_partitioned_query_month(self):
        base_query = "SELECT category, SUM(sales) AS total_sales FROM daily_sales"
        query = tdu.create_date_partitioned_query(base_query, "sale_date", partition_by="month")
        expected_partition_func = "EXTRACT(YEAR FROM sale_date) * 100 + EXTRACT(MONTH FROM sale_date)"
        expected = f"{base_query} GROUP BY {expected_partition_func}"
        self.assertEqual(query.strip(), expected)

    def test_create_date_partitioned_query_day(self):
        base_query = "SELECT category, SUM(sales) AS total_sales FROM daily_sales"
        query = tdu.create_date_partitioned_query(base_query, "sale_date", partition_by="day")
        expected_partition_func = "CAST(sale_date AS DATE)"
        expected = f"{base_query} GROUP BY {expected_partition_func}"
        self.assertEqual(query.strip(), expected)

    def test_create_date_partitioned_query_year(self):
        base_query = "SELECT category, SUM(sales) AS total_sales FROM daily_sales"
        query = tdu.create_date_partitioned_query(base_query, "sale_date", partition_by="year")
        expected_partition_func = "EXTRACT(YEAR FROM sale_date)"
        expected = f"{base_query} GROUP BY {expected_partition_func}"
        self.assertEqual(query.strip(), expected)

    def test_create_date_partitioned_query_with_dates(self):
        base_query = "SELECT store_id, SUM(revenue) FROM store_revenue"
        query = tdu.create_date_partitioned_query(
            base_query, "transaction_date", partition_by="month", start_date="2023-01-01", end_date="2023-01-31"
        )
        expected_filter = "WHERE transaction_date >= '2023-01-01' AND transaction_date <= '2023-01-31'"
        expected_partition_func = "EXTRACT(YEAR FROM transaction_date) * 100 + EXTRACT(MONTH FROM transaction_date)"
        # Basic check, regex in actual function is more robust
        self.assertIn(expected_filter, query)
        self.assertIn(f"GROUP BY {expected_partition_func}", query)

    def test_create_date_partitioned_query_existing_group_by(self):
        base_query = "SELECT product, SUM(sales) FROM product_sales GROUP BY product"
        query = tdu.create_date_partitioned_query(base_query, "sale_time", partition_by="day")
        expected_partition_func = "CAST(sale_time AS DATE)"
        # Expecting "GROUP BY CAST(sale_time AS DATE), product"
        # The current implementation prepends the new partition.
        # Normalize query for comparison by removing multiple spaces.
        normalized_query = ' '.join(query.split())
        expected_fragment = f"GROUP BY {expected_partition_func}, product"
        self.assertIn(expected_fragment, normalized_query)


    def test_create_date_partitioned_query_invalid_partition_by(self):
        base_query = "SELECT * FROM data"
        with self.assertRaisesRegex(ValueError, "Invalid partition_by value: 'weekly'. Must be 'day', 'month', or 'year'."):
            tdu.create_date_partitioned_query(base_query, "event_date", partition_by="weekly")

    def test_create_date_partitioned_query_already_partitioned(self):
        # Test that if the exact partition function is already in GROUP BY, it's not added again
        partition_func = "EXTRACT(YEAR FROM order_date) * 100 + EXTRACT(MONTH FROM order_date)"
        base_query = f"SELECT customer_id, SUM(amount) FROM orders GROUP BY {partition_func}, customer_id"
        query = tdu.create_date_partitioned_query(base_query, "order_date", partition_by="month")
        # Count occurrences of the partition function string
        self.assertEqual(query.count(partition_func), 1, "Partition function should not be duplicated in GROUP BY")


if __name__ == '__main__':
    unittest.main()
