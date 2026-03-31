"""Resume scoring engine with role-specific weight profiles."""

from typing import Any, Dict

# ── Role-specific weight profiles ──

ROLE_WEIGHTS = {
    "quant_developer": {
        "education": 0.20,
        "competitions": 0.15,
        "skills": 0.30,
        "experience": 0.25,
        "research": 0.10,
    },
    "quant_researcher": {
        "education": 0.25,
        "competitions": 0.20,
        "skills": 0.15,
        "experience": 0.20,
        "research": 0.20,
    },
    "trader": {
        "education": 0.20,
        "competitions": 0.25,
        "skills": 0.15,
        "experience": 0.25,
        "research": 0.15,
    },
    "portfolio_manager": {
        "education": 0.20,
        "competitions": 0.10,
        "skills": 0.15,
        "experience": 0.35,
        "research": 0.20,
    },
}

ROLE_LABELS = {
    "quant_developer": "量化开发 (Quant Developer)",
    "quant_researcher": "量化研究 (Quant Researcher)",
    "trader": "交易员 (Trader)",
    "portfolio_manager": "投资组合经理 (Portfolio Manager)",
}

# ── School tier classification ──

TIER1_SCHOOLS = {
    "mit", "stanford", "harvard", "caltech", "princeton", "cmu", "carnegie mellon",
    "berkeley", "uc berkeley", "oxford", "cambridge", "eth zurich",
    "清华", "北大", "清华大学", "北京大学", "tsinghua", "peking",
    "中科大", "中国科学技术大学", "ustc",
    "复旦", "复旦大学", "fudan",
    "上交", "上海交通大学", "sjtu", "shanghai jiao tong",
}

TIER2_SCHOOLS = {
    "columbia", "yale", "upenn", "penn", "chicago", "uchicago",
    "nyu", "cornell", "duke", "northwestern", "michigan", "georgia tech",
    "ucl", "imperial", "epfl", "ntu", "nus",
    "浙大", "浙江大学", "zhejiang",
    "南大", "南京大学", "nanjing",
    "人大", "中国人民大学", "renmin",
    "武大", "武汉大学", "wuhan",
    "中山", "中山大学", "sysu",
    "哈工大", "哈尔滨工业大学", "hit",
}

# ── Scoring functions ──

def score_education(parsed: Dict[str, Any]) -> float:
    """Score education (0-100)."""
    score = 0.0
    edu = parsed.get("education", [])
    if not edu:
        return 0.0

    best_school = edu[0] if edu else {}
    school_name = best_school.get("school", "").lower()
    degree = best_school.get("degree", "").lower()
    gpa = best_school.get("gpa", 0)

    # School tier (0-40)
    if any(t in school_name for t in TIER1_SCHOOLS):
        score += 40
    elif any(t in school_name for t in TIER2_SCHOOLS):
        score += 30
    else:
        score += 15

    # Degree level (0-30)
    if "phd" in degree or "博士" in degree:
        score += 30
    elif "master" in degree or "硕士" in degree:
        score += 22
    elif "bachelor" in degree or "学士" in degree or "本科" in degree:
        score += 15

    # GPA (0-30)
    if gpa > 0:
        if gpa <= 4.0:
            score += min(30, gpa / 4.0 * 30)
        elif gpa <= 100:
            score += min(30, gpa / 100 * 30)

    return min(100, score)


def score_competitions(parsed: Dict[str, Any]) -> float:
    """Score competition achievements (0-100)."""
    comps = parsed.get("competitions", [])
    if not comps:
        return 0.0

    score = 0.0
    prestige_map = {
        "imo": 50, "国际数学奥林匹克": 50,
        "putnam": 40, "usamo": 40,
        "icpc": 35, "acm": 35,
        "kaggle": 30,
        "aime": 25,
        "cmo": 25, "全国数学竞赛": 20,
        "mathematic": 15, "programming": 15,
    }

    for comp in comps:
        name = comp.get("name", "").lower()
        for key, pts in prestige_map.items():
            if key in name:
                rank = comp.get("rank", "").lower()
                multiplier = 1.0
                if any(w in rank for w in ["gold", "1st", "一等", "金"]):
                    multiplier = 1.0
                elif any(w in rank for w in ["silver", "2nd", "二等", "银"]):
                    multiplier = 0.8
                elif any(w in rank for w in ["bronze", "3rd", "三等", "铜"]):
                    multiplier = 0.6
                score += pts * multiplier
                break

    return min(100, score)


