你是技能分析专家。请深入分析以下技能定义，提取测试规划所需的全面信息。

## 技能定义

{skill_context}

## 预提取的结构化信息

以下信息已通过程序化解析从技能定义中提取，可直接参考，无需重复解析:

{structural_context}

## 分析任务

请从以下维度进行深入分析:

### 1. 复杂度评估 (每项 1-10 分)

- **步骤复杂度** (step_complexity): 工作流程有多少步骤? 简单的1-3步=1-3分, 中等4-6步=4-6分, 复杂7+步=7-10分
- **参数复杂度** (param_complexity): 需要多少输入参数/字段? 少量1-2个=1-3分, 中等3-5个=4-6分, 很多6+个=7-10分
- **验证复杂度** (validation_complexity): 有多少验证规则/边界条件? 少=1-3分, 中=4-6分, 多=7-10分
- **推理复杂度** (reasoning_complexity): 需要多深层的推理和资源激活? 无需加载额外资源、简单匹配=1-3分, 需加载1-2个references组合推理=4-6分, 需跨多个references/scripts/assets深度推理=7-10分

### 2. 核心功能列表

列出该技能的 3-8 个核心功能点，每个功能包含:
- name: 功能名称 (简短)
- weight: 重要性权重 (0.0-1.0, 所有权重之和建议约等于1.0)
- input_fields: 相关的输入字段列表
- description: 功能的详细行为描述 (说明该功能做什么、如何处理输入、产生什么结果)
- error_conditions: 该功能可能遇到的错误或异常情况 (如输入不合法、条件不满足等)
- output_description: 正常输出的关键特征 (格式、包含哪些关键信息、如何验证正确性)

### 3. 用户场景

识别 3-5 个典型用户使用场景:
- scenario: 场景描述 (用户在什么情况下会使用该技能)
- trigger: 触发意图 (用户想达成什么目的)
- input_traits: 典型输入特征 (用户通常会提供什么信息、以什么方式表达)

### 4. 功能依赖关系

识别核心功能间的依赖关系:
- from: 源功能名称
- to: 目标功能名称
- type: 关系类型 (requires=前置依赖, enhances=增强配合, conflicts=互斥冲突)

如果没有依赖关系，返回空列表。

### 5. 领域约束

提取该技能特有的业务规则和领域知识约束 (3-8条):
- 不是通用的格式/数值校验，而是该技能业务领域特有的规则
- 例如: "转账金额不能超过单日限额"、"处方药必须有医生签名"等
- 每条约束说明其限制条件和违反时的预期行为

### 6. 边界条件类型

识别适用的边界类型 (从以下选项中选择):
- numeric: 数值边界 (最大/最小/零值/负值/超限)
- completeness: 完整性边界 (必填字段缺失/部分缺失)
- format: 格式边界 (错误格式/特殊字符/超长输入)
- business: 业务边界 (该技能特有的业务规则边界)

### 7. 测试策略建议

- **recommended_total**: 建议的总测试用例数量 (综合考虑复杂度和功能数量，建议 4-12)
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
      "input_fields": ["字段1", "字段2"],
      "description": "功能的详细行为描述",
      "error_conditions": ["错误条件1", "错误条件2"],
      "output_description": "正常输出的关键特征"
    }}
  ],
  "user_scenarios": [
    {{
      "scenario": "用户场景描述",
      "trigger": "触发意图",
      "input_traits": "典型输入特征"
    }}
  ],
  "function_dependencies": [
    {{
      "from": "功能A",
      "to": "功能B",
      "type": "requires|enhances|conflicts"
    }}
  ],
  "domain_constraints": [
    "领域约束1",
    "领域约束2"
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
