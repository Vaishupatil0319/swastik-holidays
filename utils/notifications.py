from database.db import get_connection

def add_notification(title, message):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO notifications (title, message)
        VALUES (%s, %s)
        """,
        (title, message)
    )

    conn.commit()

    cursor.close()
    conn.close()