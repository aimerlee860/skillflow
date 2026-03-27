# Skillflow

Complete skill lifecycle management: **create**, **evaluate**, and **evolve** AI agent skills.

A unified CLI for managing AI agent skills with LLM-powered creation, comprehensive evaluation, and autonomous evolution capabilities.

## Features

- **LLM-Powered Skill Creation**: Generate high-quality skills using LLM with the skill-creator meta-skill
- **Template Mode**: Fast skill generation without LLM using Jinja2 templates
- **Multi-Language Support**: Automatic language detection (Chinese/English) - output matches input language
- **Comprehensive Evaluation**: TASK-level and SKILL-level metrics with skill tracking
- **Autonomous Evolution**: AI-driven skill improvement with intelligent operator selection
- **LangGraph Workflow**: State-machine based evaluation pipeline with ReAct agent pattern
- **DeepAgents Integration**: Native skill support via deepagents framework with progressive disclosure
- **Skill Trigger Detection**: Automatic detection of skill file access (SKILL.md, references/, scripts/)

## Installation

```bash
# Using uv (recommended)
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .

# Or install from wheel
uv pip install dist/skillflow-0.1.0-py3-none-any.whl --force-reinstall
```

> **Note**: Due to the `src/` layout structure, the `cli.py` entry point requires proper packaging configuration. If you encounter `ModuleNotFoundError: No module named 'cli'`, reinstall from wheel:
> ```bash
> uv build --wheel
> uv pip install dist/skillflow-0.1.0-py3-none-any.whl --force-reinstall
> ```

## Environment Variables

```bash
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_API_KEY="your-api-key"
export LLM_MODEL_NAME="gpt-4o"  # Optional, defaults to gpt-4o
```

## Commands

### create - Create a new skill

**LLM mode (default)** - High-quality skill generation using LLM:

```bash
# Basic usage
skillflow create bank-transfer --desc "处理银行转账业务"

# Long description from file
skillflow create complex-skill --file ./requirements.md

# With examples and constraints
skillflow create my-skill \
  --desc "Review Python code" \
  --example "Check for SQL injection vulnerabilities" \
  --constraint "Must follow PEP 8 style"

# From existing codebase
skillflow create project-helper --file ./README.md --from-codebase ./my-project

# With custom LLM settings
skillflow create my-skill --desc "..." --model gpt-4o --base-url https://api.openai.com/v1
```

**Template mode** - Fast generation without LLM:

```bash
skillflow create my-skill --desc "Review code" --no-llm
skillflow create my-skill --desc "Review code" --no-llm --template code-review
```

**Options:**
- `--desc, -d`: Brief description of the skill
- `--file, -f`: Read description from file (for long descriptions)
- `--no-llm`: Use template mode instead of LLM
- `--lang, -L`: Output language (auto, zh, en). Default: auto-detect
- `--dir`: Output directory (default: ./skills)
- `--template, -t`: Template style (default, code-review, documentation, testing)
- `--example, -e`: Add an example (can be used multiple times)
- `--constraint, -C`: Add a constraint (can be used multiple times)
- `--context, -c`: Additional context for LLM mode
- `--from-codebase`: Analyze codebase to create skill (LLM mode)
- `--base-url`: LLM API base URL (default: LLM_BASE_URL env)
- `--api-key`: LLM API key (default: LLM_API_KEY env)
- `--model, -m`: Model name (default: LLM_MODEL_NAME env or gpt-4o)

### eval - Evaluate a skill

```bash
# Generate eval.yaml and evaluate (default behavior)
skillflow eval ./skills/bank-transfer

# Only generate eval.yaml, do not evaluate
skillflow eval ./skills/bank-transfer --init

# Evaluate with existing eval.yaml (skip generation)
skillflow eval ./skills/bank-transfer --skip-init

# Use specific eval.yaml file
skillflow eval ./skills/bank-transfer --skip-init --config ./custom-eval.yaml

# Other options
skillflow eval ./skills/bank-transfer --trials 5 --keep-workspaces
skillflow eval ./skills/bank-transfer --quiet

# Parallel evaluation (run multiple tasks concurrently)
skillflow eval ./skills/bank-transfer --parallel 4
skillflow eval ./skills/bank-transfer -j 4  # shorthand
```

**Options:**
- `--init`: Only generate eval.yaml, do not evaluate
- `--skip-init`: Skip eval.yaml generation, use existing file
- `--config, -c`: Path to eval.yaml to use (with --skip-init)
- `--target, -t`: Path to generate eval.yaml (only with --init)
- `--trials, -n`: Number of trials per task (default: 5)
- `--parallel, -j`: Number of tasks to evaluate in parallel (default: 1, sequential)
- `--output, -o`: Output directory for results
- `--keep-workspaces`: Keep workspace copies for debugging
- `--quiet, -q`: Suppress output
- `--base-url`: LLM API base URL for eval.yaml generation
- `--api-key`: LLM API key for eval.yaml generation
- `--model, -m`: Model name for eval.yaml generation (default: gpt-4o)

### evolve - Automatically improve a skill

