#!/bin/sh
set -eu

CI_WORKFLOW=.github/workflows/ci.yml
MONITOR=.github/workflows/production-monitor.yml

# Public workflows produce tested artifacts and public monitoring evidence.
# Release selection and publication belong exclusively to the private controller.
test ! -e .github/workflows/deploy-hetzner.yml
test ! -e .github/hetzner-release.json
for workflow in .github/workflows/*.yml; do
  if grep -Eiq 'HetznerReleaseGateway|secrets:[[:space:]]*inherit|HETZNER_|SSH_PRIVATE_KEY|SSH_KNOWN_HOSTS|HetznerPlatform|/opt/|(^|[^[:alnum:]_])(ssh|scp|rsync)([^[:alnum:]_]|$)' "$workflow"; then
    echo "A public workflow reintroduces retired deployment authority or credentials." >&2
    exit 1
  fi
  if grep -Eiq 'permissions:[[:space:]]*write-all|(^|[[:space:]{,])(actions|attestations|checks|contents|deployments|discussions|id-token|issues|packages|pages|pull-requests|repository-projects|security-events|statuses):[[:space:]]*write' "$workflow"; then
    echo "Public workflows must not request publication or repository write permissions." >&2
    exit 1
  fi
done
grep -Fq 'contents: read' "$CI_WORKFLOW"
grep -Fq 'contents: read' "$MONITOR"

# CI must continue to package the exact scanned SHA-tagged image set, verify its
# checksum, and load that same artifact for integration without rebuilding it.
grep -Fq 'SYSTEMFORGE_IMAGE_TAG: ${{ github.sha }}' "$CI_WORKFLOW"
grep -Fq 'VITE_CANONICAL_RELEASE_ENABLED: "true"' "$CI_WORKFLOW"
grep -Fq 'image: systemforge-api:${{ github.sha }}' "$CI_WORKFLOW"
grep -Fq 'image: systemforge-web:${{ github.sha }}' "$CI_WORKFLOW"
grep -Fq 'image: systemforge-worker:${{ github.sha }}' "$CI_WORKFLOW"
grep -Fq 'docker save --output "$RUNNER_TEMP/systemforge-release/systemforge-images.tar"' "$CI_WORKFLOW"
grep -Fq 'uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7' "$CI_WORKFLOW"
grep -Fq 'uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8' "$CI_WORKFLOW"
grep -Fq 'name: systemforge-images-${{ github.sha }}-${{ github.run_attempt }}' "$CI_WORKFLOW"
grep -Fq 'sha256sum --check systemforge-images.tar.gz.sha256' "$CI_WORKFLOW"
grep -Fq 'docker compose --env-file deploy/.env.example -f deploy/docker-compose.prod.yml up -d --no-build' "$CI_WORKFLOW"

# Public monitoring must not depend on retired repository deployment material.
if grep -Eiq 'secrets\.|vars\.(HETZNER|SYSTEMFORGE_RELEASE_APPROVED)|PRIVATE_KEY|KNOWN_HOSTS|HetznerPlatform|/opt/|([0-9]{1,3}\.){3}[0-9]{1,3}' "$MONITOR"; then
  echo "Production monitoring depends on restricted deployment configuration." >&2
  exit 1
fi

if grep -E '^[[:space:]]*- uses: [^#]+@(v[0-9]|main|master)([[:space:]#]|$)' .github/workflows/*.yml; then
  echo "GitHub Actions must be pinned to immutable commit SHAs." >&2
  exit 1
fi

for retired in \
  deploy/Caddyfile.systemforge \
  deploy/Caddyfile.systemforge.open \
  scripts/deploy_hetzner.sh \
  scripts/stage_hetzner.sh \
  scripts/install_caddy_route.sh \
  scripts/verify_cloudflare_ranges.sh \
  reports/release-hardening-ledger.json
do
  test ! -e "$retired"
done

if grep -Eiq '/opt/|Caddy|dedicated SSH|host checkout|target Hetzner host' \
  README.md docs/operations/production.md docs/release-readiness.md docs/architecture.md; then
  echo "Public release documentation contains retired private infrastructure details." >&2
  exit 1
fi

echo "Private-controller artifact and public-boundary contract passed."
