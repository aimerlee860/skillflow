# Skillgrade Python

Complete skill lifecycle management: **create**, **evaluate**, and **evolve** AI agent skills.

This is a Python rewrite of the original [skillgrade](https://github.com/mgechev/skillgrade) project, with added capabilities for skill creation and autonomous evolution.

## Features

- **Skill Creation (skillforge)**: Generate new skills from templates or existing codebases
- **Skill Evaluation (skillgrade)**: Test that AI agents correctly discover and use your skills
- **Skill Evolution (skillevol)**: Automatically improve skills through iterative optimization
- **OpenAI Functions Agent**: Uses function calling for reliable tool usage
- **LangGraph Workflow**: State-machine based evaluation pipeline
- **Dual Graders**: Deterministic (Python) + LLM Rubric evaluation

## Installation

```bash
pip install -e .
```

## Environment Variables

```bash
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_API_KEY="your-api-key"
export LLM_MODEL_NAME="gpt-4o"
```

## Commands

### init - Create a new skill

```bash
# Basic usage
skillgrade init my-skill --description "Review code for bugs"

# With template
skillgrade init my-skill --description "Review code" --template code-review

# With examples and constraints
skillgrade init my-skill \
  --description "Review code for bugs" \
  --example "Review a Python function for security issues" \
  --constraint "Must identify SQL injection risks"
```

Options:
- `--dir, -d`: Directory to create the skill in (default: current directory)
- `--description, -D`: Description of what the skill does (required)
- `--template, -t`: Template to use (default, code-review, documentation, testing)
- `--example, -e`: Add an example (can be used multiple times)
- `--constraint, -C`: Add a constraint (can be used multiple times)

### eval - Evaluate a skill

```bash
skillgrade eval /path/to/skill --trials 5
skillgrade eval /path/to/skill --config /path/to/eval.yaml
skillgrade eval /path/to/skill --keep-workspaces
```

### evolve - Automatically improve a skill

```bash
# Basic usage
skillgrade evolve /path/to/skill --trials 5 --iterations 50

# With custom strategy
skillgrade evolve /path/to/skill --strategy autonomous --llm-model gpt-4o

# All options
skillgrade evolve /path/to/skill \
  --trials 5 \
  --iterations 100 \
  --max-time 3600 \
  --patience 20 \
  --strategy hybrid \
  --program program.md \
  --llm-model gpt-4o \
  --verbose
```

Options:
- `--trials, -n`: Evaluation trials per iteration (default: 5)
- `--iterations, -i`: Maximum iterations (default: 100)
- `--max-time, -t`: Max time in seconds (default: 3600)
- `--patience, -p`: Stop after N no-improvements (default: 20)
- `--strategy, -s`: Exploration strategy: hybrid, autonomous, structured
- `--program`: Path to custom program.md
- `--llm-model, -m`: LLM model name (default: gpt-4o)
- `--keep-workspace`: Keep workspaces after completion
- `--verbose, -v`: Verbose output

### preview - View evaluation results

```bash
skillgrade preview [--results-dir PATH] [--browser]
```

## Project Structure

```
src/
├── skillgrade/       # Core evaluation framework
│   ├── commands/     # CLI commands (eval, preview)
│   ├── core/         # Config, runner, workspace management
│   ├── agents/       # OpenAI Functions Agent
│   ├── graph/        # LangGraph evaluation workflow
│   ├── tools/        # Agent tools (shell, file, glob)
│   ├── graders/      # Deterministic and LLM graders
│   ├── providers/    # Local execution environment
│   └── reporters/    # CLI and browser reporters
│
├── skillforge/       # Skill creation module
│   ├── creator.py    # Skill creator logic
│   └── templates/    # Skill templates
│       ├── default/
│       ├── code-review/
│       ├── documentation/
│       └── testing/
│
└── skillevol/        # Skill evolution module
    ├── commands.py   # Evolution CLI logic
    ├── core/         # Core evolution components
    │   ├── llm.py        # LLM client wrapper
    │   ├── types.py      # Type definitions
    │   ├── explorer.py   # Modification proposer
    │   ├── evaluator.py  # Runs skillgrade
    │   └── decision.py   # Keep/revert decisions
    └── operators/    # Skill modification operators
        ├── clarify.py
        ├── add_examples.py
        └── enhance_constraints.py
```

## Skill Lifecycle

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│  init   │ ──▶ │   eval  │ ──▶ │ evolve  │
│ (create)│     │  (test) │     │ (improve)│
└─────────┘     └─────────┘     └─────────┘
                    ▲                 │
                    └─────────────────┘
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
  - name: example-task
    instruction: |
      Describe what the agent should do.
    workspace:
      - src: fixtures/test.js
        dest: test.js
    graders:
      - type: deterministic
        run: |
          import json
          print(json.dumps({"score": 1.0, "details": "All checks passed"}))
        weight: 0.7
      - type: llm_rubric
        rubric: |
          Evaluate the agent's approach.
        weight: 0.3
```

## Evolution Metric

The optimization target is the **Combined Score**:

```
Combined Score = pass_rate × (1 + pass_at_k) / 2
```

- `pass_rate`: Average evaluation score
- `pass_at_k`: Probability of at least one success in k trials

## License

MIT
