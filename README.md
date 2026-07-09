# AgentLens: Production-Assessed Trajectory Reviews for Coding Agent Evaluation

[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![arXiv](https://img.shields.io/badge/arXiv-2607.06624-yellow.svg)](https://arxiv.org/abs/2607.06624)
[![Leaderboard](https://img.shields.io/badge/website-leaderboard-lightgrey.svg)](https://agent-lens.github.io/agent-lens-bench/)
[![Blog post](https://img.shields.io/badge/website-blogpost-lightgrey.svg)](https://explyt.ai/en/blog/agent-lens-bench?utm_source=github&utm_medium=readme&utm_campaign=agentlens&utm_id=260001)

AgentLens evaluates a coding agent the way its user experiences it — across the whole session, not just the final repository state or a pass/fail flag. We evaluate this way because binary success is too coarse for production assistants: a run can clear a narrow check and still be unreliable or unpleasant to work with, and a failing run can still do useful work along the way.

Each trajectory gets formal checks where they apply — tests, repository-state and regex checks, build tasks, static analysis — plus configurable LLM-judge metrics scoring the quality dimensions users actually feel, from final result to instruction compliance, tool use, and interaction style. Every judge score comes with a written review that cites the evidence behind it, so a result is a reviewed verdict, not an opaque number — and if you're building the agent, those reviews point to what to fix, not just a score that moved.

The same trajectories drive side-by-side comparisons against an anchor run, so AgentLens is useful well beyond ranking: diagnosing how agents differ, comparing versions, and catching regressions between runs.

---

<details open>
  <summary><b>Table of Contents</b></summary>

1. [How It Works](#how-it-works)
2. [Use Cases](#use-cases)
3. [Quick Start](#quick-start)
4. [Collecting Runs](#collecting-runs)
5. [Running Evaluations](#running-evaluations)
6. [Interpreting Reports](#interpreting-reports)
7. [Leaderboard](#leaderboard)
8. [Project Layout](#project-layout)
9. [Contributing](#contributing)
10. [Development Notes](#development-notes)

</details>

---

## How It Works

The unit of evaluation is a **trajectory** — one full interaction between an LLM user simulator and an agent on a repository task. AgentLens looks at both the final repository state and the decisions the agent made along the way.

A benchmark goes through two stages:

1. **Collection** — the IDE runner (`idea-plugin/`) plays a full chat between an LLM user simulator and the agent inside a headless IDE, and records the trace of everything the agent did. It writes one dump per trajectory.
2. **Evaluation** — the Python evaluator (`agent_lens/`) scores those dumps and writes reports.

Evaluation combines:

1. **Formal verification**: tests, repository-state checks, regex checks, build-system tasks, and static analysis.
2. **LLM-written trajectory reviews**: configurable judge metrics with written evidence from the interaction.
3. **Side-by-side reviews**: pairwise comparisons of two agents on the same task instances.

The released open-source fold is a compact Java `workflows` fold with 16 scenarios and two user personas (neutral and toxic). Scenarios come from developer-interview scenarios and anonymized production-usage summaries mapped to reproducible open-source repository tasks. Its default judge metrics are End Result, Instruction Compliance, Pitfalls, Pleasantness, and Tool Calls. Other folds can use different tasks, languages, personas, verifiers, and judge metrics.

Nothing in the framework is tied to Java or IntelliJ IDEA — it is the first fold we are releasing, with other languages and JetBrains IDEs (such as a Python fold on PyCharm) planned for open-source release.

## Use Cases

- **Compare agents** side-by-side on the same tasks — see [Running Evaluations](#running-evaluations).
- **Understand an agent's behavior** from the cited reviews, not just its score — see [Interpreting Reports](#interpreting-reports).
- **Catch regressions** automatically in a nightly or CI pipeline — see [Running via CI](#running-via-ci).
- **Rank agents** on the [leaderboard](#leaderboard) using the Quality Index.

## Quick Start

A full benchmark is two steps: collect dumps with the runner, then evaluate them.

### 1. Collect dumps

Run the IDE runner to produce trajectory dumps. See [Collecting Runs](#collecting-runs) for the dataset, environment variables, and agent options:

```bash
cd idea-plugin
./gradlew :idea-runner:runHeadless --no-daemon --stacktrace
```

Dumps are written to the directory you set in `WHERE_TO_SAVE_DUMPS` (e.g. `idea-plugin/bench_output`); that path is the `--idea_logs_path` value for the next step.

### 2. Evaluate dumps

Install the evaluator and point it at the dumps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r agent_lens/eval/requirements.txt
export LLM_API_KEY=<your_judge_api_key>

python -m agent_lens.eval.cli.run_agent_bench \
  --idea_logs_path <path_to_idea_dumps> \
  --dump_dir ./benchmark_runs \
  --config_path agent_lens/eval/configs/agent_bench_config.yaml \
  -k "$LLM_API_KEY"
```

Tune the judge model, limits, and report language in that config file.

A successful run creates a folder like `./benchmark_runs/<run_name>/<language>/` with:

- Markdown report files for the evaluated trajectories and benchmark summary;
- `quality_index.json`;
- run metadata next to the generated reports.

## Collecting Runs

The IDE runner in `idea-plugin/` turns each scenario into a recorded trajectory. For every scenario and persona it resets the task repository to a pinned revision, then plays a turn-by-turn dialogue between an LLM user simulator and the agent — the simulator reads the agent's code diffs and IDE errors before each reply, until the task is done or a step/budget limit is hit. The chat, tool calls, file diffs, verifier outputs, and per-turn telemetry are recorded as the **dump**.

Set the environment variables and run the headless Gradle task from `idea-plugin/`:

```bash
# user simulator (the LLM that role-plays the user)
export SIMULATOR_MODEL_NAME=<model>
export SIMULATOR_BASE_URL=<openai_compatible_base_url>
export SIMULATOR_API_KEY=<key>
# agent under test
export AGENT_API_KEY=<key>
export PROVIDER_NAME=OpenAI-compatible
# fold and collection I/O
export CONFIG_FILE_PATH=config/agent/workflows.json  # released Java fold
export GITHUB_TOKEN=<token>                           # for scenarios using the GitHub MCP server
export PROJECTS_ROOT_DIR=$PWD/dataset                # checked-out task dataset
export WHERE_TO_SAVE_DUMPS=$PWD/bench_output         # dumps -> --idea_logs_path
export PLUGIN_COMMIT_HASH=$(git rev-parse HEAD)

./gradlew :idea-runner:runHeadless --no-daemon --stacktrace
```

Prefer the IntelliJ Idea IDE? The configs in [`idea-plugin/.run/`](idea-plugin/.run/) set the same variables — fill in the API keys and `PLUGIN_COMMIT_HASH` and run them from your IDE.

### IDE-native vs CLI agents

IDE-native agents run in-process through the JetBrains IDE integration (`AgentEngine` interface); this is the default `ExplytCommonAgentEngine` in the fold config.

CLI agents such as Claude Code run instead behind the REST adapter in [`agent_lens/agent_server/`](agent_lens/agent_server/), which the runner reaches through `ExternalAgentEngine`. Start the adapter before collecting dumps and point the runner at it with `AGENT_ENGINE_URL`:

```bash
cd agent_lens/agent_server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The adapter runs at `http://127.0.0.1:8000`; open `/docs` for the API reference. See [`agent_lens/agent_server/README.md`](agent_lens/agent_server/README.md) for Claude Code-specific setup.

### Running via CI

To run the whole pipeline without a local setup, fork the repository and add the secrets [`run-benchmark.yml`](.github/workflows/run-benchmark.yml) reads — `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `SIMULATOR_MODEL_NAME`, `PAT` (GitHub MCP), `DATASET_PAT_TOKEN` (dataset access), and `ANTHROPIC_API_KEY` for Claude Code. Then trigger **Run benchmark** from the Actions tab, pick the Java or Python fold, and the workflow collects the dumps, evaluates them, and uploads the reports as artifacts.

## Running Evaluations

Evaluation is the second stage: the Python evaluator scores collected dumps and writes reports. A dump holds the recorded interaction, tool activity, file changes, verification outputs, and final-state metadata produced during collection.

Evaluate a dump folder:

```bash
python -m agent_lens.eval.cli.run_agent_bench \
  --idea_logs_path <path_to_idea_dumps> \
  --dump_dir ./benchmark_runs \
  --config_path agent_lens/eval/configs/agent_bench_config.yaml \
  -k <judge_api_key>
```

Compare two evaluated runs:

```bash
python -m agent_lens.eval.cli.compare_2_runs \
  --data_dir ./benchmark_runs \
  --dump_dir ./sbs_comparisons \
  --name my-agent-vs-baseline \
  --run1_name <baseline_run_name> \
  --run2_name <current_run_name> \
  -k <judge_api_key>
```

Merge multiple folds:

```bash
python -m agent_lens.eval.cli.merge_folds_and_publish \
  --input_folder <folder_with_folds> \
  --output_folder <merged_output_folder>
```

For local experiments, pass `--disable_tracking true` to commands that support it.

## Interpreting Reports

Reports combine aggregate metrics, written reviews, telemetry, and run metadata. Aggregate metrics compare runs; judge reviews contain cited trajectory evidence.

For the released Java fold, single-run reports include:

- **TL;DR and metric reviews**: benchmark-level summaries plus per-metric written reviews.
- **Formal verification**: number and rate of trajectories that passed configured checks.
- **Judge metrics**: the configured metric means, each with a written review.
- **Operational telemetry**: termination reasons, per-tool success rates, tool-call counts, latency, token usage, cache use, and cost.
- **Run metadata**: model, harness, judge, dataset/config hashes, and artifact paths.

Side-by-side reports compare two agents on the same task instances.

## Leaderboard

The static leaderboard in [`leaderboard/`](leaderboard/) displays the current Java fold results from [`leaderboard/data/leaderboard.csv`](leaderboard/data/leaderboard.csv).

The table reports `score` (QI), formal-verification rate, and judge metric means for the released Java fold. Rows correspond to evaluated agent setups. Metric values in the CSV are percentage-scaled report aggregates.

## Project Layout

```text
agent-lens-bench/
├── agent_lens/
│   ├── agent_server/    REST adapter for CLI agents such as Claude Code
│   └── eval/            evaluation CLI, metrics, reporting, comparison, tracking
├── idea-plugin/         IDE benchmark runner and agent integrations
├── leaderboard/         static leaderboard page and CSV data
└── .github/workflows/   CI workflows for benchmark runs and releases
```

Main entry points:

- [`idea-plugin/idea-runner/`](idea-plugin/idea-runner/) registers the `:idea-runner:runHeadless` Gradle task that collects trajectory dumps for the Java fold.
- [`idea-plugin/pycharm-runner/`](idea-plugin/pycharm-runner/) registers the `:pycharm-runner:runHeadless` Gradle task that collects trajectory dumps for the Python fold.
- [`agent_lens/eval/cli/run_agent_bench.py`](agent_lens/eval/cli/run_agent_bench.py) evaluates raw runner dumps and renders single-run reports.
- [`agent_lens/eval/cli/compare_2_runs.py`](agent_lens/eval/cli/compare_2_runs.py) renders side-by-side comparisons for two evaluated runs.
- [`agent_lens/eval/cli/merge_folds_and_publish.py`](agent_lens/eval/cli/merge_folds_and_publish.py) merges multiple folds into a combined run report.
- [`agent_lens/eval/cli/answer_based_on_data.py`](agent_lens/eval/cli/answer_based_on_data.py) answers a custom LLM-judge question over the dataset built from runner dumps.
- [`agent_lens/agent_server/main.py`](agent_lens/agent_server/main.py) exposes CLI agents through the external-agent REST contract.
- [`leaderboard/`](leaderboard/) contains the static leaderboard UI and CSV data.

## Contributing

Adapt AgentLens to your own agent by wiring it in the same way as the bundled integrations — IDE-native like Explyt or CLI like Claude Code — and adjust the datasets and metrics to fit your setup.
We welcome PRs for new agents, datasets, and metrics, as well as bug reports and feature requests filed as GitHub issues.
For questions or discussion, feel free to tag @sergeyrid, @le-oof, or @vlomshakov on the relevant issue or pull request.

### Agents

IDE-native agents implement the JetBrains IDE benchmark engine interface:

```text
idea-plugin/benchmark-common/src/main/kotlin/com/agentlens/benchmark/common/runner/agent/engine/AgentEngine.kt
```

CLI agents can be connected through the REST adapter in [`agent_lens/agent_server/`](agent_lens/agent_server/). On the JetBrains IDE side, external agents are handled by:

```text
idea-plugin/benchmark-common/src/main/kotlin/com/agentlens/benchmark/common/runner/agent/engine/ExternalAgentEngine.kt
```

### Datasets and scenarios

A fold config, for example [`idea-plugin/idea-runner/src/main/resources/config/agent/workflows.json`](idea-plugin/idea-runner/src/main/resources/config/agent/workflows.json), defines the repository, pinned revision, agent engine, scenarios, and user personas.

A new scenario should include a user-simulator prompt, scenario metadata, and one or more verifiers when the requirement is checkable — see [`add_logging`](idea-plugin/idea-runner/src/main/resources/config/agent/scenarios/workflows/en/add_logging) for an example.

### Metrics and verifiers

Use formal verifiers for checkable requirements: tests, expected file changes, regex matches, build output, generated files, or static analysis. Use judge metrics when the evidence is in the trajectory rather than in a final-state predicate.

Verifiers run in the IDE runner and implement the `Verifier` interface (or extend one of the abstract bases there); the bundled ones live under:

```text
idea-plugin/benchmark-common/src/main/kotlin/com/agentlens/benchmark/common/runner/agent/verifiers/
```

Reference a new verifier from a scenario in the fold config.

Judge metric and report code lives under:

```text
agent_lens/eval/metrics/
agent_lens/eval/reporting/
```

A judge metric subclasses `LlmMetric` and `PairwiseLlmMetric`, supplying its single-run and side-by-side prompt instructions. Registering it for the relevant tag in `tag_to_metrics.py` is enough for the reports to include it.

## Development Notes

Evaluation and comparison CLIs can use tracking through [`agent_lens/eval/configs/tracking_config.yaml`](agent_lens/eval/configs/tracking_config.yaml). For local experiments, pass `--disable_tracking true` where supported.

The CI workflow [`run-benchmark.yml`](.github/workflows/run-benchmark.yml) collects, merges, and evaluates the selected folds. Side-by-side comparison via `compare_2_runs.py` is a separate manual step, not part of this workflow.

## Citation

If you use AgentLens in your research, please cite:

```bibtex
@misc{podivilov2026agentlens,
      title={AgentLens: Production-Assessed Trajectory Reviews for Coding Agent Evaluation},
      author={Andrey Podivilov and Vadim Lomshakov and Sergey Savin and Matvei Startsev and Roman Pozharskiy and Maksim Parshin and Sergey Nikolenko},
      year={2026},
      eprint={2607.06624},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2607.06624},
}
```