```bash
# Basic usage (steady mode by default)
skillflow evolve ./skills/bank-transfer --trials 5 --iterations 50

# Greedy mode - evolve from current best
skillflow evolve ./skills/bank-transfer --mode greedy

# With custom strategy
skillflow evolve ./skills/bank-transfer --strategy autonomous --model gpt-4o

# All options
skillflow evolve ./skills/bank-transfer \
  --trials 5 \
  --iterations 100 \
  --max-time 3600 \
  --patience 20 \
  --strategy hybrid \
  --mode steady \
  --model gpt-4o \
  --keep-workspace \
  --verbose
```

**Options:**
- `--config, -c`: Path to eval.yaml configuration
- `--trials, -n`: Evaluation trials per iteration (default: 5)
- `--iterations, -i`: Maximum iterations (default: 100)
- `--max-time, -t`: Max time in seconds (default: 3600)
- `--patience, -p`: Stop after N no-improvements (default: 20)
- `--strategy, -s`: Exploration strategy (hybrid, autonomous, structured)
- `--mode, -M`: Evolution mode - steady (from baseline) or greedy (from best)
- `--model`: LLM model for evolution (default: gpt-4o)
- `--parallel, -j`: Number of tasks to evaluate in parallel (default: 1)
- `--keep-workspace`: Keep workspaces after completion
- `--verbose, -v`: Verbose output

## Evaluation Metrics

Skillflow uses a two-tier metric system for comprehensive skill evaluation:

### TASK-level Metrics

| Metric | Description |
|--------|-------------|
| `pass_rate` | Single trial success rate |
| `pass_at_k` | Probability of at least 1 success in K trials |
| `pass_pow_k` | Probability of all K trials succeeding |
| `reward` | Weighted average score from graders |

### SKILL-level Metrics

| Metric | Description |
|--------|-------------|
| `access_rate` | Trigger accuracy - how often the skill is used when appropriate |
| `deep_usage_rate` | How deeply the skill content is utilized |
| `false_positive_rate` | How often the skill is triggered inappropriately |
| `effective_usage_rate` | Overall effectiveness of skill usage |
| `quality_score` | Comprehensive quality score combining all factors |

### Combined Score Calculation

```
combined_score =
    0.25 × pass_pow_k +      # Consistency (most important)
    0.15 × pass_at_k +        # Reliability
    0.15 × reward +           # Output quality
    0.20 × trigger_accuracy + # access_rate × (1 - false_positive_rate)
    0.15 × usage_depth +      # effective_usage_rate × (1 + deep_usage_rate) / 2
    0.10 × quality_score      # Overall quality
```

## Skill Evolution System

### Evolution Modes

The evolution system supports two modes with different strategies for skill improvement:

| Mode | Flag | Starting Point | Acceptance Criteria | Best For |
|------|------|----------------|---------------------|----------|
| **Steady** | `--mode steady` (default) | Always from baseline | Score > baseline | Diverse exploration, avoiding local optima |
| **Greedy** | `--mode greedy` | From current best | Score > best + 0.01 | Fast convergence, maximum score |

**Steady Mode (Default):**
- Each iteration starts from the original skill
- Accepts any improvement over baseline
- Explores more diverse solutions
- Better for discovering unexpected improvements

**Greedy Mode:**
- Each iteration starts from the current best skill
- Only accepts significant improvements (> 0.01 threshold)
- Converges faster to optimal solution
- Better for fine-tuning already good skills

```bash
# Steady mode - explore diverse improvements from baseline
skillflow evolve ./skills/my-skill --mode steady

# Greedy mode - converge quickly from best known
skillflow evolve ./skills/my-skill --mode greedy
```

### Evolution Strategies

1. **hybrid** (default): Structured operators first, then autonomous exploration
2. **autonomous**: LLM freely explores improvements
3. **structured**: Only use predefined operators

### Operators

| Operator | Purpose | When Used |
|----------|---------|-----------|
| `CLARIFY` | Improve instruction clarity | Low reliability, under-triggering |
| `ADD_EXAMPLES` | Add concrete examples | Unstable results, shallow usage |
| `ENHANCE_CONSTRAINTS` | Strengthen requirements | Inconsistency, over-triggering |
| `AUTONOMOUS` | Free-form LLM exploration | After 3+ consecutive no-improvements |

### Intelligent Operator Selection

The system diagnoses issues based on metrics and selects the most appropriate operator:

```
Diagnosed Issue          → Recommended Operator(s)
─────────────────────────────────────────────────────
low_reliability          → CLARIFY (2x), ADD_EXAMPLES (1.5x)
unstable                 → ADD_EXAMPLES (2x), CLARIFY (1.3x)
inconsistent             → ENHANCE_CONSTRAINTS (2x)
over_triggering          → ENHANCE_CONSTRAINTS (2.5x)
under_triggering         → CLARIFY (2x)
shallow_usage            → ADD_EXAMPLES (2x), CLARIFY (1.5x)
ineffective_usage        → ADD_EXAMPLES (2x), ENHANCE_CONSTRAINTS (1.5x)
```

Operator effectiveness is tracked throughout evolution to improve future selections.

