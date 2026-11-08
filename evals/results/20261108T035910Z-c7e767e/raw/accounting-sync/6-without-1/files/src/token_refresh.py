"""OAuth token refresh for the accounting connection."""

def call_with_refresh(conn, api, request):
    if conn.access_token_expired():
        tokens = api.refresh(conn.refresh_token)
        conn.access_token = tokens["access_token"]
        # Refresh tokens rotate: the old one is dead now. Persist the new one
        # before anything else can fail, or the connection is lost.
        conn.refresh_token = tokens["refresh_token"]
        conn.save()
        return api.call(request, conn.access_token)
    return api.call(request, conn.access_token)
