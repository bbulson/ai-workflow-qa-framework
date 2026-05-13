from framework.db_integrity import _is_pg, _fetchall, _execute


def seed_orders(conn, orders):
    """Insert a batch of (order_id, user_id, amount) tuples into orders."""
    if not orders:
        return  # Prevents accidental empty inserts from doing unnecessary work.

    if _is_pg(conn):
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO orders (order_id, user_id, amount) VALUES (%s, %s, %s)",
                orders
            )
    else:
        conn.executemany(
            "INSERT INTO orders (order_id, user_id, amount) VALUES (?, ?, ?)",
            orders
        )
    conn.commit()


def clear_orders(conn):
    """Delete all rows from the orders table."""
    _execute(conn, "DELETE FROM orders")
    conn.commit()


def find_duplicate_order_ids(conn):
    """Return rows where order_id appears more than once."""
    return _fetchall(conn, """
        SELECT order_id, COUNT(*) AS cnt
        FROM orders
        GROUP BY order_id
        HAVING COUNT(*) > 1
    """)
