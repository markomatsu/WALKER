from rule_engine import RuleEngine

from function_rules import FunctionRule
from variable_rules import VariableRule
from control_flow_rules import ControlFlowRule
from return_rules import ReturnRule
from missing_return_rule import MissingReturnRule
from unused_variable_rule import UnusedVariableRule
from io_rules import IOStreamRule
from for_loop_rule import ForLoopRule
from while_loop_rule import WhileLoopRule
from do_while_rule import DoWhileRule
from range_for_rule import RangeForRule
from division_by_zero_rule import DivisionByZeroRule
from assignment_in_condition_rule import AssignmentInConditionRule
from constant_condition_rule import ConstantConditionRule
from self_comparison_rule import SelfComparisonRule
from switch_safety_rule import SwitchSafetyRule
from shadowed_variable_rule import ShadowedVariableRule
from unreachable_code_rule import UnreachableCodeRule
from empty_loop_body_rule import EmptyLoopBodyRule
from loop_update_rule import LoopUpdateRule
from contradictory_condition_rule import ContradictoryConditionRule
from duplicate_branch_condition_rule import DuplicateBranchConditionRule
from unused_parameter_rule import UnusedParameterRule
from unused_function_rule import UnusedFunctionRule
from class_field_rules import ClassFieldRule
from function_declared_not_defined_rule import FunctionDeclaredNotDefinedRule
from uninitialized_local_rule import UninitializedLocalRule
from unreachable_elseif_rule import UnreachableElseIfRule


ALL_RULE_GROUPS = {"loops", "conditionals", "functions", "classes", "io", "safety"}


def _normalized_groups(enabled_groups):
    if not enabled_groups:
        return set(ALL_RULE_GROUPS)
    return {g for g in enabled_groups if g in ALL_RULE_GROUPS}


def build_engine(enabled_groups=None):
    groups = _normalized_groups(enabled_groups)
    rules = []

    if "functions" in groups:
        rules.extend(
            [
                FunctionRule(),
                VariableRule(),
                ReturnRule(),
                MissingReturnRule(),
                UnusedVariableRule(),
                UnusedParameterRule(),
                UnusedFunctionRule(),
                FunctionDeclaredNotDefinedRule(),
                UninitializedLocalRule(),
            ]
        )

    if "conditionals" in groups:
        rules.extend(
            [
                ControlFlowRule(),
                AssignmentInConditionRule(),
                ConstantConditionRule(),
                SelfComparisonRule(),
                ContradictoryConditionRule(),
                DuplicateBranchConditionRule(),
                UnreachableElseIfRule(),
            ]
        )

    if "loops" in groups:
        rules.extend(
            [
                ForLoopRule(),
                WhileLoopRule(),
                DoWhileRule(),
                RangeForRule(),
                EmptyLoopBodyRule(),
                LoopUpdateRule(),
            ]
        )

    if "classes" in groups:
        rules.append(ClassFieldRule())

    if "io" in groups:
        rules.append(IOStreamRule())

    if "safety" in groups:
        rules.extend(
            [
                DivisionByZeroRule(),
                SwitchSafetyRule(),
                ShadowedVariableRule(),
                UnreachableCodeRule(),
            ]
        )

    return RuleEngine(rules)
