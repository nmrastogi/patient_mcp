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
from datetime import date, datetime, timedelta
from statistics import mean
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
Today: {today}. All glucose values are in mg/dL.
TIMEZONE: All timestamps stored in the database are in UTC. The user lives in US/Pacific time (PDT = UTC-7, Mar–Nov; PST = UTC-8, Nov–Mar). Always convert and display times in Pacific time when presenting results.
Be concise — 2-4 sentences max per response. Lead with the key number or finding."""


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
    two_weeks_ago = (today - timedelta(days=14)).isoformat()
    system     = SYSTEM_PROMPT.format(today=today.isoformat())

    INSIGHT_PROMPTS = {
        "glucose": (
            f"Use tools to fetch glucose readings since {week_start}. "
            "Then write a 2-4 sentence glucose insight covering average mg/dL, "
            "time-in-range %, and any concerning highs or lows."
        ),
        "sleep": (
            f"Use tools to fetch sleep data since {two_weeks_ago}. "
            "Then write a 2-4 sentence sleep insight comparing average hours to the 7-9h goal "
            "and highlighting the best and worst nights."
        ),
        "exercise": (
            f"Use tools to fetch exercise data since {two_weeks_ago}. "
            "Then write a 2-4 sentence exercise insight comparing total minutes to the 150 min/week goal "
            "and commenting on session frequency."
        ),
        "combined": (
            f"Use tools to fetch glucose, sleep, and exercise data since {two_weeks_ago}. "
            "Then write a 2-4 sentence combined health insight with one specific actionable recommendation."
        ),
    }

    insights = []
    for insight_type, prompt in INSIGHT_PROMPTS.items():
        try:
            answer, _ = _run_agent_loop(
                [{"role": "user", "content": prompt}], system
            )
            if answer:
                insights.append({
                    "insight_type": insight_type,
                    "week_start":   week_start,
                    "content":      answer,
                })
                logger.info(f"✅ Generated {insight_type} insight")
        except Exception as err:
            logger.error(f"Failed to generate {insight_type} insight: {err}", exc_info=True)

    return insights


def _fetch_summaries(today: date) -> dict:
    """Fetch and aggregate health data directly from DB — no Claude tool calls needed."""
    from db_config import db_config
    from models import BloodGlucose, SleepData, ExerciseData

    week_start_dt  = today - timedelta(days=today.weekday())
    two_weeks_ago  = today - timedelta(days=14)

    session = db_config.get_session()
    try:
        # Glucose: current week
        g_recs = session.query(BloodGlucose).filter(
            BloodGlucose.timestamp >= datetime.combine(week_start_dt, datetime.min.time())
        ).all()
        g_vals = [float(r.value) for r in g_recs if r.value]
        glucose = {
            "period": f"{week_start_dt} to {today}",
            "readings": len(g_vals),
            "avg_mg_dl": round(mean(g_vals), 1) if g_vals else None,
            "time_in_range_pct": round(
                sum(1 for v in g_vals if 70 <= v <= 180) / len(g_vals) * 100, 1
            ) if g_vals else None,
            "min_mg_dl": round(min(g_vals), 1) if g_vals else None,
            "max_mg_dl": round(max(g_vals), 1) if g_vals else None,
        }

        # Sleep: past 2 weeks
        s_recs = session.query(SleepData).filter(
            SleepData.date >= two_weeks_ago
        ).order_by(SleepData.date.asc()).all()
        s_mins = [r.sleep_duration_minutes for r in s_recs if r.sleep_duration_minutes]
        sleep = {
            "period": f"{two_weeks_ago} to {today}",
            "nights_recorded": len(s_mins),
            "avg_hours": round(mean(s_mins) / 60.0, 1) if s_mins else None,
            "goal_hours": 7.5,
            "nightly": [
                {"date": str(r.date), "hours": round(r.sleep_duration_minutes / 60.0, 1)}
                for r in s_recs if r.sleep_duration_minutes
            ],
        }

        # Exercise: past 2 weeks, sessions > 10 min only
        e_recs = session.query(ExerciseData).filter(
            ExerciseData.timestamp >= datetime.combine(two_weeks_ago, datetime.min.time()),
            ExerciseData.duration_minutes > 10,
        ).order_by(ExerciseData.timestamp.asc()).all()
        e_mins = [r.duration_minutes for r in e_recs if r.duration_minutes]
        exercise = {
            "period": f"{two_weeks_ago} to {today}",
            "sessions": len(e_mins),
            "total_minutes": sum(e_mins),
            "avg_minutes_per_session": round(mean(e_mins), 1) if e_mins else None,
            "goal_minutes_per_week": 150,
        }

        return {"glucose": glucose, "sleep": sleep, "exercise": exercise}
    finally:
        session.close()


