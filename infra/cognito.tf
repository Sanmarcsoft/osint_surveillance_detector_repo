# -----------------------------------------------------------------------------
# Cognito — ALB authentication for N.E.S.T. Ops
#
# This service authenticates against the SHARED phenom-prod user pool (the same
# Cognito pool + hosted-UI domain Hasura/GraphQL uses). It does NOT own a pool,
# client, group, or domain — those are referenced by ID via variables and wired
# into the ALB listener rule (see alb.tf). Earlier revisions created a phantom
# dev-local pool client + group + domain that nothing used and that, on apply,
# would have reverted the live ALB auth to the wrong pool. Removed 2026-06-11.
#
# If this service ever needs its own dedicated client/group, add them here in
# the phenom-prod pool (var.cognito_user_pool_id) and point the ALB rule at the
# new client id — do not recreate a separate dev-local pool.
# -----------------------------------------------------------------------------

locals {
  cognito_user_pool_id = var.cognito_user_pool_id
}
