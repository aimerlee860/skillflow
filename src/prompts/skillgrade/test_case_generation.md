基于技能定义生成一个测试用例。

## 技能定义

{skill_context}

## 测试规格

- 类型: {test_type_name}
- 目标难度: {difficulty_name}
{function_hint}{boundary_hint}

## 测试类型说明

{test_type_description}

## 难度定义

- **简单** (easy): {difficulty_easy}
- **中等** (medium): {difficulty_medium}
- **困难** (hard): {difficulty_hard}

## 当前目标难度

**{difficulty_name}**: {difficulty_description}

## 输出要求

1. **instruction**: 用户的原始输入
   - 符合目标难度 (简单=完整信息, 困难=缺失关键信息)
   - 自然语言，符合真实用户表达习惯
   - 不要包含处理流程、技术细节等

2. **expected**: 期望的系统答复 (仅正向和演化测试需要)
   - 详细的预期输出内容
   - 包含关键信息点
   - 负向测试填写 "不适用"

3. **difficulty_reasoning**: 说明为什么符合目标难度

## 输出格式 (仅JSON)

```json
{{
  "name": "测试用例名称（简短描述）",
  "instruction": "用户的原始输入",
  "expected_trigger": true或false,
  "expected": "期望的系统答复（负向测试填"不适用"）",
  "difficulty": "easy或medium或hard",
  "difficulty_reasoning": "难度判定理由"
}}
```

只输出JSON，不要其他内容。