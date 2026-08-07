from __future__ import annotations

from typing import Any

from config import DEEPEVAL_JUDGE_MODEL


def _tool_call(raw: dict[str, Any], ToolCall):
    return ToolCall(
        name=str(raw.get("name") or raw.get("tool_name") or "unknown_tool"),
        description=raw.get("description"),
        input_parameters=raw.get("input_parameters") or raw.get("input") or raw.get("arguments"),
        output=raw.get("output") or raw.get("result"),
        reasoning=raw.get("reasoning"),
    )


def build_test_cases(case: dict[str, Any], response: Any):
    try:
        from deepeval.test_case import ConversationalTestCase, LLMTestCase, ToolCall, Turn
    except ImportError as exc:
        raise RuntimeError("DeepEval is not installed. Run pip install -r requirements.txt") from exc

    actual_tools = [_tool_call(item, ToolCall) for item in (response.tools_called or case.get("tools_called") or [])]
    expected_tools = [_tool_call(item, ToolCall) for item in (case.get("expected_tools") or [])]
    available_tools = [_tool_call(item, ToolCall) for item in (case.get("available_tools") or [])]
    retrieval_context = response.retrieval_context or case.get("retrieval_context") or []
    single = LLMTestCase(
        input=case["input"],
        actual_output=response.output,
        expected_output=case.get("expected_output"),
        context=case.get("context") or None,
        retrieval_context=retrieval_context or None,
        tools_called=actual_tools or None,
        expected_tools=expected_tools or None,
        metadata=case.get("metadata") or {},
    )

    turns = list(case.get("turns") or [])
    if not turns or turns[-1].get("role") != "user" or turns[-1].get("content") != case["input"]:
        turns.append({"role": "user", "content": case["input"]})
    assistant_turn: dict[str, Any] = {"role": "assistant", "content": response.output}
    if actual_tools:
        assistant_turn["tools_called"] = actual_tools
    if retrieval_context:
        assistant_turn["retrieval_context"] = retrieval_context
    turns.append(assistant_turn)
    conversation = ConversationalTestCase(
        turns=[turn if isinstance(turn, Turn) else Turn.model_validate(turn) for turn in turns],
        scenario=case.get("scenario"),
        expected_outcome=case.get("expected_outcome") or case.get("expected_output"),
        chatbot_role=case.get("chatbot_role"),
        context=case.get("context") or None,
        user_description=case.get("user_description"),
        metadata=case.get("metadata") or {},
    )
    return single, conversation, available_tools


def _common_kwargs(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "threshold": float(config.get("threshold", 0.5)),
        "model": config.get("judge_model") or DEEPEVAL_JUDGE_MODEL,
        "include_reason": True,
        "strict_mode": bool(config.get("strict_mode", False)),
        "async_mode": True,
        "verbose_mode": False,
    }


def build_metric(metric_id: str, config: dict[str, Any], available_tools: list[Any]):
    try:
        import deepeval.metrics as metrics
        from deepeval.test_case import MultiTurnParams, SingleTurnParams
    except ImportError as exc:
        raise RuntimeError("DeepEval is not installed. Run pip install -r requirements.txt") from exc

    kwargs = _common_kwargs(config)
    simple = {
        "answer_relevancy": "AnswerRelevancyMetric",
        "faithfulness": "FaithfulnessMetric",
        "contextual_precision": "ContextualPrecisionMetric",
        "contextual_recall": "ContextualRecallMetric",
        "contextual_relevancy": "ContextualRelevancyMetric",
        "argument_correctness": "ArgumentCorrectnessMetric",
        "tool_correctness": "ToolCorrectnessMetric",
        "turn_relevancy": "TurnRelevancyMetric",
        "role_adherence": "RoleAdherenceMetric",
        "knowledge_retention": "KnowledgeRetentionMetric",
        "conversation_completeness": "ConversationCompletenessMetric",
        "goal_accuracy": "GoalAccuracyMetric",
        "turn_faithfulness": "TurnFaithfulnessMetric",
        "turn_contextual_precision": "TurnContextualPrecisionMetric",
        "turn_contextual_recall": "TurnContextualRecallMetric",
        "turn_contextual_relevancy": "TurnContextualRelevancyMetric",
    }
    if metric_id in simple:
        return getattr(metrics, simple[metric_id])(**kwargs)
    if metric_id == "g_eval":
        criteria = config.get("criteria") or "Evaluate whether the actual output is correct, complete, clear, and aligned with the expected output when one is provided."
        params = [SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT]
        if config.get("use_expected_output", True):
            params.append(SingleTurnParams.EXPECTED_OUTPUT)
        g_eval_kwargs = {key: value for key, value in kwargs.items() if key != "include_reason"}
        return metrics.GEval(name=config.get("name", "Custom quality"), criteria=criteria, evaluation_params=params, **g_eval_kwargs)
    if metric_id == "conversational_g_eval":
        criteria = config.get("criteria") or "Evaluate whether the assistant is helpful, coherent, and correct throughout the conversation."
        g_eval_kwargs = {key: value for key, value in kwargs.items() if key != "include_reason"}
        return metrics.ConversationalGEval(
            name=config.get("name", "Conversation quality"),
            criteria=criteria,
            evaluation_params=[MultiTurnParams.ROLE, MultiTurnParams.CONTENT],
            **g_eval_kwargs,
        )
    if metric_id == "tool_use":
        if not available_tools:
            raise ValueError("Tool Use requires available_tools in the dataset")
        return metrics.ToolUseMetric(available_tools=available_tools, **kwargs)
    if metric_id == "topic_adherence":
        topics = config.get("allowed_topics")
        if not topics:
            raise ValueError("Topic Adherence requires allowed_topics in metric configuration")
        return metrics.TopicAdherenceMetric(relevant_topics=topics, **kwargs)
    raise ValueError(f"Metric '{metric_id}' is not supported by the black-box runner")


CONVERSATIONAL_IDS = {
    "conversational_g_eval",
    "turn_relevancy",
    "role_adherence",
    "knowledge_retention",
    "conversation_completeness",
    "goal_accuracy",
    "tool_use",
    "topic_adherence",
    "turn_faithfulness",
    "turn_contextual_precision",
    "turn_contextual_recall",
    "turn_contextual_relevancy",
}


async def measure(metric_id: str, config: dict[str, Any], single_case: Any, conversation_case: Any, available_tools: list[Any]) -> dict[str, Any]:
    metric = build_metric(metric_id, config, available_tools)
    test_case = conversation_case if metric_id in CONVERSATIONAL_IDS else single_case
    score = await metric.a_measure(test_case, _show_indicator=False)
    return {
        "score": float(score) if score is not None else None,
        "passed": bool(metric.is_successful()) if score is not None else None,
        "reason": getattr(metric, "reason", None),
        "evaluation_model": getattr(metric, "evaluation_model", None),
        "evaluation_cost": getattr(metric, "evaluation_cost", None),
    }
