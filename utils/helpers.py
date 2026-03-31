"""Shared utility functions."""

import io
import pandas as pd


def format_score(score: float, max_score: float = 100) -> str:
    """Format score with color indicator."""
    pct = score / max_score * 100 if max_score > 0 else 0
    if pct >= 80:
        return f"🟢 {score:.1f}/{max_score:.0f} ({pct:.0f}%)"
    elif pct >= 60:
        return f"🟡 {score:.1f}/{max_score:.0f} ({pct:.0f}%)"
    else:
        return f"🔴 {score:.1f}/{max_score:.0f} ({pct:.0f}%)"


def seconds_to_hms(seconds: int) -> str:
    """Convert seconds to HH:MM:SS format."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def candidates_to_dataframe(candidates: list) -> pd.DataFrame:
    """Convert candidate list to pandas DataFrame for display."""
    import json
    rows = []
    for c in candidates:
        scores = json.loads(c.get("scores", "{}")) if isinstance(c.get("scores"), str) else c.get("scores", {})
        parsed = json.loads(c.get("parsed_data", "{}")) if isinstance(c.get("parsed_data"), str) else c.get("parsed_data", {})
        row = {
            "ID": c["id"],
            "姓名": parsed.get("name", c.get("name", "N/A")),
            "邮箱": parsed.get("email", c.get("email", "")),
            "简历文件": c.get("resume_filename", ""),
            "量化开发": scores.get("quant_developer", {}).get("total", 0),
            "量化研究": scores.get("quant_researcher", {}).get("total", 0),
            "交易员": scores.get("trader", {}).get("total", 0),
            "组合经理": scores.get("portfolio_manager", {}).get("total", 0),
            "最佳匹配": max(scores.values(), key=lambda x: x.get("total", 0) if isinstance(x, dict) else 0, default={}).get("label", "N/A") if scores else "N/A",
            "最高分": max((v.get("total", 0) for v in scores.values() if isinstance(v, dict)), default=0),
            "上传时间": c.get("created_at", ""),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def export_candidates_csv(candidates: list) -> bytes:
    """Export candidates to CSV bytes."""
    df = candidates_to_dataframe(candidates)
    return df.to_csv(index=False).encode("utf-8-sig")
