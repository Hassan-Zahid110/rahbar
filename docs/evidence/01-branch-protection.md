# Branch Protection Configuration Evidence

Repository: `https://github.com/Hassan-Zahid110/rahbar`
Protected Branch: `main`
Date Verified: 2026-11-04

## GitHub Branch Protection Rule Details
- **Branch pattern**: `main`
- **Require a pull request before merging**: `true`
  - Required approvals: `1`
  - Dismiss stale pull request approvals when new commits are pushed: `true`
  - Require review from Code Owners: `false`
- **Require status checks to pass before merging**: `true`
  - Require branches to be up to date before merging: `true`
  - Status checks required:
    - `Lint & Typecheck` (`ci.yml / lint`)
    - `Unit Tests & Coverage (Stubs Only)` (`ci.yml / test`)
    - `Validate Kustomize Manifests` (`ci.yml / manifests`)
    - `Build Container Images (No Push on PR)` (`ci.yml / build`)
    - `Trivy Vulnerability Scan` (`ci.yml / scan`)
    - `Ephemeral kind Cluster E2E & Eval Gate` (`ci.yml / e2e-eval`)
- **Do not allow bypassing the above settings**: `true` (enforced for administrators)
- **Allow direct pushes**: `false` (all changes must arrive via PR from `dev` or feature branches)

## CLI Verification
```bash
gh api repos/Hassan-Zahid110/rahbar/branches/main/protection --jq '{
  required_status_checks: .required_status_checks.contexts,
  enforce_admins: .enforce_admins.enabled,
  required_pull_request_reviews: .required_pull_request_reviews.required_approving_review_count
}'
```
Output:
```json
{
  "required_status_checks": [
    "Lint & Typecheck",
    "Unit Tests & Coverage (Stubs Only)",
    "Validate Kustomize Manifests",
    "Build Container Images (No Push on PR)",
    "Trivy Vulnerability Scan",
    "Ephemeral kind Cluster E2E & Eval Gate"
  ],
  "enforce_admins": true,
  "required_pull_request_reviews": 1
}
```
