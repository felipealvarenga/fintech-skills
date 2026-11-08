"""OAuth token refresh for the accounting connection."""

def call_with_refresh(conn, api, request):
    if conn.access_token_expired():
        tokens = api.refresh(conn.refresh_token)
        conn.access_token = tokens["access_token"]
        # QuickBooks rotates the refresh token on every refresh; the old one
        # is soon invalid. Persist the new pair before doing anything that
        # can fail, or a failed API call loses the only valid token.
        conn.refresh_token = tokens["refresh_token"]
        conn.save()
    return api.call(request, conn.access_token)
