#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Elite Motors — One-Click Deploy to GitHub + Railway
# ─────────────────────────────────────────────────────────────

# Change to the script's own directory (the project folder)
cd "$(dirname "$0")"

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
RESET="\033[0m"

echo ""
echo -e "${BOLD}${CYAN}══════════════════════════════════════════${RESET}"
echo -e "${BOLD}${CYAN}   Elite Motors — Deploy Script           ${RESET}"
echo -e "${BOLD}${CYAN}══════════════════════════════════════════${RESET}"
echo ""

# ── Step 1: Check git ──────────────────────────────────────────
if ! command -v git &>/dev/null; then
  echo -e "${RED}✗ Git is not installed.${RESET}"
  echo "  Install it from: https://git-scm.com/download/mac"
  echo "  (or run: xcode-select --install)"
  read -p "Press Enter to exit..."
  exit 1
fi
echo -e "${GREEN}✓ Git found${RESET}"

# ── Step 2: GitHub repo ────────────────────────────────────────
echo ""
echo -e "${BOLD}STEP 1 — Create a GitHub Repository${RESET}"
echo "  1. Opening github.com/new in your browser..."
open "https://github.com/new" 2>/dev/null || echo "  (please open https://github.com/new manually)"
echo ""
echo "  2. Fill in:"
echo "     • Repository name: elite-motors  (or anything you like)"
echo "     • Set to Public or Private"
echo "     • Do NOT check 'Add a README' — leave everything else blank"
echo "     • Click  [Create repository]"
echo ""
echo -e "${YELLOW}  Once created, copy the HTTPS URL shown on that page.${RESET}"
echo "  It looks like:  https://github.com/YOUR-USERNAME/elite-motors.git"
echo ""
read -p "  Paste the repository URL here and press Enter: " REPO_URL
echo ""

if [[ -z "$REPO_URL" ]]; then
  echo -e "${RED}✗ No URL entered. Exiting.${RESET}"
  exit 1
fi

# ── Step 3: Init & push ────────────────────────────────────────
echo -e "${BOLD}STEP 2 — Pushing files to GitHub...${RESET}"

# Remove any existing git repo to start fresh
rm -rf .git

git init -b main
git add .
git commit -m "🚗 Initial commit — Elite Motors car dealership"

git remote add origin "$REPO_URL"

echo ""
echo "  Pushing to GitHub (you may be asked to log in)..."
git push -u origin main

if [[ $? -ne 0 ]]; then
  echo ""
  echo -e "${RED}✗ Push failed.${RESET}"
  echo "  Tip: If you see an authentication error, create a Personal Access Token:"
  echo "  https://github.com/settings/tokens/new?scopes=repo"
  echo "  Use it as your password when Git asks."
  read -p "Press Enter to exit..."
  exit 1
fi

echo -e "${GREEN}✓ Code pushed to GitHub!${RESET}"

# ── Step 4: Railway ────────────────────────────────────────────
echo ""
echo -e "${BOLD}STEP 3 — Deploy on Railway${RESET}"
echo "  1. Opening railway.app in your browser..."
open "https://railway.app/new" 2>/dev/null || echo "  (please open https://railway.app/new manually)"
echo ""
echo "  2. Sign in with GitHub (same account you just used)"
echo "  3. Click  [Deploy from GitHub repo]"
echo "  4. Select:  elite-motors  (or whatever you named it)"
echo "  5. Railway will start building automatically"
echo ""
echo "  6. Once deployed, go to your project → Variables tab and add:"
echo ""
echo -e "${CYAN}     SECRET_KEY    =  $(python3 -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null || echo 'some-very-long-random-string-here')${RESET}"
echo -e "${CYAN}     ADMIN_PASSWORD = YourChosenPassword${RESET}"
echo -e "${CYAN}     WHATSAPP_NUMBER = 966501234567${RESET}"
echo ""
echo "  7. Railway will redeploy automatically after you add the variables."
echo "  8. Your live URL will appear under  Settings → Domains."
echo ""
echo -e "${GREEN}${BOLD}══════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  ✓ All done! Your site is deploying.  ${RESET}"
echo -e "${GREEN}${BOLD}══════════════════════════════════════${RESET}"
echo ""
read -p "Press Enter to close this window..."
