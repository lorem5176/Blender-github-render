#!/usr/bin/env python3
"""
Uploads rendered Blender animations directly to Google Drive.
Uses standard library urllib (zero third-party dependencies).
Supports OAuth 2.0 Refresh Tokens for personal (@gmail.com) Google Drive accounts.
Uploads directly into your designated Google Drive folder.
"""

import sys
import os
import json
import base64
import urllib.request
import urllib.parse
import urllib.error

# Default destination folder provided by user: 'Rendered Videos'
DEFAULT_FOLDER_ID = "15BqDdaLMcOVDVeob6Xg-pQesPSeSIveY"


def parse_credentials():
    """Extracts client_id, client_secret, refresh_token, folder_id from env."""
    client_id = os.environ.get("GDRIVE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GDRIVE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GDRIVE_REFRESH_TOKEN", "").strip()
    folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip() or DEFAULT_FOLDER_ID

    # Check combined secret GDRIVE_CREDENTIALS
    combined = os.environ.get("GDRIVE_CREDENTIALS", "").strip()
    if combined:
        try:
            # Try plain JSON
            data = json.loads(combined)
        except Exception:
            try:
                # Try Base64-decoded JSON
                decoded = base64.b64decode(combined).decode("utf-8")
                data = json.loads(decoded)
            except Exception:
                data = {}

        if isinstance(data, dict):
            client_id = data.get("client_id") or client_id
            client_secret = data.get("client_secret") or client_secret
            refresh_token = data.get("refresh_token") or refresh_token
            folder_id = data.get("folder_id") or folder_id

    if not folder_id:
        folder_id = DEFAULT_FOLDER_ID

    if not (client_id and client_secret and refresh_token):
        return None

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "folder_id": folder_id
    }


def refresh_access_token(creds):
    """Exchanges refresh token for a fresh Google Drive access token."""
    token_url = "https://oauth2.googleapis.com/token"
    payload = urllib.parse.urlencode({
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type": "refresh_token"
    }).encode("utf-8")

    req = urllib.request.Request(token_url, data=payload, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "BlenderGitHubRender/1.0"
    })

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("access_token")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        print(f"[GDrive] Error refreshing access token (HTTP {e.code}): {err_msg}")
        return None
    except Exception as e:
        print(f"[GDrive] Network error refreshing token: {e}")
        return None


def get_clean_upload_name(target_file):
    """Generates a descriptive filename like Lion_run12.mp4 based on project and run number."""
    final_dir = os.path.dirname(target_file)
    meta_path = os.path.join(final_dir, "render_metadata.json")
    base_name = os.path.basename(target_file)
    ext = os.path.splitext(base_name)[1]

    project_stem = None
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as fp:
                meta = json.load(fp)
                pname = meta.get("project_name", "")
                if pname:
                    project_stem = os.path.splitext(pname)[0]
        except Exception:
            pass

    run_num = os.environ.get("GITHUB_RUN_NUMBER", "").strip()
    if project_stem:
        if run_num:
            return f"{project_stem}_run{run_num}{ext}"
        return f"{project_stem}_rendered{ext}"
    elif run_num and base_name == "rendered_animation.mp4":
        return f"animation_run{run_num}{ext}"
    return base_name


