def seed_orders(conn, orders):
    if not orders:
        return
#Prevents accidental empty inserts from doing unnecessary work.
    conn.executemany(
        "INSERT INTO orders (order_id, user_id, amount) VALUES (?, ?, ?)",
        orders
    )
    conn.commit()

def clear_orders(conn):
    conn.execute("DELETE FROM orders")
    conn.commit()


def find_duplicate_order_ids(conn):
    return conn.execute("""
        SELECT order_id, COUNT(*)
        FROM orders
        GROUP BY order_id
        HAVING COUNT(*) > 1
    """).fetchall()