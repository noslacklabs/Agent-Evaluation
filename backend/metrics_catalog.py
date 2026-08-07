from __future__ import annotations

from typing import Any


def metric(
    metric_id: str,
    name: str,
    category: str,
    description: str,
    required: list[str],
    *,
    availability: str = "ready",
    availability_note: str | None = None,
    reference_based: bool = False,
) -> dict[str, Any]:
    return {
        "id": metric_id,
        "name": name,
        "category": category,
        "description": description,
        "required_fields": required,
        "availability": availability,
        "availability_note": availability_note,
        "reference_based": reference_based,
    }


METRICS = [
    metric("g_eval", "G-Eval", "Custom", "Judge output against your own natural-language criteria.", ["input", "actual_output"]),
    metric("dag", "DAG", "Custom", "Custom decision-graph evaluation.", ["input"], availability="advanced", availability_note="Requires a configured DeepEval DAG definition."),
    metric("conversational_g_eval", "Conversational G-Eval", "Custom", "Custom criteria over a complete conversation.", ["turns"]),
    metric("conversational_dag", "Conversational DAG", "Custom", "Decision-graph evaluation for conversations.", ["turns"], availability="advanced", availability_note="Requires a configured conversational DAG definition."),
    metric("arena_g_eval", "Arena G-Eval", "Custom", "Compare two candidate agents head-to-head.", ["actual_output", "candidate_output"], availability="advanced", availability_note="Requires a second comparison agent."),
    metric("custom", "Do it yourself", "Custom", "Plug in a project-specific DeepEval metric.", ["input"], availability="extension", availability_note="Implement a custom metric factory before selecting this option."),

    metric("task_completion", "Task Completion", "Agentic", "Determine whether the full agent run accomplished its task.", ["trace"], availability="trace_only", availability_note="DeepEval 4 evaluates this metric from an instrumented trace."),
    metric("step_efficiency", "Step Efficiency", "Agentic", "Measure unnecessary or inefficient agent steps.", ["trace"], availability="trace_only", availability_note="Requires DeepEval tracing or a framework integration."),
    metric("argument_correctness", "Argument Correctness", "Agentic", "Judge whether tool arguments fit the task.", ["input", "actual_output", "tools_called"]),
    metric("tool_correctness", "Tool Correctness", "Agentic", "Compare actual tool calls with expected tool calls.", ["input", "actual_output", "tools_called", "expected_tools"], reference_based=True),
    metric("plan_adherence", "Plan Adherence", "Agentic", "Judge whether execution followed the agent plan.", ["trace"], availability="trace_only", availability_note="Requires plan and execution spans in a DeepEval trace."),
    metric("plan_quality", "Plan Quality", "Agentic", "Judge the quality of the plan extracted from the trace.", ["trace"], availability="trace_only", availability_note="Requires reasoning or plan data in a DeepEval trace."),

    metric("answer_relevancy", "Answer Relevancy", "RAG — DeepEval", "Measure how directly the answer addresses the question.", ["input", "actual_output"]),
    metric("faithfulness", "Faithfulness", "RAG — DeepEval", "Measure whether answer claims are grounded in retrieved context.", ["input", "actual_output", "retrieval_context"]),
    metric("contextual_precision", "Contextual Precision", "RAG — DeepEval", "Measure whether relevant chunks are ranked ahead of irrelevant chunks.", ["input", "actual_output", "expected_output", "retrieval_context"], reference_based=True),
    metric("contextual_recall", "Contextual Recall", "RAG — DeepEval", "Measure whether retrieved context contains the facts needed for the expected answer.", ["input", "actual_output", "expected_output", "retrieval_context"], reference_based=True),
    metric("contextual_relevancy", "Contextual Relevancy", "RAG — DeepEval", "Measure how much retrieved context is relevant to the question.", ["input", "actual_output", "retrieval_context"]),

    metric("turn_relevancy", "Turn Relevancy", "Multi-Turn", "Measure response relevance throughout a conversation.", ["turns"]),
    metric("role_adherence", "Role Adherence", "Multi-Turn", "Measure whether the assistant maintains its assigned role.", ["turns", "chatbot_role"]),
    metric("knowledge_retention", "Knowledge Retention", "Multi-Turn", "Measure whether earlier user facts are retained.", ["turns"]),
    metric("conversation_completeness", "Conversation Completeness", "Multi-Turn", "Measure whether the conversation satisfies the user's intentions.", ["turns"]),
    metric("goal_accuracy", "Goal Accuracy", "Multi-Turn", "Measure whether the assistant identifies the correct user goal.", ["turns"]),
    metric("tool_use", "Tool Use", "Multi-Turn", "Measure tool selection and arguments across turns.", ["turns", "available_tools"]),
    metric("topic_adherence", "Topic Adherence", "Multi-Turn", "Measure whether the conversation stays within allowed topics.", ["turns"]),
    metric("turn_faithfulness", "Turn Faithfulness", "Multi-Turn", "Measure grounding for each conversational answer.", ["turns"]),
    metric("turn_contextual_precision", "Turn Contextual Precision", "Multi-Turn", "Measure retrieval precision across turns.", ["turns"]),
    metric("turn_contextual_recall", "Turn Contextual Recall", "Multi-Turn", "Measure retrieval recall across turns.", ["turns"]),
    metric("turn_contextual_relevancy", "Turn Contextual Relevancy", "Multi-Turn", "Measure retrieval relevancy across turns.", ["turns"]),

    metric("mcp_use", "MCP-Use", "MCP", "Judge MCP primitive selection and arguments for one interaction.", ["mcp_servers", "mcp_calls"], availability="telemetry_required", availability_note="The agent response mapping must return typed MCP server and primitive telemetry."),
    metric("multi_turn_mcp_use", "Multi-Turn MCP-Use", "MCP", "Judge MCP usage over a complete conversation.", ["turns", "mcp_servers"], availability="telemetry_required", availability_note="Requires per-turn MCP primitive telemetry."),
    metric("mcp_task_completion", "MCP Task Completion", "MCP", "Measure task completion for MCP interactions.", ["turns", "mcp_servers"], availability="telemetry_required", availability_note="Requires per-turn MCP primitive telemetry."),
]

METRIC_BY_ID = {item["id"]: item for item in METRICS}


def list_metrics() -> list[dict[str, Any]]:
    return METRICS