## Project Structure

```
src/
├── cli.py             # Unified CLI entry point

├── skillforge/        # Skill creation module
│   ├── __init__.py
│   ├── creator.py         # Template-based skill creator
│   ├── agent_creator.py   # LLM-powered skill creator (ReAct agent)
│   ├── skills/            # Built-in skills
│   │   └── skill-creator/     # Meta-skill for creating other skills
│   └── templates/         # Skill templates
│       ├── default/
│       ├── code-review/
│       ├── documentation/
│       └── testing/

├── skillgrade/        # Skill evaluation module
│   ├── cli.py
│   ├── commands/         # CLI commands
│   ├── core/             # Config, metrics, skill_tracking
│   │   ├── metrics.py        # Metric definitions
│   │   ├── skill_tracking.py # Skill file access tracking
│   │   └── skill_stats.py    # Skill statistics
│   ├── agents/           # Agent implementations
│   │   ├── base.py           # Base agent interface
│   │   └── deep_agent.py     # DeepAgents integration with skill tracking
│   ├── middleware/       # Agent middleware
│   │   └── skill_tracking.py # Skill access tracking middleware
│   ├── graph/            # LangGraph workflow
│   ├── tools/            # Agent tools
│   ├── graders/          # Evaluation graders
│   │   ├── llm_rubric.py     # LLM-based rubric grading
│   │   └── trigger_grader.py # Skill trigger detection
│   └── reporters/        # Result reporters

└── skillevol/         # Skill evolution module
    ├── commands.py       # Evolution CLI
    ├── core/             # Core components
    │   ├── types.py         # EvalResult, ExperimentRecord
    │   ├── explorer.py      # Intelligent operator selection
    │   ├── evaluator.py     # Metric parsing
    │   └── decision.py      # Keep/revert decisions
    └── operators/        # Skill modification operators
        ├── clarify.py
        ├── add_examples.py
        └── enhance_constraints.py
```

## Skill Lifecycle

```
┌─────────────┐     ┌─────────────────┐     ┌─────────┐
│   create    │ ──▶ │      eval       │ ──▶ │ evolve  │
│ (SKILL.md)  │     │ (eval.yaml +    │     │(improve)│
│             │     │  evaluation)    │     │         │
└─────────────┘     └─────────────────┘     └─────────┘
                            ▲                     │
                            └─────────────────────┘
                              (iterate & refine)
```

**Workflow:**

1. `skillflow create my-skill --desc "..."` → Creates SKILL.md
2. `skillflow eval ./skills/my-skill` → Generates eval.yaml and evaluates
3. `skillflow evolve ./skills/my-skill` → Automatically improves the skill

## Generated Skill Structure

When you run `skillflow create`, it generates:

```
skills/my-skill/
├── SKILL.md           # Main skill file with YAML frontmatter
├── references/        # Optional: detailed documentation
│   ├── formats.md
│   └── guidelines.md
└── scripts/           # Optional: helper scripts
    └── helper.py
```

When you run `skillflow eval`, it generates `eval.yaml`:

```
skills/my-skill/
├── SKILL.md           # Created by 'skillflow create'
├── eval.yaml          # Created by 'skillflow eval' (or 'skillflow eval --init')
└── results/           # Evaluation results
    └── results_YYYYMMDD_HHMMSS.tsv
```

## SKILL.md Format

```markdown
---
name: my-skill
description: What this skill does. Use when users need to...
---

# My Skill

Detailed instructions for the AI agent...

## Examples
...

## Constraints
...
```

## eval.yaml Configuration

```yaml
version: "1"

defaults:
  agent: openai
  provider: local
  trials: 5
  timeout: 300
  threshold: 0.8
  grader_model: gpt-4o
  # LLM-first evaluation with optional rule files (0.8/0.2 weight)
  evaluation_mode: llm_primary

tasks:
  - name: basic-task
    prompt: |
      Describe what the agent should do.
    workspace:
      files:
        test.txt: |
          Sample input content
    expect:
      exit_code: 0
    graders:
      - type: llm_rubric
        rubric: |
          Evaluate whether the agent correctly completed the task.
          Score 1.0 for success, 0.5 for partial, 0.0 for failure.
        weight: 1.0
```

## Language Support

Skillflow automatically detects the input language:

```bash
# Chinese input → Chinese output
skillflow create bank-transfer --desc "处理银行转账业务"

# English input → English output
skillflow create bank-transfer --desc "Process bank transfers"

# Override language detection
skillflow create my-skill --desc "处理转账" --lang en
```

## Dependencies

- **langchain** / **langgraph**: Agent framework and workflow
- **langchain-openai**: OpenAI LLM integration
- **deepagents**: DeepAgents framework with native skill support and progressive disclosure
- **jinja2**: Template engine for skill generation
- **pyyaml**: YAML configuration parsing
- **httpx**: HTTP client
- **rich** / **typer**: CLI formatting
- **anthropic** / **openai**: LLM API clients

## Requirements

- Python >= 3.12
- OpenAI-compatible API (OpenAI, Azure, or self-hosted)

## License

MIT
