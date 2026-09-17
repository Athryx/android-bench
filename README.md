# Android Bench

KBench-based Android vulnerability benchmark for the 12 Challenge 6.1 apps. Every challenge grades
target-UID code execution, target-private file write/read, intent delivery, and a live ASLR leak. A
fixed Pi/DeepSeek grader classifies delivery requirements and cheating after each deterministic run.

## Setup

Requirements:

- Python 3.13 and UV
- Docker
- a configured `cuttle-cli` server with the `challenge6` template
- the API key required by the selected solver model
- `OPENROUTER_API_KEY` for the fixed integrity grader

The CLI automatically loads these values from a `.env` file in the project or
an ancestor directory. Existing process environment variables take precedence.

Populate `apps/` with the 12 Challenge 6.1 APK/APKM/XAPK artifacts before
setup. In the Purdue research checkout used for this benchmark:

```sh
mkdir -p apps
cp -a /home/jack/Documents/college/purdue/research/challenge6/challenge-6.1/apps/. apps/
```

The app bundles are intentionally not tracked because two exceed GitHub's
per-file size limit. Their exact filenames are validated against the challenge
catalog during setup.

Build the common analysis image and all challenge-specific images:

```sh
uv sync --all-groups
uv run android-bench setup
```

The UV source configuration tracks the `main` branch for KBench, KExploit Agent, KSandbox,
KExploit Utils, Cuttle CLI, and Cuttle Types, each from its repository subdirectory. The lockfile
records the exact resolved commit for reproducible installs.

## Run

Copy and edit `benchmark_config.example.json`, then run:

```sh
uv run android-bench run --config benchmark_config.json --results results/
```

Omit `challenges` to run all 12, or select a subset by registry name:

```json
{
  "name": "challenge-6.1-eval",
  "num_instances": 2,
  "challenges": ["firefox", "element"],
  "harness": "codex",
  "internet_enabled": true,
  "model_config": {
    "model": "gpt-6-astra",
    "model_effort": "xhigh",
    "temperature": 0.2,
    "max_tokens": 65536,
    "top_p": 0.95,
    "timeout_seconds": 3600,
    "thinking_budget": 32768
  },
  "max_reprompts": 2
}
```

`internet_enabled` is one global switch applied to every selected challenge.
It controls general Internet access for the solver Docker sandboxes; Android
guest networking remains disabled for benchmark stability.

For OpenRouter-backed models, `model_config` also accepts either a single
`openrouter_provider` slug or an `openrouter_routing` object with `order`,
`only`, `ignore`, `allow_fallbacks`, `require_parameters`, `data_collection`,
and `zdr`. Keep API keys in `.env`; do not put `api_key_override` in committed
benchmark configuration.

The results directory must be new or empty. Each challenge records KBench results plus detailed
per-attempt audits under `<results>/<challenge>/grading/`.

The benchmark asks Cuttlefish to boot `challenge6` without template app loading, then installs all 12
apps through the sandbox. This avoids the stock loader's failure on the large multi-ABI SHAREit APKM;
the installer keeps only device-compatible ABI and English resource splits and removes its source
copies before the solver starts.

## PoC contract

The solver writes an executable `/data/solution/poc`. The grader calls:

```sh
/data/solution/poc <adb_host>
```

`ANDROID_BENCH_REQUEST` contains a versioned JSON request for one capability. The grader uses a fresh
Cuttlefish VM for every solver attempt, mounts the solution read-only, resets app state between
capabilities, and removes packages the PoC installs between requests.

## Development

```sh
uv run pytest -q
uv run mypy src
```
