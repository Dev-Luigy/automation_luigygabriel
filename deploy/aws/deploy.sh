#!/usr/bin/env bash
set -Eeuo pipefail

ea_project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ea_project_root}"

ea_stack_name="${EA_AWS_STACK_NAME:-expense-agent-sandbox}"
ea_environment_name="${EA_ENVIRONMENT_NAME:-expense-agent-sandbox}"
ea_region="${EA_AWS_REGION:-sa-east-1}"
ea_profile="${EA_AWS_PROFILE:-}"
ea_reviewer_username="${EA_REVIEWER_USERNAME:-reviewer}"
ea_reviewer_id="${EA_REVIEWER_ID:-assessment-reviewer}"
ea_reviewer_email="${EA_REVIEWER_EMAIL:-reviewer@example.com}"
ea_reviewer_display_name="${EA_REVIEWER_DISPLAY_NAME:-Assessment Reviewer}"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 1
    fi
}

require_command aws
require_command docker
require_command openssl
require_command python3
require_command sam
require_command uv

if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but its daemon is not running." >&2
    exit 1
fi

if [[ ! "${ea_stack_name}" =~ ^[A-Za-z][A-Za-z0-9-]{0,127}$ ]]; then
    echo "EA_AWS_STACK_NAME is not a valid CloudFormation stack name." >&2
    exit 1
fi
if [[ ! "${ea_environment_name}" =~ ^[a-z][a-z0-9-]{2,31}$ ]]; then
    echo "EA_ENVIRONMENT_NAME must match ^[a-z][a-z0-9-]{2,31}$." >&2
    exit 1
fi

ea_aws_global=(--region "${ea_region}")
ea_sam_profile=()
if [[ -n "${ea_profile}" ]]; then
    ea_aws_global+=(--profile "${ea_profile}")
    ea_sam_profile=(--profile "${ea_profile}")
fi

echo "Checking AWS identity for ${ea_stack_name} in ${ea_region}..."
aws "${ea_aws_global[@]}" sts get-caller-identity --output json >/dev/null

if [[ "${EA_AUTO_APPROVE:-false}" != "true" ]]; then
    echo "This creates billable API Gateway, Lambda, EFS, VPC, S3, and log resources."
    read -r -p "Create or update the assessment sandbox? [y/N] " ea_confirmation
    if [[ ! "${ea_confirmation}" =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 0
    fi
fi

ea_reviewer_password=""
if [[ -n "${EA_REVIEWER_PASSWORD_HASH:-}" ]]; then
    ea_reviewer_password_hash="${EA_REVIEWER_PASSWORD_HASH}"
else
    read -r -s -p "Reviewer password: " ea_reviewer_password
    echo
    read -r -s -p "Confirm reviewer password: " ea_reviewer_confirmation
    echo
    if [[ -z "${ea_reviewer_password}" ]]; then
        echo "Reviewer password must not be empty." >&2
        exit 1
    fi
    if [[ "${ea_reviewer_password}" != "${ea_reviewer_confirmation}" ]]; then
        echo "Reviewer passwords do not match." >&2
        exit 1
    fi
    ea_reviewer_password_hash="$(
        printf '%s\n' "${ea_reviewer_password}" |
            uv run --frozen expense-agent-hash-password --password-stdin
    )"
    unset ea_reviewer_confirmation
fi
ea_csrf_secret="${EA_CSRF_SECRET:-$(openssl rand -hex 32)}"

echo "Validating and building the Lambda artifact in an AWS build container..."
python3 deploy/aws/prepare_build.py
sam validate --template-file deploy/aws/template.yaml --lint
sam build --template-file deploy/aws/template.yaml --use-container

echo "Deploying the CloudFormation stack..."
sam deploy \
    --template-file .aws-sam/build/template.yaml \
    --stack-name "${ea_stack_name}" \
    --region "${ea_region}" \
    "${ea_sam_profile[@]}" \
    --capabilities CAPABILITY_IAM \
    --resolve-s3 \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --on-failure ROLLBACK \
    --parameter-overrides \
        "ParameterKey=EnvironmentName,ParameterValue=${ea_environment_name}" \
        "ParameterKey=ReviewerUsername,ParameterValue=${ea_reviewer_username}" \
        "ParameterKey=ReviewerId,ParameterValue=${ea_reviewer_id}" \
        "ParameterKey=ReviewerEmail,ParameterValue=${ea_reviewer_email}" \
        "ParameterKey=ReviewerDisplayName,ParameterValue=${ea_reviewer_display_name}" \
        "ParameterKey=ReviewerPasswordHash,ParameterValue=${ea_reviewer_password_hash}" \
        "ParameterKey=CsrfSecret,ParameterValue=${ea_csrf_secret}"

ea_api_url="$(
    # JMESPath uses literal backticks; shell expansion here would be incorrect.
    # shellcheck disable=SC2016
    aws "${ea_aws_global[@]}" cloudformation describe-stacks \
        --stack-name "${ea_stack_name}" \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue | [0]' \
        --output text
)"
if [[ -z "${ea_api_url}" || "${ea_api_url}" == "None" ]]; then
    echo "Stack deployed, but its ApiUrl output could not be read." >&2
    exit 1
fi

if [[ "${EA_SEED_DEMO:-true}" == "true" && -n "${ea_reviewer_password}" ]]; then
    echo "Seeding the three public assignment samples through HTTPS..."
    printf '%s\n' "${ea_reviewer_password}" |
        uv run --frozen python deploy/aws/seed_demo.py \
            --base-url "${ea_api_url}" \
            --username "${ea_reviewer_username}" \
            --password-stdin
elif [[ "${EA_SEED_DEMO:-true}" == "true" ]]; then
    echo "Demo seed skipped because only a password hash was supplied."
fi

unset ea_reviewer_password ea_reviewer_password_hash ea_csrf_secret
echo
echo "Assessment sandbox deployed."
echo "Review UI: ${ea_api_url}/reviews"
echo "Username:  ${ea_reviewer_username}"
echo "Safety:    synthetic assessment data only; this is not the production target."
