#!/usr/bin/env python3
"""
Interactive setup helper for Google Drive integration.
Run this script ONCE on your Mac/PC to authorize Google Drive upload:
    python3 setup_gdrive_auth.py
"""

import sys
import os
import json
import base64
import urllib.request
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

REDIRECT_PORT = 8085
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/"
SCOPE = "https://www.googleapis.com/auth/drive.file"

auth_code = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed_url = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed_url.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <html>
            <head><title>Authorization Successful</title></head>
            <body style="font-family: -apple-system, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #2e7d32;">✅ Google Drive Authorization Successful!</h1>
                <p style="font-size: 18px;">You can now close this browser tab and return to your terminal.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization failed or cancelled.</h1>")

    def log_message(self, format, *args):
        # Silence HTTP server access logs in terminal
        pass


def exchange_code_for_tokens(client_id, client_secret, code):
    token_url = "https://oauth2.googleapis.com/token"
    payload = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }).encode("utf-8")

    req = urllib.request.Request(token_url, data=payload, headers={
        "Content-Type": "application/x-www-form-urlencoded"
    })

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    print("=" * 70)
    print("  🎨 Google Drive Setup for Blender GitHub Render Farm")
    print("=" * 70)
    print("""
This 2-minute setup connects your Google Drive so that every time a video
is rendered on GitHub Actions, it automatically uploads directly to your Drive!

📋 Prerequisites (Google Cloud Console - 100% Free):
  1. Open: https://console.cloud.google.com/
  2. Create a project (e.g. "Blender Farm").
  3. Go to 'APIs & Services' -> 'Library' -> Search 'Google Drive API' -> Click 'Enable'.
  4. Go to 'APIs & Services' -> 'OAuth consent screen':
     - Choose 'External', enter an App name (e.g. "Blender Farm"), and your email.
     - Click 'Save and Continue'.
  5. Go to 'APIs & Services' -> 'Credentials' -> 'Create Credentials' -> 'OAuth client ID':
     - Application type: 'Web application' (or 'Desktop app')
     - Authorized redirect URIs: add 'http://localhost:8085/'
     - Click 'Create'.
""")
    print("=" * 70)

    # Prompt user for credentials or JSON file
    inp = input("👉 Enter your Client ID (or drag your client_secret.json file here): ").strip().strip("'\"")
    client_id = ""
    client_secret = ""

    if os.path.exists(inp) and os.path.isfile(inp):
        try:
            with open(inp, "r") as fp:
                data = json.load(fp)
            creds_data = data.get("installed") or data.get("web") or data
            client_id = creds_data.get("client_id", "")
            client_secret = creds_data.get("client_secret", "")
            print(f"✅ Loaded credentials from {os.path.basename(inp)}")
        except Exception as e:
            print(f"Error reading JSON file: {e}")

    if not client_id:
        client_id = inp
        client_secret = input("👉 Enter your Client Secret: ").strip().strip("'\"")

    if not client_id or not client_secret:
        print("❌ Error: Client ID and Client Secret are required.")
        sys.exit(1)

    # Ask for optional folder ID
    folder_input = input("👉 (Optional) Google Drive Folder ID to upload into (Press ENTER for Drive root): ").strip()

    # Build OAuth URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(auth_params)

    print("\n🌐 Opening your browser to sign in with Google...")
    print(f"If the browser doesn't open automatically, copy this link:\n{auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    # Start local server to capture redirect
    server = HTTPServer(("localhost", REDIRECT_PORT), OAuthCallbackHandler)
    print("⏳ Waiting for authorization in browser...")
    while auth_code is None:
        server.handle_request()

    print("\n🔄 Exchanging code for permanent Refresh Token...")
    try:
        tokens = exchange_code_for_tokens(client_id, client_secret, auth_code)
    except Exception as e:
        print(f"❌ Failed to exchange code for token: {e}")
        sys.exit(1)

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("⚠️ Warning: No refresh token returned. (Try re-running with prompt=consent)")
        sys.exit(1)

    combined_secret = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "folder_id": folder_input if folder_input else ""
    }
    combined_json = json.dumps(combined_secret)

    print("\n" + "=" * 70)
    print("  🎉 GOOGLE DRIVE AUTHENTICATION COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print("""
Now add this secret to your GitHub repository so GitHub Actions can upload:

1. Open your GitHub Repository in your browser:
   https://github.com/lorem5176/Blender-github-render

2. Go to:
   Settings ⚙️ -> Secrets and variables -> Actions -> 'New repository secret'

3. Create the secret:
   - Name:  GDRIVE_CREDENTIALS
   - Value: (copy and paste the JSON below)
""")
    print("----------------------------------------------------------------------")
    print(combined_json)
    print("----------------------------------------------------------------------")
    print("""
That's it! Every future render will automatically upload directly to your Google Drive!
""")
    print("=" * 70)


if __name__ == "__main__":
    main()
