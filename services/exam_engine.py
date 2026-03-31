"""Exam engine: question loading, selection, and grading."""

import os
import json
import random
import re
from typing import Any, Optional, List, Dict, Tuple

import yaml

from services.claude_client import call_claude

QUESTIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "questions")

TRACK_FILES = {
    "quant_developer": "quant_developer.yaml",
    "quant_researcher": "quant_researcher.yaml",
    "trading": "trading.yaml",
    "portfolio_manager": "portfolio_manager.yaml",
}

SHARED_FILES = ["iq_brainteasers.yaml", "math_competition.yaml"]
PSYCH_FILES = ["psychology_test.yaml", "character_test.yaml"]

TRACK_LABELS = {
    "quant_developer": "量化开发能力 (Quant Developer)",
    "quant_researcher": "量化研究能力 (Quant Researcher)",
    "trading": "交易能力 (Trading)",
    "portfolio_manager": "投资组合经理 (Portfolio Manager)",
}

TRACK_DESCRIPTIONS = {
    "quant_developer": "考察算法与数据结构、系统设计、Python/C++编程、并发与性能优化、数据管道、因子挖掘领域代码能力。",
    "quant_researcher": "考察概率统计、随机微积分、因子建模、机器学习/深度学习、时间序列分析、研究设计能力。",
    "trading": "考察市场微观结构、风险管理、心算与估算、做市与博弈论、行为决策、组合盈亏分析能力。",
    "portfolio_manager": "考察组合构建、风险归因、Alpha生成与因子投资、宏观分析、团队管理、合规监管能力。",
}


def load_questions(filename: str) -> List[dict]:
    """Load questions from a YAML file."""
    filepath = os.path.join(QUESTIONS_DIR, filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        return []
    return [q for q in data if q is not None and isinstance(q, dict)]


def load_track_questions(track: str) -> List[dict]:
    """Load all questions for a specific track."""
    filename = TRACK_FILES.get(track)
    if not filename:
        return []
    return load_questions(filename)


def load_shared_questions() -> List[dict]:
    """Load IQ brainteasers and math competition questions."""
    questions = []
    for filename in SHARED_FILES:
        questions.extend(load_questions(filename))
    return questions


def load_psychology_questions() -> List[dict]:
    """Load psychology and character test questions."""
    questions = []
    for filename in PSYCH_FILES:
        questions.extend(load_questions(filename))
    return questions


def select_exam_questions(
    track: str,
    num_track: int = 30,
    num_iq_math: int = 3,
    num_psych: int = 10,
    num_character: int = 10,
    seed: Optional[int] = None,
) -> List[dict]:
    """Select questions for an exam sitting.

    Default exam format: 30 professional + 3 IQ/math + 10 psychology + 10 character = 53 questions
    (Psychology = 心理素质, Character = 职业素养)
    """
    if seed is not None:
        random.seed(seed)

    track_qs = load_track_questions(track)
    shared_qs = load_shared_questions()
    psych_qs = load_psychology_questions()

    # ── Professional questions (stratified by difficulty) ──
    by_diff = {"medium_high": [], "senior": [], "expert": []}
    for q in track_qs:
        diff = q.get("difficulty", "medium_high")
        if diff in by_diff:
            by_diff[diff].append(q)

    selected_track = []
    target = {
        "medium_high": int(num_track * 0.4),
        "senior": int(num_track * 0.4),
        "expert": num_track - int(num_track * 0.4) - int(num_track * 0.4),
    }

    for diff, count in target.items():
        pool = by_diff.get(diff, [])
        selected_track.extend(random.sample(pool, min(count, len(pool))))

    selected_ids = {q["id"] for q in selected_track}
    remaining = [q for q in track_qs if q["id"] not in selected_ids]
    shortfall = num_track - len(selected_track)
    if shortfall > 0 and remaining:
        selected_track.extend(random.sample(remaining, min(shortfall, len(remaining))))

    difficulty_order = {"medium_high": 0, "senior": 1, "expert": 2}
    selected_track.sort(key=lambda q: difficulty_order.get(q.get("difficulty", "medium_high"), 0))

    # ── IQ + Math (combined pool, select num_iq_math) ──
    selected_shared = random.sample(shared_qs, min(num_iq_math, len(shared_qs))) if shared_qs else []

    # ── Psychology questions ──
    psych_only = [q for q in psych_qs if "PSY" in q.get("id", "")]
    char_only = [q for q in psych_qs if "CHR" in q.get("id", "")]

    selected_psych = random.sample(psych_only, min(num_psych, len(psych_only))) if psych_only else []
    selected_char = random.sample(char_only, min(num_character, len(char_only))) if char_only else []

    return selected_track + selected_shared + selected_psych + selected_char


def grade_multiple_choice(question: dict, response: str) -> tuple[bool, float, str]:
    """Grade a multiple choice question. Returns (is_correct, score, notes)."""
    correct = str(question.get("answer", "")).strip().upper()
    given = response.strip().upper()

    # Extract just the letter if response contains more
    letter_match = re.match(r"^([A-D])", given)
    if letter_match:
        given = letter_match.group(1)

    is_correct = given == correct
    score = question.get("points", 1.0) if is_correct else 0.0
    explanation = question.get("explanation", "")
    notes = f"正确答案: {correct}" + (f"\n解析: {explanation}" if explanation else "")

    return is_correct, score, notes


GRADE_OPEN_ENDED_PROMPT = """你是量化金融面试评分专家。请根据评分标准对候选人的回答进行评分。

评分要求：
1. 满分为该题的最高分值
2. 返回纯JSON格式（不要markdown代码块）：
{
  "score": 7.5,
  "max_score": 10,
  "feedback": "评分理由和改进建议",
  "key_points_hit": ["命中的要点1", "要点2"],
  "key_points_missed": ["遗漏的要点1"]
}
"""


def grade_open_ended(question: dict, response: str) -> tuple[bool, float, str]:
    """Grade an open-ended question using Claude. Returns (is_correct, score, notes)."""
    max_score = question.get("points", 10.0)
    rubric = question.get("rubric", "")

    user_msg = f"""题目: {question['question']}

评分标准: {rubric}

满分: {max_score}

候选人回答:
{response}

请评分。"""

    try:
        result = call_claude(GRADE_OPEN_ENDED_PROMPT, user_msg)
        json_match = re.search(r"\{[\s\S]*\}", result)
        if json_match:
            data = json.loads(json_match.group())
            score = min(float(data.get("score", 0)), max_score)
            is_correct = score >= max_score * 0.6
            notes = data.get("feedback", "")
            return is_correct, score, notes
    except Exception as e:
        pass

    return False, 0, "评分失败，请人工复核"


def grade_question(question: dict, response: str) -> tuple[bool, float, str]:
    """Grade a question based on its type."""
    q_type = question.get("type", "multiple_choice")

    if q_type == "multiple_choice":
        return grade_multiple_choice(question, response)
    else:
        return grade_open_ended(question, response)
