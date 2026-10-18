# Production release boundary

SystemForge uses a two-part release design. This public repository builds,
tests, scans, and identifies a release. A restricted release control plane owns
promotion, routing, persistence, backup, restore, and rollback.

The public repository intentionally contains no machine addressing, login
details, transport configuration, credential identifiers, internal filesystem
layout, or private service topology. Those values are operational state and
must remain outside source control, workflow logs, artifacts, issue text, and
public documentation.

## Release selection

The restricted controller selects a completed `SystemForge CI` run only when:

- its conclusion is successful;
- its initiating event was a push;
- its reported head branch is `main`;
- its head repository is this repository;
- its source SHA remains the current, unsuperseded default-branch commit.

Pull requests, forks, failed CI runs, and non-main pushes cannot authorize a
production release. Publication approval and operational gates remain private.

## Public workflow contract

This repository has no production deployment caller. Its CI and public monitor
request read access to repository contents. They cannot request deployment
identity tokens, forward host credentials, invoke the retired public release
gateway, or publish production releases. External actions remain pinned to full
commit SHAs.

## CI artifact contract

CI builds the API, web, and worker images with the tested source SHA. It scans
that exact image set, packages it with a checksum, uploads it with short
retention, and downloads the same named artifact for integration testing. The
integration job verifies the checksum, loads the images, and starts the stack
without rebuilding.

This provides evidence that the controller consumes the same source and
container set exercised by CI. A green build is still only one release gate;
the restricted control plane independently verifies provenance and performs
the operational safety gates before promotion.

## Restricted release responsibilities

Infrastructure-specific behavior belongs exclusively to the restricted control
plane. Its responsibilities include:

- authenticating source provenance and checking its repository, workflow,
  commit, branch, event, and conclusion;
- resolving immutable images and rejecting missing or superseded releases;
- creating a current backup and proving an isolated restore before mutation;
- applying the candidate with bounded health and smoke checks;
- preserving the previous known-good release until acceptance;
- rolling back application state and routing when acceptance fails;
- issuing a signed, auditable receipt for the final outcome.

Public workflow changes must not recreate any of those responsibilities in this
repository. Public workflows must never gain direct machine access,
embed infrastructure coordinates, or receive long-lived deployment credentials.

## Data and rollback invariants

Application migrations must remain compatible with the immediately previous
release because schema rollback is not automatic. Promotion must fail closed if
backup, restore, health, or smoke evidence is missing. An incomplete candidate
must never replace the last accepted release, and a failed first promotion must
not leave a partially available stack.

Operational backup locations, retention configuration, off-site destinations,
and recovery procedures are deliberately maintained with the restricted release
configuration. This public document records the required outcomes without
publishing the infrastructure needed to reach them.

## Monitoring and incident response

Production monitoring should validate the public shell and canonical readiness
without depending on retired repository deployment variables. A readiness
failure should not disable browser-local functionality. Operators should inspect
the restricted service telemetry, preserve the accepted release, and restore
canonical submission only after queue and worker health are stable.

## Changing the boundary

Changes to the artifact or public workflow boundary must keep
`scripts/deploy_workflow_contract.test.sh` green. Reviewers should reject public
publication authority, mutable action references, elevated permissions,
infrastructure literals, or credential forwarding. Private release behavior is
reviewed and tested in the restricted control plane rather than mirrored here.
