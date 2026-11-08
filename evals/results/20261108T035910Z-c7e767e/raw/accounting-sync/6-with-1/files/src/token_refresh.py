"""OAuth token refresh for the accounting connection."""

import time


def call_with_refresh(conn, api, request):
    if conn.access_token_expired():
        tokens = api.refresh(conn.refresh_token)
        # Refresh tokens rotate: persist the new one before anything else uses
        # it, so a failing API call or a crash cannot lose it.
        conn.access_token = tokens["access_token"]
        conn.refresh_token = tokens["refresh_token"]
        expires_in = tokens.get("x_refresh_token_expires_in")
        if expires_in is not None:
            # Lets the product warn the customer before the connection lapses.
            conn.refresh_token_expires_at = time.time() + int(expires_in)
        conn.save()
    return api.call(request, conn.access_token)
