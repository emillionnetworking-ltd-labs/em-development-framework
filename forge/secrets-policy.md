---
version: 1.0.0
status: active
category: reference
title: Secrets policy and GitHub App provisioning runbook
description: Operator runbook for provisioning the mirror GitHub App and managing repository secrets. Required for repo bifurcation cutover (W61).
last_changed: 2026-06-03
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Secrets Policy and GitHub App Provisioning Runbook

This document is the operator runbook for cross-repo mirror infrastructure. Authored by SCRUM-626 (W58, Sprint 27 Repo Bifurcation). Required reading before W61 cutover execution.

---

## 1. Why this exists

The W61 cutover establishes a PRIVATE/PUBLIC bifurcation with a GitHub Actions workflow (`distro-mirror.yml`) that pushes from PRIVATE to PUBLIC on tag push. The workflow requires cross-repo authentication. Per ADR-014 and strategy session executive report, the chosen mechanism is **GitHub App with OIDC trusted publishing**.

This runbook documents the manual provisioning steps the operator must execute via GitHub admin UI. These steps CANNOT be automated by an agent because they require GitHub organization admin permissions.

---

## 2. Pre-flight checklist

Before provisioning:

- [ ] Operator has GitHub org admin role on `emillionnetworking-ltd-labs`.
- [ ] W58 ADR-014 sealed and accepted.
- [ ] W59-W60 lifecycle waves not yet started (GitHub App provisioning is decoupled but recommended before W59 for clarity).
- [ ] Local backup tarball exists at `/tmp/em-framework-pre-bifurcation-backup.tar.gz`.

---

## 3. GitHub App provisioning steps

### Step 3.1 — Create the GitHub App

1. Navigate to `https://github.com/organizations/emillionnetworking-ltd-labs/settings/apps`.
2. Click **New GitHub App**.
3. Configuration:
   - **App name**: `em-development-framework-mirror`
   - **Homepage URL**: `https://github.com/emillionnetworking-ltd-labs/em-development-framework`
   - **Webhook**: disabled (we don't need webhooks for tag-trigger workflows; the trigger lives in the source repo's own Actions runner).
   - **Repository permissions**:
     - `Contents`: **Read and write**
     - `Metadata`: **Read-only** (required default)
     - `Workflows`: **Read and write** (in case mirror needs to update PUBLIC workflows)
   - **Organization permissions**: none (App is repo-scoped, not org-scoped).
   - **Where can this GitHub App be installed?**: **Only on this account** (single-org scope).
4. Click **Create GitHub App**.

### Step 3.2 — Generate and store the private key

