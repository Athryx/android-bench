---
name: run-android-benchmark
description: Prepare remote Android benchmark configurations, resource budgets, and descriptive results paths on benchmarks, and launch synthetic test runs in persistent tmux sessions.
---

# Run Android Benchmark

Use `ssh benchmarks` to access the remote checkout at `~/android-bench`.
This skill covers configuration and resource management, with execution examples
for the synthetic test challenges. Do not extend it into autonomous exploitation
of third-party apps.

## Choose the run settings

- Use the requested model, harness, challenge subset, and any explicit overrides.
  Ask for missing model or harness choices rather than borrowing an unrelated run.
- Ask for a duration in hours if the user has not supplied one. Set
  `[limits].time_limit` to hours multiplied by 3600; fractional hours are valid.
  This is a solver time budget, not a deadline for the whole benchmark including
  provisioning and grading.
- Default to `num_instances = 2`. This bounds concurrency, not repeat count.
  Use one when requested; exceed two only when explicitly specified.
- Prefer only the time limit. Omit `token_limit`, `turn_limit`, and `dollar_limit`
  unless requested, including CLI overrides. Do not confuse the model's request
  timeout or output-token setting with the benchmark duration.
- Use a descriptive filesystem-safe run name, for example
  `codex-gpt-6-astra-test-all-1h-20261001-143000`. Include the model/harness,
  challenge subset or experiment purpose, duration, and timestamp. Use letters,
  digits, hyphens, and underscores so the name also works in tmux.

## Prepare the remote configuration

Store the configuration at
`~/android-bench/challenges/<run-name>/challenge.toml`, with its `name` matching
the run name. Store results at `~/android-bench/results/<run-name>/`.
Create only run-specific configuration and output artifacts remotely. Source
changes belong in the local checkout unless remote source editing was explicitly
requested. `PROMPT.md` is for manual runs and does not configure the runner.

Inspect the remote `src/android_bench/config.py`, CLI help, and existing
configuration examples before preparing a run, because its version can differ
from the local checkout. Keep API keys in the existing `.env` or environment;
do not print them or put them in TOML. Confirm `uv`, `tmux`, Docker, the configured
Cuttlefish service/template, and the necessary challenge images are available.
Do not upgrade dependencies or rebuild the environment as part of routine launch.

The minimal example below is a one-hour synthetic test. Replace its name,
model, harness, and duration with the agreed settings:

```toml
name = "codex-gpt-6-astra-test-all-1h-20261001-143000"
num_instances = 2
challenges = ["test_all"]
harness = "codex"
internet_enabled = false
summarize = false
max_reprompts = 2

[model_config]
model = "gpt-6-astra"

[limits]
time_limit = 3600
```

`name`, `harness`, and `[model_config]` are required. `challenges` accepts registry
names or per-challenge tables; keep the selection explicit. Omitting it selects
all registered production challenges. Optional `model_effort` must be supported
by the chosen model/harness. `internet_enabled` defaults to false. `summarize`
defaults to false and requires OpenRouter credentials when enabled; the integrity
grader also requires `OPENROUTER_API_KEY`. Preserve requested settings.
Per-challenge tables support `capabilities`, `solutions_folder`, and `extra_prompt`;
relative solution paths resolve from the configuration's directory. Validate the
file using `BenchmarkConfig.from_file` before launch, without executing a run.

## Launch a synthetic test in tmux

Run these commands on the remote host after preparing the configuration. Set
`run_name` to the agreed name. The working directory **must be `~/android-bench`**
so the CLI loads the project `.env`. The tmux session must be named
`benchmark_<run-name>` and start detached so SSH disconnection leaves it running.

```bash
cd "$HOME/android-bench" || exit 1
run_name=codex-gpt-6-astra-test-all-1h-20261001-143000
session_name="benchmark_${run_name}"

test -f "challenges/$run_name/challenge.toml" || exit 1
if tmux has-session -t "=$session_name" 2>/dev/null; then
  printf 'Session already exists: %s\n' "$session_name"
  exit 1
fi
if [ -e "results/$run_name" ]; then
  if [ ! -d "results/$run_name" ] || [ -n "$(ls -A "results/$run_name")" ]; then
    printf 'Results path must be a new or empty directory\n'
    exit 1
  fi
fi

tmux new-session -d -s "$session_name" -c "$PWD" bash -c '
  uv run android-bench run \
    --config "challenges/$1/challenge.toml" \
    --results "results/$1"
  benchmark_status=$?
  printf "\nBenchmark exited with status %s\n" "$benchmark_status"
  exec bash
' bash "$run_name"
```

The shell remains available after the command finishes so its output and exit
status can be inspected. A surviving tmux session alone does not prove the
benchmark is still running. Check startup using `tmux capture-pane -p -t
"=$session_name"` and look for configuration errors or immediate failure.
Do not automatically retry a failed launch or replace an existing session.

List sessions with `tmux list-sessions`. Reconnect with `ssh benchmarks`, then
attach with `tmux attach-session -t "benchmark_<run-name>"`. Detach with
`Ctrl-b`, then `d`; avoid `Ctrl-c` when the intention is to leave the run working.
Persistence covers SSH disconnection, not host reboot or termination of tmux.

The runner creates the results directory and writes its own `challenge.toml`
snapshot there. Do not prepopulate it with configuration or logs. Existing run
outputs should be inspected or explicitly resumed rather than overwritten.
Report the run name, tmux session, remote configuration and results paths,
startup status, and exact attachment command. Do not claim completion from
successful tmux creation alone.
