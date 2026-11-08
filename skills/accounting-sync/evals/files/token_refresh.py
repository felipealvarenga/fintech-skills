"""OAuth token refresh for the accounting connection."""

def call_with_refresh(conn, api, request):
    if conn.access_token_expired():
        tokens = api.refresh(conn.refresh_token)
        conn.access_token = tokens["access_token"]
        response = api.call(request, conn.access_token)
        conn.refresh_token = tokens["refresh_token"]
        conn.save()
        return response
    return api.call(request, conn.access_token)
