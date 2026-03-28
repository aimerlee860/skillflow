"""Skill analysis module for deep understanding of skill content."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ..types import (
    SkillAnalysis,
    SkillExample,
    SkillMetadata,
    SkillResource,
    SkillSection,
    WorkflowStep,
)


class SkillAnalyzer:
    """深入分析技能内容.

    分析 SKILL.md 的完整内容，包括：
    - 元数据（frontmatter）
    - 各章节内容
    - 关联资源（references/、scripts/、assets/）
    """

    # 章节标题映射（支持中英文）
    SECTION_PATTERNS = {
        "use_cases": [
            r"何时使用",
            r"When to Use",
            r"使用场景",
            r"Use Cases",
            r"适用场景",
        ],
        "core_functions": [
            r"核心功能",
            r"Core Functions?",
            r"主要功能",
            r"Main Functions?",
            r"功能概述",
            r"Features?",
        ],
        "workflow": [
            r"工作流程",
            r"Workflow",
            r"处理流程",
            r"Process",
            r"操作步骤",
            r"Steps?",
        ],
        "validation": [
            r"验证规则",
            r"Validation Rules?",
            r"校验规则",
            r"检查规则",
            r"验证",
        ],
        "examples": [
            r"示例",
            r"Examples?",
            r"用例",
            r"Use Cases",
            r"案例",
            r"Cases?",
        ],
        "errors": [
            r"错误处理",
            r"Error Handling",
            r"异常处理",
            r"Exception Handling",
            r"故障排除",
            r"Troubleshooting",
        ],
        "security": [
            r"安全注意",
            r"Security",
            r"安全事项",
            r"安全",
            r"注意事项",
        ],
        "output": [
            r"输出格式",
            r"Output Format",
            r"输出",
            r"Output",
            r"格式",
            r"Format",
        ],
    }

    def __init__(self):
        """Initialize the skill analyzer."""
        pass

    def analyze(self, skill_dir: Path) -> SkillAnalysis:
        """分析技能目录.

        Args:
            skill_dir: 技能目录路径

        Returns:
            SkillAnalysis: 技能分析结果
        """
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

        # 1. 解析 SKILL.md
        metadata, sections = self._parse_skill_md(skill_md)

        # 2. 读取关联资源
        resources = self._load_resources(skill_dir)

        # 3. 提取关键信息
        use_cases = self._extract_use_cases(sections)
        core_functions = self._extract_functions(sections)
        workflows = self._extract_workflows(sections)
        validation_rules = self._extract_rules(sections)
        examples = self._extract_examples(sections)
        error_conditions = self._extract_errors(sections)
        security_notes = self._extract_security(sections)
        output_formats = self._extract_output_formats(sections)

        return SkillAnalysis(
            metadata=metadata,
            sections=sections,
            resources=resources,
            use_cases=use_cases,
            core_functions=core_functions,
            workflows=workflows,
            validation_rules=validation_rules,
            examples=examples,
            error_conditions=error_conditions,
            security_notes=security_notes,
            output_formats=output_formats,
        )

    def _parse_skill_md(
        self, path: Path
    ) -> tuple[SkillMetadata, list[SkillSection]]:
        """解析 SKILL.md：frontmatter + sections.

        Args:
            path: SKILL.md 文件路径

        Returns:
            Tuple of (metadata, sections)
        """
        content = path.read_text(encoding="utf-8")

        # 解析 YAML frontmatter
        metadata = self._parse_frontmatter(content)

        # 解析 markdown sections
        sections = self._parse_sections(content)

        return metadata, sections

    def _parse_frontmatter(self, content: str) -> SkillMetadata:
        """解析 YAML frontmatter.

        Args:
            content: 文件内容

        Returns:
            SkillMetadata
        """
        # 提取 frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1))
                return SkillMetadata(
                    name=frontmatter.get("name", "unknown"),
                    description=frontmatter.get("description", ""),
                    compatibility=frontmatter.get("compatibility", []),
                )
            except yaml.YAMLError:
                pass

        # 如果没有 frontmatter，尝试从内容推断
        return SkillMetadata(name="unknown", description="", compatibility=[])

    def _parse_sections(self, content: str) -> list[SkillSection]:
        """解析 markdown sections.

        Args:
            content: 文件内容

        Returns:
            List of SkillSection
        """
        sections = []

        # 移除 frontmatter
        content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)

        # 按 ## 标题分割
        pattern = r"^(#{2,4})\s+(.+?)\s*$"
        lines = content.split("\n")

        current_title = ""
        current_content = []
        current_level = 2

        for line in lines:
            match = re.match(pattern, line)
            if match:
                # 保存上一个 section
                if current_title:
                    sections.append(
                        SkillSection(
                            title=current_title,
                            content="\n".join(current_content).strip(),
                            level=current_level,
                        )
                    )
                current_level = len(match.group(1))
                current_title = match.group(2).strip()
                current_content = []
            else:
                # 不是标题行，添加到当前内容
                if current_title:
                    current_content.append(line)

        # 保存最后一个 section
        if current_title:
            sections.append(
                SkillSection(
                    title=current_title,
                    content="\n".join(current_content).strip(),
                    level=current_level,
                )
            )

        return sections

    def _load_resources(self, skill_dir: Path) -> list[SkillResource]:
        """加载 references/、scripts/、assets/ 目录内容.

        Args:
            skill_dir: 技能目录路径

        Returns:
            List of SkillResource
        """
        resources = []

        resource_types = {
            "references": "reference",
            "scripts": "script",
            "assets": "asset",
        }

        for dir_name, resource_type in resource_types.items():
            resource_dir = skill_dir / dir_name
            if resource_dir.exists() and resource_dir.is_dir():
                for file_path in resource_dir.iterdir():
                    if file_path.is_file():
                        try:
                            content = file_path.read_text(encoding="utf-8")
                            resources.append(
                                SkillResource(
                                    path=str(file_path.relative_to(skill_dir)),
                                    type=resource_type,
                                    content=content,
                                )
                            )
                        except (UnicodeDecodeError, IOError):
                            # 跳过二进制文件或无法读取的文件
                            continue

        return resources

    def _find_section_by_patterns(
        self, sections: list[SkillSection], patterns: list[str]
    ) -> SkillSection | None:
        """根据标题模式查找章节.

        Args:
            sections: 章节列表
            patterns: 标题模式列表

        Returns:
            匹配的章节或 None
        """
        for section in sections:
            for pattern in patterns:
                if re.search(pattern, section.title, re.IGNORECASE):
                    return section
        return None

    def _extract_list_items(self, content: str) -> list[str]:
        """从内容中提取列表项.

        Args:
            content: markdown 内容

        Returns:
            List of list item strings
        """
        items = []
        lines = content.split("\n")

        for line in lines:
            # 匹配 - 开头的列表项
            match = re.match(r"^\s*[-*]\s+(.+)$", line)
            if match:
                item = match.group(1).strip()
                # 移除加粗标记
                item = re.sub(r"\*\*(.+?)\*\*", r"\1", item)
                items.append(item)

        return items

    def _extract_use_cases(self, sections: list[SkillSection]) -> list[str]:
        """提取"何时使用"章节的要点."""
        section = self._find_section_by_patterns(
            sections, self.SECTION_PATTERNS["use_cases"]
        )
        if not section:
            return []

        return self._extract_list_items(section.content)

    def _extract_functions(self, sections: list[SkillSection]) -> list[str]:
        """提取核心功能章节."""
        section = self._find_section_by_patterns(
            sections, self.SECTION_PATTERNS["core_functions"]
        )
        if not section:
            return []

        # 提取子标题作为功能点
        functions = []
        lines = section.content.split("\n")

        for line in lines:
            # 匹配 ### 子标题（可能带编号，如 "### 1. xxx"）
            match = re.match(r"^#{3,4}\s+(.+)$", line)
            if match:
                func = match.group(1).strip()
                # 移除编号（如 "1. "、"2. " 等）
                func = re.sub(r"^\d+\.\s*", "", func)
                if func:
                    functions.append(func)

        # 如果父章节没有内容，查找其 ### 子章节
        if not functions:
            # 查找紧跟在核心功能章节后的 ### 级别章节
            found_parent = False
            for s in sections:
                if s.title == section.title:
                    found_parent = True
                    continue
                if found_parent and s.level == 3:
                    func = re.sub(r"^\d+\.\s*", "", s.title)
                    functions.append(func)
                elif found_parent and s.level == 2:
                    # 遇到下一个 ## 级别，停止
                    break

        # 如果仍然没有，尝试提取列表项
        if not functions:
            functions = self._extract_list_items(section.content)

        return functions

    def _extract_workflows(self, sections: list[SkillSection]) -> list[WorkflowStep]:
        """提取工作流程章节."""
        section = self._find_section_by_patterns(
            sections, self.SECTION_PATTERNS["workflow"]
        )
        if not section:
            return []

        steps = []

        # 首先查找紧跟在工作流程章节后的 ### 级别步骤章节
        found_parent = False
        for s in sections:
            if s.title == section.title:
                found_parent = True
                continue
            if found_parent and s.level == 3:
                # 解析步骤标题，如 "步骤1：收集转账信息"
                match = re.match(
                    r"^(?:步骤\s*(\d+)|Step\s*(\d+)|(\d+)\.)\s*[:：]?\s*(.+)$",
                    s.title,
                )
                if match:
                    order = int(match.group(1) or match.group(2) or match.group(3) or len(steps) + 1)
                    name = match.group(4).strip() if match.group(4) else s.title
                else:
                    order = len(steps) + 1
                    name = s.title

                steps.append(
                    WorkflowStep(
                        name=name,
                        description=s.content.strip(),
                        order=order,
                    )
                )
            elif found_parent and s.level == 2:
                # 遇到下一个 ## 级别，停止
                break

        # 如果没有从子章节提取到步骤，尝试从内容中解析
        if not steps:
            lines = section.content.split("\n")
            current_step = None
            current_content = []

            for line in lines:
                # 匹配步骤标题（如 "步骤1："、"Step 1:"、"1. "）
                match = re.match(
                    r"^(?:步骤\s*(\d+)|Step\s*(\d+)|(\d+)\.)\s*[:：]?\s*(.+)$", line
                )
                if match:
                    # 保存上一个步骤
                    if current_step:
                        steps.append(
                            WorkflowStep(
                                name=current_step["name"],
                                description="\n".join(current_content).strip(),
                                order=current_step["order"],
                            )
                        )

                    # 提取步骤编号和名称
                    order = int(match.group(1) or match.group(2) or match.group(3))
                    name = match.group(4).strip()
                    current_step = {"name": name, "order": order}
                    current_content = []
                elif current_step:
                    # 添加到当前步骤的描述
                    if line.strip():
                        current_content.append(line)

            # 保存最后一个步骤
            if current_step:
                steps.append(
                    WorkflowStep(
                        name=current_step["name"],
                        description="\n".join(current_content).strip(),
                        order=current_step["order"],
                    )
                )

        return steps

    def _extract_rules(self, sections: list[SkillSection]) -> list[str]:
        """提取验证规则章节."""
        section = self._find_section_by_patterns(
            sections, self.SECTION_PATTERNS["validation"]
        )
        if not section:
            return []

        rules = []

        # 提取子标题和列表项
        lines = section.content.split("\n")
        current_sub_title = ""

        for line in lines:
            # 匹配子标题
            match = re.match(r"^#{3,4}\s+(.+)$", line)
            if match:
                current_sub_title = match.group(1).strip()
                continue

            # 匹配列表项
            list_match = re.match(r"^\s*[-*]\s+(.+)$", line)
            if list_match:
                item = list_match.group(1).strip()
                if current_sub_title:
                    rules.append(f"{current_sub_title}: {item}")
                else:
                    rules.append(item)

        return rules

    def _extract_examples(self, sections: list[SkillSection]) -> list[SkillExample]:
        """提取示例章节."""
        section = self._find_section_by_patterns(
            sections, self.SECTION_PATTERNS["examples"]
        )
        if not section:
            return []

        examples = []

        # 首先查找紧跟在示例章节后的 ### 级别示例章节
        found_parent = False
        for s in sections:
            if s.title == section.title:
                found_parent = True
                continue
            if found_parent and s.level == 3:
                # 解析示例标题，如 "示例1：个人转账"
                match = re.match(
                    r"^(?:示例\s*(\d+)|Example\s*(\d+))[:：]?\s*(.+)$",
                    s.title,
                    re.IGNORECASE,
                )
                if match:
                    name = match.group(3).strip() if match.group(3) else s.title
                else:
                    name = s.title

                # 从内容中提取输入和输出
                content = s.content
                input_text = ""
                output_text = ""

                # 匹配用户输入（遇到处理步骤、处理流程、技能输出、代码块等就停止）
                # 注意：必须匹配到非空内容，否则不算有效输入
                input_match = re.search(
                    r"(?:\*\*用户输入\*\*|\*\*Input\*\*|用户输入|Input)[:：]?\s*[\"\']?([^\n].+?)(?=\*\*处理步骤|\*\*处理流程|\*\*技能输出|\*\*Output|\*\*技能\*输出|技能输出|处理步骤|处理流程|```|\n\n|$)",
                    content,
                    re.IGNORECASE | re.DOTALL,
                )
                if input_match:
                    input_text = input_match.group(1).strip()
                    # 清理引号和尾部空白
                    input_text = input_text.strip("\"'").strip()

                # 匹配技能输出（代码块）
                output_match = re.search(
                    r"(?:技能输出|Output)[:：]?\s*```[^\n]*\n(.+?)```",
                    content,
                    re.IGNORECASE | re.DOTALL,
                )
                if output_match:
                    output_text = output_match.group(1).strip()

                examples.append(
                    SkillExample(name=name, input=input_text, expected_output=output_text)
                )
            elif found_parent and s.level == 2:
                # 遇到下一个 ## 级别，停止
                break

        # 如果没有从子章节提取到示例，尝试从内容中解析
        if not examples:
            content = section.content

            # 尝试匹配代码块
            code_blocks = re.findall(r"```.*?\n(.+?)```", content, re.DOTALL)
            for i, block in enumerate(code_blocks):
                examples.append(
                    SkillExample(
                        name=f"Example {i + 1}",
                        input="",
                        expected_output=block.strip(),
                    )
                )

        return examples

    def _extract_errors(self, sections: list[SkillSection]) -> list[str]:
        """提取错误处理条件."""
        section = self._find_section_by_patterns(
            sections, self.SECTION_PATTERNS["errors"]
        )
        if not section:
            return []

        return self._extract_list_items(section.content)

    def _extract_security(self, sections: list[SkillSection]) -> list[str]:
        """提取安全注意事项."""
        section = self._find_section_by_patterns(
            sections, self.SECTION_PATTERNS["security"]
        )
        if not section:
            return []

        return self._extract_list_items(section.content)

    def _extract_output_formats(self, sections: list[SkillSection]) -> list[str]:
        """提取输出格式要求."""
        section = self._find_section_by_patterns(
            sections, self.SECTION_PATTERNS["output"]
        )
        if not section:
            return []

        formats = []

        # 提取格式模板标题
        lines = section.content.split("\n")
        for line in lines:
            match = re.match(r"^#{3,4}\s+(.+)$", line)
            if match:
                formats.append(match.group(1).strip())

        return formats
