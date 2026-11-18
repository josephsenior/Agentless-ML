# Live benchmarks on Amazon Bedrock

Select Amazon Bedrock explicitly to run in Paris (`eu-west-3`),
with `gpt-6.2-sol` at `xhigh`. It sends the fixed stage prompts through the
Responses API using the `global.openai.gpt-6.2-sol` inference profile. AWS bills
these requests to the account associated with the Bedrock API key. The global
profile can process requests outside the source region.

Add your Bedrock key to `.env` at the repository root, without quotes. Git
ignores this file. If `AWS_BEARER_TOKEN_BEDROCK` is already set in the terminal,
that value takes precedence.

```dotenv
AWS_BEARER_TOKEN_BEDROCK=
```

Run the batch from the Agentless-ML repository with the same task, records,
repository, and output arguments as before. Leave off `--grinta-root` for
Bedrock. For example:

```powershell
.venv/Scripts/python.exe tools/run_agentless_batch.py `
  --provider bedrock `
  --tasks <task-id> `
  --records-root artifacts/shared-deepswe-final-2026-10-24 `
  --repositories ../benchmarks/deepswe/repos `
  --output artifacts/<new-run-directory>
```

The shared-task launcher uses Bedrock with `--live-bedrock`. Recorded runs use
`--experiment`. For the default live provider, see the
[ChatGPT subscription guide](live-subscription.md).

For a small paid connection check before running a whole task, use the same
terminal and print only the model identifier and token counts:

```powershell
.venv/Scripts/python.exe -c "from pathlib import Path; from agentless_ml.workflow.bedrock import BedrockResponses; r = BedrockResponses(env_file=Path('.env')).complete('Reply with OK only.'); print(r['model'], r['usage']['input_tokens'], r['usage']['output_tokens'])"
```

An HTTP 401 or 403 means AWS refused the credentials or permissions. Check the
key and access to the global inference profile. The launcher records the
provider, model, reasoning effort, region, and reported usage with the run.

[AWS model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-6-2-sol.html) ·
[AWS Responses API prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-responses-api.html)
