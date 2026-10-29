# Live responses through the ChatGPT subscription

The fixed workflow can now request model responses as it reaches each stage.
Recorded replay remains available. The model receives a stage prompt and returns
text; it cannot choose tools, execute commands or select the next stage.

The local connection uses Grinta's Python environment and its independently
authorized ChatGPT-plan session. It calls the public Responses endpoint with
storage disabled, no model tools and no conversation continuation. Credentials
stay inside the Grinta worker process and OS credential store. They are not
copied into candidate containers or Agentless artifacts. Renewal uses the same
Grinta authorization module. There is no API-key or Codex-backend fallback.

## Run explicitly

First complete Grinta's `chatgpt_plan_auth login`. Then, from Agentless-ML's
Python environment, use the existing shared-task launcher:

```powershell
python tools/run_shared_deepswe_workflow.py `
  --shared-task <shared-task.json> `
  --source-repository <pinned-repository> `
  --workspace-root <new-workspace-directory> `
  --artifact-root <new-artifact-directory> `
  --live-subscription `
  --grinta-root C:/Users/GIGABYTE/Desktop/Grinta `
  --model gpt-6.1-sol --reasoning medium `
  --edit-samples 1 --repair-samples 1
```

This command consumes subscription allowance and runs the task's public schedule.
It does not run the hidden benchmark scorer. The sample counts above illustrate
the interface; they are not the agreed research configuration or budget.
Use `--experiment <directory>` instead for recorded replay, or `--inspect-start`
for preflight without model calls.

Public baseline selection, file localization, symbol localization, each edit
sample and its repair samples follow the existing controller. Reproduction
generation is also supported when a reproduction specification is supplied to
the controller; the shared-task CLI does not invent one. All repair responses
are generated before candidate validation. Failures do not trigger model retries
or feed test output back into repair generation.

Each `model-calls/<number>` folder records the prompt, completed response and
reported usage immediately. Final run records contain actual call/token totals.
Missing token accounting stops the run rather than silently reporting zero.
Failures retain their request evidence and the attempted call count. Completed
responses are also saved in the existing replayable response bundle.

## Verification and remaining work

A real repository fixture exercises stage requests through patch selection and
final export using a deterministic provider. The recorded controller tests remain
green. A live text-only request through this adapter returned the expected marker
using `gpt-6.1-sol`, medium reasoning, and 29 reported tokens. No real benchmark
task was attempted for that check.

The overall experiment's token/time budget, sample allocations and scoring
protocol still need agreement and aggregate enforcement before benchmark runs.
Per-request connection timeouts and finite sample counts do not establish those
aggregate limits. This local adapter currently requires the Grinta checkout and
its Python environment; it is not a standalone OAuth installation in Agentless-ML.