def score_skills(parsed: Dict[str, Any], role: str) -> float:
    """Score technical skills (0-100) with role-specific weighting."""
    skills = parsed.get("skills", [])
    if not skills:
        return 0.0

    skill_set = {s.lower() for s in skills}

    role_priority_skills = {
        "quant_developer": [
            ("python", 15), ("c++", 15), ("c", 10),
            ("pytorch", 10), ("tensorflow", 8),
            ("sql", 8), ("dolphindb", 10),
            ("docker", 5), ("kubernetes", 5), ("airflow", 8),
            ("git", 3), ("linux", 5),
            ("rust", 8), ("go", 5), ("java", 5),
        ],
        "quant_researcher": [
            ("python", 15), ("r", 10), ("matlab", 8),
            ("pytorch", 12), ("tensorflow", 10),
            ("statistics", 10), ("machine learning", 12),
            ("deep learning", 10), ("pandas", 8),
            ("sql", 5), ("latex", 3),
        ],
        "trader": [
            ("python", 12), ("excel", 8),
            ("bloomberg", 10), ("wind", 8),
            ("sql", 5), ("vba", 5),
            ("risk management", 10), ("derivatives", 10),
            ("options", 8), ("futures", 8),
        ],
        "portfolio_manager": [
            ("python", 10), ("r", 8), ("excel", 5),
            ("bloomberg", 10), ("wind", 8),
            ("portfolio optimization", 12), ("risk management", 12),
            ("factor investing", 12), ("barra", 10),
            ("sql", 5),
        ],
    }

    score = 0.0
    for skill_name, points in role_priority_skills.get(role, []):
        if skill_name in skill_set:
            score += points

    return min(100, score)


def score_experience(parsed: Dict[str, Any]) -> float:
    """Score work experience (0-100)."""
    exp = parsed.get("experience", [])
    if not exp:
        return 0.0

    score = 0.0
    quant_keywords = ["quant", "量化", "hedge fund", "对冲", "trading", "交易",
                      "factor", "因子", "alpha", "systematic"]

    for job in exp:
        title = (job.get("title", "") + " " + job.get("company", "")).lower()
        years = job.get("years", 0)

        if any(k in title for k in quant_keywords):
            score += min(25, years * 10 + 15)
        elif any(k in title for k in ["data scientist", "machine learning", "ml engineer", "研究员"]):
            score += min(20, years * 8 + 10)
        elif any(k in title for k in ["software", "developer", "engineer", "开发"]):
            score += min(15, years * 6 + 8)
        else:
            score += min(8, years * 3 + 3)

    return min(100, score)


def score_research(parsed: Dict[str, Any]) -> float:
    """Score research & publications (0-100)."""
    pubs = parsed.get("publications", [])
    if not pubs:
        return 0.0

    score = 0.0
    top_venues = {"nature", "science", "nips", "neurips", "icml", "aaai", "kdd",
                  "jfe", "rfs", "journal of finance", "jof"}

    for pub in pubs:
        venue = pub.get("venue", "").lower()
        if any(v in venue for v in top_venues):
            score += 20
        elif pub.get("is_journal", False):
            score += 12
        else:
            score += 6

    return min(100, score)


def calculate_scores(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate scores for all roles."""
    dimension_scores = {
        "education": score_education(parsed),
        "competitions": score_competitions(parsed),
        "experience": score_experience(parsed),
        "research": score_research(parsed),
    }

    role_scores = {}
    for role, weights in ROLE_WEIGHTS.items():
        skill_score = score_skills(parsed, role)
        dims = {**dimension_scores, "skills": skill_score}
        total = sum(dims[dim] * w for dim, w in weights.items())
        role_scores[role] = {
            "total": round(total, 1),
            "dimensions": {k: round(v, 1) for k, v in dims.items()},
            "label": ROLE_LABELS[role],
        }

    return role_scores
