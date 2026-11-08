"""Loyalty points: earned on purchases, redeemed at checkout."""
def earn(db, user_id, points):
    db.execute("UPDATE users SET points = points + %s WHERE id = %s", (points, user_id))


def redeem(db, user_id, points):
    db.execute("UPDATE users SET points = points - %s WHERE id = %s", (points, user_id))
