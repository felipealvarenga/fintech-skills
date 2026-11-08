"""OAuth token refresh for the accounting connection."""
import time


def call_with_refresh(conn, api, request):
    if conn.access_token_expired():
        tokens = api.refresh(conn.refresh_token)
        # QuickBooks rotates the refresh token: the old one is dead now.
        # Persist the new one (and its expiry) in a single save BEFORE
        # anything else can fail.
        conn.access_token = tokens["access_token"]
        conn.refresh_token = tokens["refresh_token"]
        expires_in = tokens.get("x_refresh_token_expires_in")
        if expires_in is not None:
            conn.refresh_token_expires_at = time.time() + int(expires_in)
        conn.save()
    return api.call(request, conn.access_token)
