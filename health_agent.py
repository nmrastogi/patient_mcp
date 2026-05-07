#!/usr/bin/env python3
"""
Claude AI Agent for Diabetes Health Data.
Calls the Anthropic API directly via urllib (no anthropic SDK / no pydantic dependency).
  - chat(question, conversation_history) -> dict
  - generate_insights() -> list[dict]
"""
import os
import json
import logging
import urllib.request
import urllib.error
from datetime import date, timedelta
from typing import Optional

from tools import (
    get_glucose_data,
    get_sleep_data,
    get_exercise_data,
    detect_patterns,
    find_correlations,
)

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 4096
MAX_ITERATIONS = 10
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You are an empathetic diabetes health assistant.
You have access to the user's health data via tools — always fetch data before answering, never guess or fabricate values.
Flag any glucose readings outside the safe range (70-180 mg/dL) explicitly.
Glucose target: 70-180 mg/dL. Sleep goal: 7-9 h/night. Exercise: >=150 min/week.
Today: {today}. All glucose values are in mg/dL."""

TOOL_DEFINITIONS = [
    {
        "name": "get_glucose_data",
        "description": "Retrieve blood glucose readings (timestamped mg/dL values) from the database.",
        "input_schema": {
            "type": "object", "required": [],
            "properties": {
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD (optional)"},
                "end_date":   {"type": "string", "description": "End date YYYY-MM-DD (optional)"},
                "limit":      {"type": "integer", "description": "Max records to return (optional)"},
            },
        },
    },
    {
        "name": "get_sleep_data",
        "description": "Retrieve sleep records including duration, deep/REM/light stages, bedtime, wake time.",
        "input_schema": {
            "type": "object", "required": [],
            "properties": {
                "start_date": {"type": "string"},
                "end_date":   {"type": "string"},
                "limit":      {"type": "integer"},
            },
        },
    },
    {
        "name": "get_exercise_data",
        "description": "Retrieve exercise/workout records with timestamps and durations.",
        "input_schema": {
            "type": "object", "required": [],
            "properties": {
                "start_date": {"type": "string"},
                "end_date":   {"type": "string"},
                "limit":      {"type": "integer"},
            },
        },
    },
    {
        "name": "detect_patterns",
        "description": "Detect hourly/weekly patterns in glucose, sleep, or exercise data.",
        "input_schema": {
            "type": "object", "required": [],
            "properties": {
                "start_date":   {"type": "string"},
                "end_date":     {"type": "string"},
                "pattern_type": {"type": "string",
                                 "enum": ["all", "glucose", "sleep", "exercise", "temporal"]},
            },
        },
    },
    {
        "name": "find_correlations",
        "description": "Find correlations between metrics: exercise<->glucose, sleep<->glucose, sleep<->exercise.",
        "input_schema": {
            "type": "object", "required": [],
            "properties": {
                "start_date":       {"type": "string"},
                "end_date":         {"type": "string"},
                "correlation_type": {"type": "string",
                                     "enum": ["all", "exercise_glucose", "sleep_glucose", "sleep_exercise"]},
            },
        },
    },
]

TOOL_REGISTRY = {
    "get_glucose_data":  get_glucose_data,
    "get_sleep_data":    get_sleep_data,
    "get_exercise_data": get_exercise_data,
    "detect_patterns":   detect_patterns,
    "find_correlations": find_correlations,
}


def _call_claude(messages: list, system: str) -> dict:
    """Call the Anthropic API directly via urllib — no SDK, no pydantic."""
    api_key = os.environ["ANTHROPIC_API_KEY"]
    payload = json.dumps({
        "model":      MODEL,
        "max_tokens": MAX_TOKENS,
        "system":     system,
        "tools":      TOOL_DEFINITIONS,
        "messages":   messages,
    }).encode("utf-8")

    req = urllib.request.Request(ANTHROPIC_API_URL, data=payload, method="POST")
    req.add_header("x-api-key",          api_key)
    req.add_header("anthropic-version",  "2023-06-01")
    req.add_header("content-type",       "application/json")

    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _execute_tool(name: str, tool_input: dict) -> str:
    func = TOOL_REGISTRY.get(name)
    if not func:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        return json.dumps(func(**tool_input), default=str)
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


def _run_agent_loop(messages: list, system: str):
    """Agentic loop: call Claude → execute tools → repeat until end_turn."""
    tools_used: list[str] = []

    for _ in range(MAX_ITERATIONS):
        response = _call_claude(messages, system)

        stop_reason = response.get("stop_reason", "end_turn")
        content     = response.get("content", [])

        text_blocks = [b["text"] for b in content if b.get("type") == "text"]
        tool_blocks = [b for b in content if b.get("type") == "tool_use"]

        if stop_reason == "end_turn" or not tool_blocks:
            return "\n".join(text_blocks), tools_used

        # Append Claude's assistant turn
        messages.append({"role": "assistant", "content": content})

        # Execute tools and collect results
        tool_results = []
        for tb in tool_blocks:
            name = tb.get("name", "")
            tools_used.append(name)
            logger.info(f"Executing tool: {name}")
            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": tb.get("id", ""),
                "content":     _execute_tool(name, tb.get("input", {})),
            })

        messages.append({"role": "user", "content": tool_results})

    return "Reached processing limit. Please try a more specific question.", tools_used


def chat(question: str, conversation_history: Optional[list] = None) -> dict:
    system   = SYSTEM_PROMPT.format(today=date.today().isoformat())
    messages = list(conversation_history or []) + [{"role": "user", "content": question}]
    try:
        answer, tools = _run_agent_loop(messages, system)
        return {
            "answer":     answer,
            "tools_used": list(dict.fromkeys(tools)),
            "status":     "success",
        }
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return {"answer": "An error occurred. Please try again.", "tools_used": [], "status": "error"}


def generate_insights() -> list:
    today      = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    system     = SYSTEM_PROMPT.format(today=today.isoformat())

    prompts = {
        "glucose":  f"Generate a 2-4 sentence weekly glucose insight for the week of {week_start}. Fetch data, compute average and time-in-range %, note highs/lows.",
        "sleep":    f"Generate a 2-4 sentence weekly sleep insight for the week of {week_start}. Fetch data, avg duration vs 7-9h goal, best/worst nights.",
        "exercise": f"Generate a 2-4 sentence weekly exercise insight for the week of {week_start}. Fetch data, total minutes vs 150 min/week goal, frequency.",
        "combined": f"Generate a 2-4 sentence combined health insight for the week of {week_start}. Find correlations, give the single most actionable recommendation.",
    }

    insights = []
    for insight_type, prompt in prompts.items():
        try:
            content, _ = _run_agent_loop([{"role": "user", "content": prompt}], system)
            insights.append({
                "insight_type": insight_type,
                "week_start":   week_start,
                "content":      content.strip(),
            })
        except Exception as e:
            logger.error(f"Failed to generate {insight_type} insight: {e}")

    return insights