def upload_file_resumable(access_token, file_path, folder_id=None, custom_name=None):
    """Uploads large files in chunks using Google Drive Resumable Upload protocol."""
    file_size = os.path.getsize(file_path)
    file_name = custom_name or os.path.basename(file_path)

    ext = os.path.splitext(file_name)[1].lower()
    if ext == ".mp4":
        mime_type = "video/mp4"
    elif ext == ".zip":
        mime_type = "application/zip"
    else:
        mime_type = "application/octet-stream"

    # 1. Initiate resumable upload session
    init_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable"
    metadata = {"name": file_name}
    if folder_id:
        metadata["parents"] = [folder_id]

    init_body = json.dumps(metadata).encode("utf-8")
    init_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": mime_type,
        "X-Upload-Content-Length": str(file_size),
        "User-Agent": "BlenderGitHubRender/1.0"
    }

    req = urllib.request.Request(init_url, data=init_body, headers=init_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            upload_url = resp.headers.get("Location")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        print(f"[GDrive] Failed to initiate upload (HTTP {e.code}): {err_body}")
        return None

    if not upload_url:
        print("[GDrive] Error: No Location header returned for resumable upload.")
        return None

    # 2. Upload content in 8 MB chunks
    chunk_size = 8 * 1024 * 1024
    offset = 0

    print(f"[GDrive] Uploading to Google Drive folder: {folder_id}")
    print(f"[GDrive] Starting upload: {file_name} ({file_size / (1024 * 1024):.2f} MB)...")

    with open(file_path, "rb") as fp:
        while offset < file_size:
            chunk = fp.read(chunk_size)
            chunk_len = len(chunk)
            end_byte = offset + chunk_len - 1

            chunk_headers = {
                "Content-Length": str(chunk_len),
                "Content-Range": f"bytes {offset}-{end_byte}/{file_size}",
                "User-Agent": "BlenderGitHubRender/1.0"
            }

            chunk_req = urllib.request.Request(upload_url, data=chunk, headers=chunk_headers, method="PUT")
            try:
                with urllib.request.urlopen(chunk_req, timeout=120) as resp:
                    if resp.status in (200, 201):
                        result = json.loads(resp.read().decode("utf-8"))
                        return result
            except urllib.error.HTTPError as e:
                # 308 Resume Incomplete is the normal response for non-final chunks
                if e.code == 308:
                    pass
                else:
                    err_msg = e.read().decode("utf-8", errors="ignore")
                    print(f"[GDrive] Upload chunk error (HTTP {e.code}): {err_msg}")
                    return None
            except Exception as e:
                print(f"[GDrive] Network error during chunk upload: {e}")
                return None

            offset += chunk_len
            percent = int((offset / file_size) * 100)
            print(f"  ⬆️ Upload progress: {percent}% ({offset / (1024 * 1024):.1f}/{file_size / (1024 * 1024):.1f} MB)")

    return None


def get_file_link(access_token, file_id):
    """Retrieves webViewLink for the uploaded file."""
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=id,name,webViewLink"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "BlenderGitHubRender/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
    except Exception:
        return f"https://drive.google.com/file/d/{file_id}/view"


def make_publicly_viewable(access_token, file_id):
    """Sets permission so anyone with the link can view (optional)."""
    perm_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions"
    body = json.dumps({"role": "reader", "type": "anyone"}).encode("utf-8")
    req = urllib.request.Request(perm_url, data=body, headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception:
        pass


def main():
    target_file = sys.argv[1] if len(sys.argv) > 1 else "final_output/rendered_animation.mp4"

    # Fallback to frames zip if video file does not exist
    if not os.path.exists(target_file):
        alt_zip = os.path.join(os.path.dirname(target_file), "all_rendered_frames.zip")
        if os.path.exists(alt_zip):
            target_file = alt_zip
        else:
            print(f"[GDrive] Target file {target_file} not found. Skipping Google Drive upload.")
            sys.exit(0)

    creds = parse_credentials()
    if not creds:
        print("""
======================================================================
  ℹ️  Google Drive Upload: Not Configured (Skipped)
======================================================================
  Your video was successfully rendered and is available in Artifacts!
  
  To have rendered videos automatically upload to your Google Drive:
  1. Run `python3 setup_gdrive_auth.py` on your computer (takes 2 minutes).
  2. Add the resulting secret to your GitHub Repository Secrets:
     Settings -> Secrets and variables -> Actions -> New secret
     Name: GDRIVE_CREDENTIALS
======================================================================
""")
        sys.exit(0)

    print("[GDrive] Authenticating with Google Drive API...")
    token = refresh_access_token(creds)
    if not token:
        print("⚠️ Warning: Failed to obtain Google Drive access token. Skipping upload.")
        sys.exit(0)

    upload_name = get_clean_upload_name(target_file)
    upload_result = upload_file_resumable(token, target_file, creds["folder_id"], custom_name=upload_name)
    if not upload_result or "id" not in upload_result:
        print("⚠️ Warning: Upload to Google Drive did not complete. Artifact remains in GitHub.")
        sys.exit(0)

    file_id = upload_result["id"]
    file_name = upload_result.get("name", upload_name)
    size_mb = os.path.getsize(target_file) / (1024 * 1024)
    folder_id = creds["folder_id"]
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"

    # Make viewable with link
    make_publicly_viewable(token, file_id)
    drive_link = get_file_link(token, file_id)

    print(f"""
======================================================================
  🎉 GOOGLE DRIVE UPLOAD COMPLETE!
======================================================================
  📁 File Name:     {file_name}
  💾 File Size:     {size_mb:.2f} MB
  📂 Target Folder: Rendered Videos ({folder_url})
  🔗 Video Link:    {drive_link}
======================================================================
""")

    # Save links locally so summarize_video.py can include them
    final_dir = os.path.dirname(target_file)
    link_file = os.path.join(final_dir, "gdrive_link.txt")
    try:
        with open(link_file, "w") as fp:
            fp.write(f"{drive_link}\n{folder_url}\n{file_name}")
    except Exception:
        pass

    # Export to GitHub Step Summary
    summary_env = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_env:
        with open(summary_env, "a") as fp:
            fp.write(f"""
### ☁️ Watch / Download on Google Drive
👉 **[Open {file_name} in Google Drive]({drive_link})**  
📂 **[Open 'Rendered Videos' Folder in Drive]({folder_url})**
""")

    # Export to GitHub Output
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fp:
            fp.write(f"drive_link={drive_link}\n")
            fp.write(f"drive_folder_url={folder_url}\n")
            fp.write(f"drive_file_id={file_id}\n")


if __name__ == "__main__":
    main()
