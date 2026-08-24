#!/usr/bin/env bash
set -euo pipefail

# Load environment variables from .env if present
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:-dandye-0324-chronicle}"
REGION="${GCP_REGION:-us-central1}"

echo "=============================================================================="
echo " Google Cloud Authentication & Environment Preflight Check"
echo "=============================================================================="

ISSUES_FOUND=0

# 1. Check gcloud CLI active account
echo -n "Checking gcloud active account... "
ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null || echo "")
if [[ -n "$ACTIVE_ACCOUNT" ]]; then
  echo "[OK] $ACTIVE_ACCOUNT"
else
  echo "[ERROR] No active gcloud account found."
  echo "  Run: gcloud auth login --update-adc"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# 2. Check gcloud CLI active project vs .env
echo -n "Checking gcloud project configuration... "
GCLOUD_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [[ "$GCLOUD_PROJECT" == "$PROJECT_ID" ]]; then
  echo "[OK] Configured to '$PROJECT_ID'"
elif [[ -n "$GCLOUD_PROJECT" ]]; then
  echo "[WARNING] Mismatch: gcloud is '$GCLOUD_PROJECT', but .env is '$PROJECT_ID'."
  echo "  To sync gcloud project to .env, run:"
  echo "    gcloud config set project $PROJECT_ID"
else
  echo "[WARNING] No gcloud default project set (scripts will use .env '$PROJECT_ID')."
fi

# 3. Check Application Default Credentials (ADC)
echo -n "Checking Application Default Credentials (ADC)... "
if gcloud auth application-default print-access-token >/dev/null 2>&1; then
  echo "[OK] Valid access token generated"
else
  echo "[ERROR] ADC token is expired, invalid, or missing."
  echo "  To refresh ADC, run:"
  echo "    gcloud auth login --update-adc"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# 4. Check ADC Quota Project
echo -n "Checking ADC quota project... "
ADC_QUOTA_PROJECT=$(gcloud auth application-default get-quota-project 2>/dev/null || echo "")
if [[ -n "$ADC_QUOTA_PROJECT" ]]; then
  if [[ "$ADC_QUOTA_PROJECT" == "$PROJECT_ID" ]]; then
    echo "[OK] Matches '$PROJECT_ID'"
  else
    echo "[INFO] Set to '$ADC_QUOTA_PROJECT' (.env uses '$PROJECT_ID')"
  fi
else
  echo "[INFO] No ADC quota project specified (default billing project applies)"
fi

# 5. Summary
echo "=============================================================================="
if [[ $ISSUES_FOUND -eq 0 ]]; then
  echo "[OK] Authentication & project configuration verified."
  exit 0
else
  echo "[WARNING] Found $ISSUES_FOUND authentication issue(s). Please review recommendations above."
  exit 1
fi