1. On the App's settings page, scroll to **Private keys**.
2. Click **Generate a private key**. A `.pem` file downloads automatically.
3. Open the `.pem` file in a text editor; copy the entire contents (including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`).
4. **Store as repository secret on PRIVATE repo**:
   - Navigate to `https://github.com/emillionnetworking-ltd-labs/em-development-framework/settings/secrets/actions` (this repo will become PRIVATE after W61 cutover; until then, the secret lives on the current public repo).
   - Click **New repository secret**.
   - Name: `MIRROR_APP_PRIVATE_KEY`
   - Value: paste the `.pem` contents.
   - Click **Add secret**.
5. **Delete the local `.pem` file** after secret is stored.

### Step 3.3 — Record the App ID as a repository variable

1. On the App settings page, copy the **App ID** (a numeric value, e.g. `123456`).
2. On the PRIVATE repo (currently public), navigate to `Settings → Secrets and variables → Actions → Variables`.
3. Click **New repository variable**.
4. Name: `MIRROR_APP_ID`
5. Value: the numeric App ID.
6. Click **Add variable**.

### Step 3.4 — Install the App on both repos

The fresh PUBLIC repo will be created in W61. For now, install the App on the current public (soon-to-be PRIVATE) repo only. After W61 creates the fresh PUBLIC, re-install the App on PUBLIC.

1. On the App's settings page, click **Install App** in the left sidebar.
2. Select `emillionnetworking-ltd-labs` org.
3. Choose **Only select repositories**.
4. For now: select `em-development-framework` (the current public repo).
5. Click **Install**.

**After W61 cutover** (when fresh PUBLIC exists):

1. Re-open App settings → Install App.
2. Configure the installation to ALSO include the freshly-created PUBLIC repo `em-development-framework`.
3. Save.

---

## 4. Verification

Post-provisioning, verify:

- [ ] App ID visible at `Settings → Apps → em-development-framework-mirror`.
- [ ] Secret `MIRROR_APP_PRIVATE_KEY` exists on PRIVATE repo (cannot be read, but presence confirmed).
- [ ] Variable `MIRROR_APP_ID` exists on PRIVATE repo with numeric value.
- [ ] App installed on PRIVATE repo (verify under repo `Settings → GitHub Apps`).
- [ ] After W61: App also installed on PUBLIC repo.

A smoke test via `workflow_dispatch` of `distro-mirror.yml` (added in W59) will be the operational verification.

---

## 5. Rotation policy

### Annual rotation (preventive)

Once per calendar year:

1. Generate new private key via App settings → Private keys → Generate.
2. Update `MIRROR_APP_PRIVATE_KEY` secret with new key contents.
3. Delete old private key entry from App settings (multiple keys can coexist briefly).
4. Verify a workflow run still authenticates successfully.

### Emergency rotation (on suspicion of compromise)

If the private key may have been exposed:

1. Immediately delete the compromised key from App settings.
2. Generate fresh key.
3. Update `MIRROR_APP_PRIVATE_KEY` secret.
4. Audit Actions runs: review past 30 days for unauthorized pushes to PUBLIC.
5. If unauthorized commits found on PUBLIC: revert via the `tag-mirror-validator.yml` recovery procedure (see ADR-014 §11).

---

## 6. Disaster recovery

### Scenario A — App accidentally deleted

1. Re-provision App via Step 3.1.
2. Generate new private key (Step 3.2).
3. Update secret + variable (Step 3.3).
4. Re-install on both repos (Step 3.4).
5. Mirror workflow resumes on next tag push.

### Scenario B — PRIVATE repo lost or corrupted

1. Restore from `/tmp/em-framework-pre-bifurcation-backup.tar.gz` (created in W58).
2. Force-push restored content to PRIVATE.
3. Mirror workflow resumes on next tag push.

### Scenario C — PUBLIC repo corrupted (unauthorized force-push or content alteration)

1. Identify the most recent valid PRIVATE tag.
2. Manually trigger `distro-mirror.yml` with `workflow_dispatch` against that tag.
3. The workflow will overwrite PUBLIC main with the clean tree from PRIVATE.
4. Branch protection prevents further unauthorized writes.

### Scenario D — `tag-mirror-validator.yml` detects drift

1. Validator opens an issue on PRIVATE with the diff summary.
2. Operator reviews diff to determine cause:
   - **PRIVATE tag advanced but PUBLIC didn't sync**: re-run `distro-mirror.yml` manually for the relevant tag.
   - **PUBLIC content altered without authorized release**: invoke Scenario C recovery.

---

## 7. Acceptable token / secret patterns

The framework prohibits hardcoded secrets in source code (Invariant 3 + Invariant 11). Acceptable secret patterns:

| Pattern | Status |
|---|---|
| GitHub App private key in repo secret | ✅ Acceptable (this runbook's pattern) |
| OIDC trusted publishing via GitHub App | ✅ Acceptable (preferred) |
| Repository deploy key | 🟡 Acceptable with rotation policy |
| Personal Access Token (PAT) in secret | 🔴 Rejected (rotation overhead, leak risk) |
| Hardcoded token in source code | 🔴 Rejected (Invariant 3 fails CI) |
| Token in commit history | 🔴 Rejected (requires history rewrite to remediate) |

---

## 8. References

- **ADR-014**: `forge/specs/adrs/adr-014-repo-bifurcation-private-dev-public-mirror.md` — architectural justification.
- **GitHub Apps documentation**: https://docs.github.com/en/apps
- **OIDC trusted publishing**: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect
- **THIRD_PARTY_NOTICES.md**: legal anchor for upstream MIT attribution.

---

*This runbook is operator-facing documentation. Updates to the GitHub App configuration should be reflected here. Authored by SCRUM-626 (W58).*
