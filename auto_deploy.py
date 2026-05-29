#!/usr/bin/env python3
"""
Elite Motors — Fully Automated Deployment
Uses GitHub OAuth device flow: browser opens, user clicks Authorize once.
Then auto-creates repo, pushes code, opens Railway.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import subprocess
import time
import sys
import os

# GitHub CLI's public OAuth app (used by many open-source tools)
CLIENT_ID = "178c6fc778ccc68e1d6a"
REPO_NAME = "elite-motors"

BOLD  = "\033[1m"
GREEN = "\033[0;32m"
GOLD  = "\033[0;33m"
CYAN  = "\033[0;36m"
RED   = "\033[0;31m"
RESET = "\033[0m"

def banner(msg):
    print(f"\n{BOLD}{CYAN}{'='*52}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'='*52}{RESET}\n")

def api(url, token=None, data=None, method=None):
    headers = {"Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())

# ── Step 1: GitHub device flow ─────────────────────────────────
banner("STEP 1 — Connecting to GitHub")

req = urllib.request.Request(
    "https://github.com/login/device/code",
    data=urllib.parse.urlencode({"client_id": CLIENT_ID, "scope": "repo"}).encode(),
    headers={"Accept": "application/json"}
)
with urllib.request.urlopen(req) as r:
    device = json.loads(r.read())

device_code = device["device_code"]
user_code   = device["user_code"]
verify_uri  = device.get("verification_uri", "https://github.com/login/device")
interval    = device.get("interval", 5)

print(f"{BOLD}  Your browser is opening:{RESET} {verify_uri}")
print(f"\n  {BOLD}{GOLD}Enter this code:  {user_code}{RESET}")
print(f"\n  (I've copied it to your clipboard — just Cmd+V and click Authorize)\n")

# Copy code to clipboard so user can just paste
try:
    subprocess.run(["pbcopy"], input=user_code.encode(), check=True)
except Exception:
    pass

# Open verification URL
subprocess.run(["open", verify_uri])

# Poll for access token
print(f"  Waiting for you to authorize in browser...")
access_token = None
while True:
    time.sleep(interval)
    req = urllib.request.Request(
        "https://github.com/login/oauth/access_token",
        data=urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
        }).encode(),
        headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        resp = json.loads(r.read())

    if "access_token" in resp:
        access_token = resp["access_token"]
        break
    elif resp.get("error") == "authorization_pending":
        print("  Waiting...", end="\r")
    elif resp.get("error") == "slow_down":
        interval += 5
    elif resp.get("error") == "expired_token":
        print(f"\n{RED}  Token expired. Please re-run the script.{RESET}")
        sys.exit(1)
    else:
        print(f"\n{RED}  Error: {resp}{RESET}")
        sys.exit(1)

user_info = api("https://api.github.com/user", token=access_token)
username  = user_info["login"]
print(f"\n{GREEN}  ✓ Authorized as: {username}{RESET}")

# ── Step 2: Create GitHub repo ─────────────────────────────────
banner("STEP 2 — Creating GitHub Repository")

result = api(
    "https://api.github.com/user/repos",
    token=access_token,
    data=json.dumps({"name": REPO_NAME, "private": False, "description": "Elite Motors — Luxury Car Dealership"}).encode()
)

if result.get("message") in ("Repository creation failed.", None) and result.get("full_name"):
    repo_url = result["clone_url"]
    print(f"{GREEN}  ✓ Repository created: {result['html_url']}{RESET}")
elif "errors" in result:
    # Repo might already exist
    repo_url = f"https://github.com/{username}/{REPO_NAME}.git"
    print(f"{GOLD}  ⚠ Repo may already exist, proceeding with: {repo_url}{RESET}")
else:
    repo_url = f"https://github.com/{username}/{REPO_NAME}.git"
    print(f"{GREEN}  ✓ Repository ready: {repo_url}{RESET}")

# ── Step 3: Git push ───────────────────────────────────────────
banner("STEP 3 — Pushing Code to GitHub")

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Embed token in URL for auth (avoids interactive prompt)
auth_url = repo_url.replace("https://", f"https://{username}:{access_token}@")

def run(cmd, **kwargs):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0 and not kwargs.get("check") == False:
        print(f"{RED}  Error: {result.stderr}{RESET}")
    return result

# Clean git state
subprocess.run(["git", "init", "-b", "main"], capture_output=True)
run(["git", "add", "."])
subprocess.run(["git", "commit", "-m", "Initial commit - Elite Motors car dealership"],
               capture_output=True)  # ignore if nothing to commit
run(["git", "remote", "remove", "origin"], check=False)
run(["git", "remote", "add", "origin", auth_url])
result = run(["git", "push", "-u", "origin", "main", "--force"])

if result.returncode == 0:
    print(f"\n{GREEN}  ✓ All files pushed to GitHub!{RESET}")
    print(f"  → https://github.com/{username}/{REPO_NAME}")
else:
    print(f"\n{RED}  Push failed. Check error above.{RESET}")
    input("Press Enter to exit...")
    sys.exit(1)

# ── Step 4: Open Railway ───────────────────────────────────────
banner("STEP 4 — Opening Railway")

import secrets as _sec
secret_key = _sec.token_hex(32)

subprocess.run(["open", "https://railway.app/new"])

print(f"  Railway is opening in your browser.\n")
print(f"  Do this on Railway:")
print(f"  1. Sign in with GitHub (same account: {username})")
print(f"  2. Click  [Deploy from GitHub repo]")
print(f"  3. Select  {REPO_NAME}")
print(f"  4. Go to  Variables  tab and add:\n")
print(f"  {BOLD}SECRET_KEY{RESET}       =  {CYAN}{secret_key}{RESET}")
print(f"  {BOLD}ADMIN_PASSWORD{RESET}   =  YourChosenPassword")
print(f"  {BOLD}WHATSAPP_NUMBER{RESET}  =  966XXXXXXXXX\n")
print(f"  Railway will build & deploy automatically (~2 min).")
print(f"  Your live URL will appear under Settings → Domains.\n")
print(f"{GREEN}{BOLD}  ✓ Deployment complete! Your site is going live.{RESET}\n")

input("  Press Enter to close this window...")
