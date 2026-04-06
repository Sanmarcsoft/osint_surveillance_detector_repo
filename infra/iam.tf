# -----------------------------------------------------------------------------
# IAM — Task execution and task roles for ECS
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# --- Task Execution Role (used by ECS agent to pull images, push logs, read secrets) ---

resource "aws_iam_role" "nest_task_execution" {
  name               = "${local.project_name}-${local.service_name}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "nest_task_execution" {
  role       = aws_iam_role.nest_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "nest_task_execution_secrets" {
  name = "${local.project_name}-${local.service_name}-secrets"
  role = aws_iam_role.nest_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.nest_secrets.arn
        ]
      }
    ]
  })
}

# --- Task Role (used by the running containers) ---

resource "aws_iam_role" "nest_task" {
  name               = "${local.project_name}-${local.service_name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = local.tags
}
