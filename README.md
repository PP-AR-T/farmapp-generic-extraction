# Generic API Extraction Framework

Configuration-driven API ingestion framework on Azure Functions + ADLS Gen2 + Key Vault, provisioned entirely with Terraform.

## 1. Project Goal

This project provides a reusable extraction runtime that can ingest data from multiple external APIs without code changes.

Core goals:
- Extract API data via JSON job configs.
- Store bronze output in ADLS Gen2 as Parquet.
- Keep sensitive values in Azure Key Vault.
- Track incremental watermarks in a state store.
- Deploy all Azure resources with Terraform in one resource group.
- Support fast create/destroy cycles for development.

## 2. High-Level Architecture

Core Azure components:
- Azure Function (Python): generic extractor runtime.
- ADLS Gen2 storage account: `bronze`, `configs`, and `state` containers.
- Azure Key Vault: stores API keys, tokens, and secrets.
- Application Insights (+ Log Analytics): logs and diagnostics.
- Terraform: infrastructure lifecycle management.

Runtime flow:
1. Trigger via HTTP or Timer.
2. Load job config JSON from ADLS `configs/jobs/<job>.json`.
3. Resolve secret values from Key Vault using secret names in config.
4. Execute API calls with pagination/retries/rate-limit handling.
5. Apply incremental logic using `state/<job>.json` watermark.
6. Write Parquet to `bronze/<dataset>/year=YYYY/month=MM/day=DD/part-*.parquet`.
7. Update watermark state.

## 3. Design Principles

- Configuration-driven: new APIs are onboarded by adding job JSON + Key Vault secrets.
- Secure by design: configs never store raw secrets.
- Stateless execution: per-run state is externalized in `state` files.
- Modular extractor code: `auth`, `pagination`, `api_client`, `sink`, `state_manager`, `runner`.
- Monorepo simplicity: app code + infra evolve together.

## 4. Repository Structure

```text
generic-api-extractor/
├── infra/
│   ├── modules/
│   │   ├── storage/
│   │   ├── function_app/
│   │   ├── keyvault/
│   │   └── monitoring/
│   ├── envs/
│   │   ├── dev/
│   │   └── prod/
│   └── providers.tf
├── src/
│   └── function_app/
│       ├── function_app.py
│       ├── host.json
│       ├── local.settings.json.example
│       ├── requirements.txt
│       └── extractor/
│           ├── api_client.py
│           ├── auth.py
│           ├── pagination.py
│           ├── runner.py
│           ├── sink.py
│           └── state_manager.py
├── configs/
│   └── jobs/
│       └── sample_api.json
├── scripts/
│   └── local_run.py
└── README.md
```

## 5. Job Configuration Model

Example: `configs/jobs/sample_api.json`

```json
{
	"job_name": "github_events",
	"source": {
		"base_url": "https://api.github.com",
		"endpoint": "/events",
		"method": "GET"
	},
	"auth": {
		"type": "bearer_token",
		"keyvault_secret_name": "github-api-token",
		"header_name": "Authorization"
	},
	"pagination": {
		"type": "page",
		"page_param": "page",
		"page_size_param": "per_page",
		"page_size": 100
	},
	"incremental": {
		"enabled": true,
		"watermark_field": "created_at"
	},
	"sink": {
		"format": "parquet",
		"container": "bronze",
		"dataset": "github/events",
		"partition_by": ["date"]
	}
}
```

Supported auth strategies in code:
- `none`
- `api_key`
- `bearer_token`
- `basic`

Supported pagination strategies in code:
- `none`
- `page`
- `offset`
- `cursor`
- `next_link`

## 6. Terraform Infrastructure

Implemented resources:
- Resource group (single RG per environment)
- Storage account (HNS enabled, ADLS Gen2) + containers (`bronze`, `configs`, `state`)
- Key Vault (RBAC-enabled)
- Application Insights + Log Analytics workspace
- Linux Function App (Python 3.11, system-assigned managed identity)
- RBAC assignments for Function identity:
	- `Storage Blob Data Contributor` on Storage Account
	- `Key Vault Secrets User` on Key Vault

Environment roots:
- `infra/envs/dev`
- `infra/envs/prod`

## 7. Local Development (VS Code)

Recommended extensions:
- Azure Functions
- Python
- Terraform

Install Python dependencies:

```powershell
pip install -r src/function_app/requirements.txt
```

Run locally with local config:

```powershell
python scripts/local_run.py --config configs/jobs/sample_api.json
```

Local secret resolution rule:
- In local mode, each `keyvault_secret_name` maps to an environment variable.
- Example: `github-api-token` -> env var `GITHUB_API_TOKEN`.

Run Function host locally:

```powershell
cd src/function_app
copy local.settings.json.example local.settings.json
func start
```

## 8. Terraform Deployment

Deploy dev environment:

```powershell
cd infra/envs/dev
terraform init
terraform plan
terraform apply
```

Deploy prod environment:

```powershell
cd infra/envs/prod
terraform init
terraform plan
terraform apply
```

Upload job config to ADLS config container path:
- `configs/jobs/<job_name>.json`

Set required Key Vault secrets:
- `github-api-token`
- or API-specific secret names referenced by job configs

Deploy function code:
- Zip deploy
- or CI/CD (for example GitHub Actions)

## 9. Triggering a Job

HTTP request body:

```json
{
	"job_name": "github_events"
}
```

Timer trigger:
- Uses app setting `DEFAULT_JOB_NAME`
- Uses app setting `DEFAULT_TIMER_SCHEDULE`

## 10. Observability

Execution logs include:
- job name
- page processing details
- records extracted
- output path
- API/retry errors

All runtime logs flow into Application Insights.

## 11. Data Format Strategy

Current:
- Bronze writes in Parquet only.

Future-compatible path:
- Keep extraction in Parquet.
- Add downstream conversion to Delta Lake or Iceberg using Spark/Fabric/Databricks.

## 12. Destroy Environment

Because all resources are in one resource group, teardown is simple:

```powershell
cd infra/envs/dev
terraform destroy
```

Use `infra/envs/prod` for production teardown.

## 13. Future Enhancements

- Queue orchestration via Azure Service Bus.
- Parallelized extraction by page/date shard.
- Schema inference and metadata capture.
- Data quality checks pre-write.
- Optional Delta/Iceberg sink adapters.
