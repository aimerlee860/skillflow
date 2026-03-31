"""Test planning module - plans test cases based on skill profile.

This module provides:
1. Calculate total test count based on complexity
2. Allocate test types (positive/negative/evolved/boundary)
3. Allocate difficulty levels
4. Generate test case specifications
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..types import (
    ComplexityLevel,
    DifficultyLevel,
    SkillProfile,
    TestCaseSpec,
    TestPlan,
    TestType,
)


class TestPlanner:
    """Plans test cases based on skill profile.

    The planner:
    1. Calculates appropriate number of tests based on complexity
    2. Distributes tests across types (positive/negative/evolved/boundary)
    3. Assigns difficulty levels to meet target distribution
    4. Ensures core functions are covered
    """

    # Default type distribution weights
    DEFAULT_TYPE_WEIGHTS = {
        TestType.POSITIVE: 0.40,
        TestType.NEGATIVE: 0.20,
        TestType.EVOLVED: 0.20,
        TestType.BOUNDARY: 0.20,
    }

    # Target difficulty distribution
    DIFFICULTY_TARGETS = {
        DifficultyLevel.EASY: 0.30,
        DifficultyLevel.MEDIUM: 0.50,
        DifficultyLevel.HARD: 0.20,
    }

    def plan(self, profile: SkillProfile) -> TestPlan:
        """Generate test plan from skill profile.

        Args:
            profile: Skill analysis result

        Returns:
            TestPlan with test case specifications
        """
        # Step 1: Calculate total test count
        total = self._calculate_total_count(profile)

        # Step 2: Allocate test types
        type_allocation = self._allocate_types(profile, total)

        # Step 3: Allocate difficulty levels
        difficulty_allocation = self._allocate_difficulty(total)

        # Step 4: Generate test case specifications
        specs = self._generate_specs(
            profile=profile,
            type_allocation=type_allocation,
            difficulty_allocation=difficulty_allocation,
            total=total,
        )

        return TestPlan(
            total_count=total,
            cases=specs,
            type_distribution=type_allocation,
            difficulty_distribution=difficulty_allocation,
        )

    def _calculate_total_count(self, profile: SkillProfile) -> int:
        """Get total test count from skill profile's recommended_total."""
        return profile.recommended_total

    def _allocate_types(
        self, profile: SkillProfile, total: int
    ) -> dict[TestType, int]:
        """Allocate tests across types.

        Adjusts allocation based on skill characteristics:
        - Reduce boundary tests if no numeric boundaries
        - Reduce negative tests for simple skills
        """
        # Start with profile weights or defaults
        weights = {}
        for tt in TestType:
            if tt.value in profile.type_weights:
                weights[tt] = profile.type_weights[tt.value]
            else:
                weights[tt] = self.DEFAULT_TYPE_WEIGHTS.get(tt, 0.2)

        # Adjust boundary weight based on boundary types
        if "numeric" not in profile.boundary_types:
            weights[TestType.BOUNDARY] *= 0.5

        # Adjust negative weight for simple skills
        if profile.complexity == ComplexityLevel.SIMPLE:
            weights[TestType.NEGATIVE] *= 0.7

        # Normalize and allocate
        return self._normalize_and_allocate(weights, total)

    def _allocate_difficulty(self, total: int) -> dict[DifficultyLevel, int]:
        """Allocate difficulty levels.

        Target distribution:
        - Easy: 30%
        - Medium: 50%
        - Hard: 20%
        """
        allocation = {}

        for level, target in self.DIFFICULTY_TARGETS.items():
            allocation[level] = max(1, int(total * target))

        # Adjust to match total
        current_total = sum(allocation.values())
        if current_total < total:
            # Add to medium (most flexible)
            allocation[DifficultyLevel.MEDIUM] += total - current_total
        elif current_total > total:
            # Remove from medium
            allocation[DifficultyLevel.MEDIUM] -= current_total - total

        return allocation

    def _normalize_and_allocate(
        self, weights: dict[TestType, float], total: int
    ) -> dict[TestType, int]:
        """Normalize weights and allocate integer counts.

        Guarantees each type gets at least 1 when total >= num_types,
        otherwise distributes proportionally with no negative remainder.
        """
        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight == 0:
            equal_weight = 1.0 / len(weights)
            weights = {k: equal_weight for k in weights}
        else:
            weights = {k: v / total_weight for k, v in weights.items()}

        num_types = len(weights)

        # If total <= number of types, give 1 to highest-weighted types
        if total <= num_types:
            allocation = {tt: 0 for tt in weights}
            sorted_types = sorted(weights.keys(), key=lambda t: weights[t], reverse=True)
            for i in range(total):
                allocation[sorted_types[i]] = 1
            return allocation

        # Normal allocation: each type gets at least 1, remainder by weight
        allocation = {tt: 1 for tt in weights}
        remaining = total - num_types

        # Distribute remaining proportionally by weight
        sorted_types = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        for i, (test_type, weight) in enumerate(sorted_types):
            if i == len(sorted_types) - 1:
                allocation[test_type] += remaining
            else:
                extra = max(0, int(total * weight) - 1)
                allocation[test_type] += extra
                remaining -= extra

        return allocation

    def _generate_specs(
        self,
        profile: SkillProfile,
        type_allocation: dict[TestType, int],
        difficulty_allocation: dict[DifficultyLevel, int],
        total: int,
    ) -> list[TestCaseSpec]:
        """Generate test case specifications.

        Creates specifications for each test case including:
        - Type (positive/negative/evolved/boundary)
        - Target function (for coverage)
        - Difficulty target
        - Boundary type (if applicable)
        """
        specs = []
        spec_id = 0

        # Get functions for coverage
        functions = profile.core_functions or [None]
        function_index = 0

        # Get difficulty levels to assign
        difficulties = self._expand_difficulty_allocation(difficulty_allocation)
        difficulty_index = 0

        # Generate specs by type
        for test_type, count in type_allocation.items():
            for i in range(count):
                # Assign difficulty
                if difficulty_index < len(difficulties):
                    difficulty = difficulties[difficulty_index]
                    difficulty_index += 1
                else:
                    difficulty = DifficultyLevel.MEDIUM

                # Assign target function (cycle through for coverage)
                target_function = None
                if test_type in (TestType.POSITIVE, TestType.EVOLVED):
                    if functions and functions[0] is not None:
                        target_function = functions[function_index % len(functions)].name
                        if i == 0:  # First of each type uses first function
                            function_index += 1
                        else:
                            function_index = (function_index + 1) % len(functions)

                # Assign boundary type
                boundary_type = None
                if test_type == TestType.BOUNDARY:
                    boundary_types = profile.boundary_types or ["completeness"]
                    boundary_type = boundary_types[i % len(boundary_types)]

                # Generate description
                description = self._generate_description(
                    test_type=test_type,
                    target_function=target_function,
                    difficulty=difficulty,
                    boundary_type=boundary_type,
                    index=i,
                )

                specs.append(TestCaseSpec(
                    id=f"test_{spec_id:03d}",
                    test_type=test_type,
                    target_function=target_function,
                    difficulty_target=difficulty,
                    boundary_type=boundary_type,
                    description=description,
                ))
                spec_id += 1

        return specs

    def _expand_difficulty_allocation(
        self, allocation: dict[DifficultyLevel, int]
    ) -> list[DifficultyLevel]:
        """Expand allocation to list of difficulties.

        Returns a shuffled list to distribute difficulties across test types.
        """
        difficulties = []
        for level, count in allocation.items():
            difficulties.extend([level] * count)

        # Sort to interleave: E, M, H, E, M, H, ...
        # This ensures each test type gets a mix of difficulties
        result = []
        by_level = {
            DifficultyLevel.EASY: [],
            DifficultyLevel.MEDIUM: [],
            DifficultyLevel.HARD: [],
        }
        for d in difficulties:
            by_level[d].append(d)

        # Round-robin from each level
        while any(by_level.values()):
            for level in [DifficultyLevel.EASY, DifficultyLevel.MEDIUM, DifficultyLevel.HARD]:
                if by_level[level]:
                    result.append(by_level[level].pop(0))

        return result

    def _generate_description(
        self,
        test_type: TestType,
        target_function: str | None,
        difficulty: DifficultyLevel,
        boundary_type: str | None,
        index: int,
    ) -> str:
        """Generate human-readable description for test case."""
        type_names = {
            TestType.POSITIVE: "正向测试",
            TestType.NEGATIVE: "负向测试",
            TestType.EVOLVED: "演化测试",
            TestType.BOUNDARY: "边界测试",
        }

        difficulty_names = {
            DifficultyLevel.EASY: "简单",
            DifficultyLevel.MEDIUM: "中等",
            DifficultyLevel.HARD: "困难",
        }

        parts = [type_names.get(test_type, "测试")]

        if target_function:
            parts.append(f"功能:{target_function}")

        if boundary_type:
            parts.append(f"边界:{boundary_type}")

        parts.append(f"难度:{difficulty_names.get(difficulty, '中等')}")

        return " - ".join(parts)
