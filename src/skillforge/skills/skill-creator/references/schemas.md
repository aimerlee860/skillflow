# Skill Schemas

This document defines the JSON structures used for skill evaluation and benchmarking.

## SKILL.md Structure

```yaml
---
name: skill-name           # Required: lowercase, hyphens, 1-64 chars
description: When to use   # Required: primary triggering mechanism
---

# Skill Title

[Markdown instructions...]
```

## evals.json Schema

Test cases for skill evaluation:

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "The user's task prompt",
      "expected_output": "Description of expected result",
      "files": ["optional/input/files"],
      "assertions": [
        {
          "name": "descriptive-check-name",
          "type": "contains|matches|llm_rubric|custom",
          "expected": "Expected value or rubric",
          "weight": 1.0
        }
      ]
    }
  ]
}
```

## eval_metadata.json Schema

Per-eval metadata during iteration:

```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name-here",
  "prompt": "The user's task prompt",
  "assertions": [
    {
      "name": "check-name",
      "type": "contains",
      "expected": "expected text",
      "weight": 1.0
    }
  ]
}
```

## grading.json Schema

Results from grading assertions:

```json
{
  "eval_id": 0,
  "run_type": "with_skill|without_skill|old_skill",
  "timestamp": "2024-01-01T00:00:00Z",
  "expectations": [
    {
      "text": "Assertion description",
      "passed": true,
      "evidence": "Why this passed or failed"
    }
  ]
}
```

## benchmark.json Schema

Aggregated benchmark results:

```json
{
  "skill_name": "example-skill",
  "iteration": 1,
  "timestamp": "2024-01-01T00:00:00Z",
  "configs": [
    {
      "name": "with_skill",
      "pass_rate": 0.85,
      "mean_time_seconds": 12.5,
      "stddev_time": 2.1,
      "mean_tokens": 8500,
      "stddev_tokens": 500,
      "per_eval": [
        {
          "eval_id": 0,
          "passed": 3,
          "total": 3,
          "time_seconds": 10.2,
          "tokens": 8000
        }
      ]
    }
  ],
  "delta": {
    "pass_rate_improvement": 0.15,
    "time_change": -2.5,
    "token_change": 500
  }
}
```

## timing.json Schema

Captured from subagent notifications:

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

## feedback.json Schema

User feedback from the eval viewer:

```json
{
  "reviews": [
    {
      "run_id": "eval-0-with_skill",
      "feedback": "The output was missing X",
      "timestamp": "2024-01-01T00:00:00Z"
    }
  ],
  "status": "complete"
}
```
