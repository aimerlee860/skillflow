从技能示例中提取并生成完整的测试用例。

## 技能定义

{skill_context}

## 原始示例

示例名称: {example_name}
示例内容:
{example_input}
{example_expected_output}

## 任务

请从上面的原始示例中：

1. **提取用户输入 (instruction)**:
   - 只提取用户的原始输入，不要包含任何处理步骤、技术细节或说明
   - 如果原始内容中有引号包裹的用户输入，提取引号内的内容
   - 确保提取的是纯粹的用户请求

2. **生成期望输出 (expected)**:
   - 根据技能定义，生成系统应该返回的详细输出
   - 输出应该包含关键信息（如金额、账号、日期等）
   - 格式应该符合技能定义的要求
   - 如果技能有输出格式要求，按照格式生成

3. **判定难度**:
   - 简单(easy): 信息完整，可直接执行
   - 中等(medium): 部分信息缺失
   - 困难(hard): 关键信息严重缺失

## 输出格式 (仅JSON)

```json
{{
  "name": "示例-{example_name}",
  "instruction": "用户的原始输入（只包含用户说的话，不要任何额外内容）",
  "expected_trigger": true,
  "expected": "期望的系统答复（详细、格式化）",
  "difficulty": "easy或medium或hard",
  "difficulty_reasoning": "难度判定理由"
}}
```

只输出JSON，不要其他内容。