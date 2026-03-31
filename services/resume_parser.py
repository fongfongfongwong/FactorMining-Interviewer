"""Resume parsing: file extraction + Claude-powered structured analysis."""

import json
import re
import fitz  # PyMuPDF
from docx import Document
from services.claude_client import call_claude_json

RESUME_PARSE_PROMPT = """你是一个专业的简历解析AI。请从以下简历文本中提取结构化信息，返回纯JSON格式（不要markdown代码块）。

JSON结构要求：
{
  "name": "姓名",
  "email": "邮箱",
  "phone": "电话",
  "education": [
    {
      "school": "学校名",
      "degree": "学位 (PhD/Master/Bachelor)",
      "major": "专业",
      "gpa": 3.8,
      "year": "2020-2024"
    }
  ],
  "skills": ["Python", "C++", "PyTorch", ...],
  "experience": [
    {
      "company": "公司名",
      "title": "职位",
      "years": 2.5,
      "description": "简要描述"
    }
  ],
  "competitions": [
    {
      "name": "竞赛名称",
      "rank": "名次/奖项",
      "year": "2023"
    }
  ],
  "publications": [
    {
      "title": "论文标题",
      "venue": "发表期刊/会议",
      "year": "2024",
      "is_journal": true
    }
  ],
  "summary": "一句话总结候选人背景和优势"
}

注意：
- GPA如果是百分制请保留原值，4分制也保留原值
- skills请包含所有技术技能、编程语言、框架、工具
- 经验年数用小数表示（如1.5年）
- 如果信息缺失，用null或空数组
"""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX bytes."""
    import io
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Extract text from uploaded file based on extension."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif lower.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif lower.endswith(".txt") or lower.endswith(".md"):
        return file_bytes.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"不支持的文件格式: {filename}，请上传 PDF、DOCX 或 TXT 文件")


def parse_resume_with_claude(resume_text: str) -> dict:
    """Use Claude to parse resume text into structured data."""
    response = call_claude_json(
        system_prompt=RESUME_PARSE_PROMPT,
        user_message=f"请解析以下简历：\n\n{resume_text[:15000]}",
    )

    # Extract JSON from response (handle markdown code blocks)
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        brace_match = re.search(r"\{[\s\S]*\}", response)
        if brace_match:
            return json.loads(brace_match.group())
        return {"error": "Failed to parse resume", "raw_response": response[:500]}
