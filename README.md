# Skillflow

Complete skill lifecycle management: **create**, **evaluate**, and **evolve** AI agent skills.

A unified CLI for managing AI agent skills with LLM-powered creation, comprehensive evaluation, and autonomous evolution capabilities.

## Features

- **LLM-Powered Skill Creation**: Generate high-quality skills using LLM with the skill-creator meta-skill
- **Template Mode**: Fast skill generation without LLM using Jinja2 templates
- **Multi-Language Support**: Automatic language detection (Chinese/English) - output matches input language
- **Skill Evaluation**: Test that AI agents correctly discover and use your skills
- **Skill Evolution**: Automatically improve skills through iterative optimization
- **LangGraph Workflow**: State-machine based evaluation pipeline with ReAct agent pattern

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

# Generate eval.yaml to custom location
skillflow eval ./skills/bank-transfer --init --target ./custom-eval.yaml

# Evaluate with existing eval.yaml (skip generation)
skillflow eval ./skills/bank-transfer --skip-init

# Use specific eval.yaml file
skillflow eval ./skills/bank-transfer --skip-init --config ./custom-eval.yaml

# Other options
skillflow eval ./skills/bank-transfer --trials 5 --keep-workspaces
skillflow eval ./skills/bank-transfer --quiet
```

**Options:**
- `--init`: Only generate eval.yaml, do not evaluate
- `--skip-init`: Skip eval.yaml generation, use existing file
- `--config, -c`: Path to eval.yaml to use (with --skip-init)
- `--target, -t`: Path to generate eval.yaml (only with --init)
- `--trials, -n`: Number of trials per task (default: 5)
- `--output, -o`: Output directory for results
- `--keep-workspaces`: Keep workspace copies for debugging
- `--quiet, -q`: Suppress output
- `--base-url`: LLM API base URL for eval.yaml generation
- `--api-key`: LLM API key for eval.yaml generation
- `--model, -m`: Model name for eval.yaml generation (default: gpt-4o)

### evolve - Automatically improve a skill

```bash
# Basic usage
skillflow evolve ./skills/bank-transfer --trials 5 --iterations 50

# With custom strategy
skillflow evolve ./skills/bank-transfer --strategy autonomous --model gpt-4o

# All options
skillflow evolve ./skills/bank-transfer \
  --trials 5 \
  --iterations 100 \
  --max-time 3600 \
  --patience 20 \
  --strategy hybrid \
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
- `--model`: LLM model for evolution (default: gpt-4o)
- `--keep-workspace`: Keep workspaces after completion
- `--verbose, -v`: Verbose output

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
│   ├── core/             # Config, runner, workspace, eval_config
│   ├── agents/           # Agent implementations
│   ├── graph/            # LangGraph workflow
│   ├── tools/            # Agent tools
│   ├── graders/          # Evaluation graders
│   ├── providers/        # Execution providers
│   └── reporters/        # Result reporters

└── skillevol/         # Skill evolution module
    ├── commands.py       # Evolution CLI
    ├── core/             # Core components
    │   ├── llm.py
    │   ├── types.py
    │   ├── explorer.py
    │   ├── evaluator.py
    │   └── decision.py
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
└── ...
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
