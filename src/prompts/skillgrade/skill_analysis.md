你是技能分析专家。请分析以下技能定义，提取测试规划所需的信息。

## 技能定义

{skill_context}

## 分析任务

请从以下维度进行量化分析:

### 1. 复杂度评估 (每项 1-10 分)

- **步骤复杂度** (step_complexity): 工作流程有多少步骤? 简单的1-3步=1-3分, 中等4-6步=4-6分, 复杂7+步=7-10分
- **参数复杂度** (param_complexity): 需要多少输入参数/字段? 少量1-2个=1-3分, 中等3-5个=4-6分, 很多6+个=7-10分
- **验证复杂度** (validation_complexity): 有多少验证规则/边界条件? 少=1-3分, 中=4-6分, 多=7-10分
- **推理复杂度** (reasoning_complexity): 需要多深层的推理? 简单匹配=1-3分, 需要组合=4-6分, 需要深层推理=7-10分

### 2. 核心功能列表

列出该技能的 3-8 个核心功能点，每个功能包含:
- name: 功能名称 (简短)
- weight: 重要性权重 (0.0-1.0, 所有权重之和建议约等于1.0)
- input_fields: 相关的输入字段列表

### 3. 边界条件类型

识别适用的边界类型 (从以下选项中选择):
- numeric: 数值边界 (最大/最小/零值/负值/超限)
- completeness: 完整性边界 (必填字段缺失/部分缺失)
- format: 格式边界 (错误格式/特殊字符/超长输入)
- business: 业务边界 (该技能特有的业务规则边界)

### 4. 测试策略建议

- **recommended_total**: 建议的总测试用例数量 (综合考虑复杂度，建议 6-20)
- **type_weights**: 各类型测试的推荐权重 (positive, negative, evolved, boundary，总和为1.0)

## 输出格式 (仅JSON)

```json
{{
  "complexity_factors": {{
    "step_complexity": 1-10,
    "param_complexity": 1-10,
    "validation_complexity": 1-10,
    "reasoning_complexity": 1-10
  }},
  "core_functions": [
    {{
      "name": "功能名称",
      "weight": 0.0-1.0,
      "input_fields": ["字段1", "字段2"]
    }}
  ],
  "boundary_types": ["numeric", "completeness", ...],
  "test_strategy": {{
    "recommended_total": 10,
    "type_weights": {{
      "positive": 0.40,
      "negative": 0.20,
      "evolved": 0.20,
      "boundary": 0.20
    }}
  }}
}}
```

只输出JSON，不要其他内容。