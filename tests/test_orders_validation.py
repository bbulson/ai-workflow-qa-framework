from framework.db_utils import seed_orders, find_duplicate_order_ids

def test_no_duplicate_order_ids(db_conn):
    seed_orders(db_conn, [
        (1001, 1, 50.0),
        (1002, 2, 75.0),
    ])

    duplicates = find_duplicate_order_ids(db_conn)

    assert len(duplicates) == 0

def test_detect_duplicate_order_ids(db_conn):
    # Arrange: insert duplicate order_ids
    seed_orders(db_conn, [
        (1001, 1, 50.0),
        (1001, 2, 75.0),  # duplicate
        (1002, 3, 20.0),
    ])

    # Act: run validation query
    duplicates = find_duplicate_order_ids(db_conn)

    # Assert: duplicates should be detected
    assert len(duplicates) > 0
    assert duplicates[0]["order_id"] == 1001
