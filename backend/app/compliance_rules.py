"""JD compliance rules (spec 20A).

Hard-coded regex rule library for Chinese employment-discrimination language.
LLM-based detection is too noisy (e.g. flagging "有大型项目经验者优先" as age
bias), so the first pass is rule-based; an LLM layer can be added later for
semantic checks if needed.
"""
from __future__ import annotations

import re
from typing import TypedDict


class Issue(TypedDict):
    category: str
    severity: str
    matched_text: str
    position: int
    law_reference: str
    suggestion: str


class Rule(TypedDict):
    category: str
    severity: str
    patterns: list[re.Pattern[str]]
    law_reference: str
    suggestion: str


RULES: list[Rule] = [
    {
        "category": "性别",
        "severity": "high",
        "patterns": [
            re.compile(r"限?男性|限?女性|男生优先|女生优先|仅限男|仅限女"),
            re.compile(r"男性优先|女性优先"),
            re.compile(r"男士?为主|女士?为主|要求?男|要求?女"),
        ],
        "law_reference": "《就业促进法》第 27 条、《妇女权益保障法》第 43 条",
        "suggestion": "删除性别要求。岗位胜任力与性别无关，改为'不限'或直接删除。",
    },
    {
        "category": "年龄",
        "severity": "high",
        "patterns": [
            re.compile(r"\d{2}\s*岁?以下"),
            re.compile(r"不超过\s*\d{2}\s*岁"),
            re.compile(r"年龄\s*[<≤]\s*\d{2}"),
            re.compile(r"35\s*岁|30\s*岁|28\s*岁"),
        ],
        "law_reference": "《就业促进法》第 3 条、第 26 条",
        "suggestion": "删除年龄限制。改为'具备 X 年以上相关经验'等能力性描述。",
    },
    {
        "category": "地域/户籍",
        "severity": "high",
        "patterns": [
            re.compile(r"本地户口|本市户口|限本地|仅限本地"),
            re.compile(r"不招\s*[一-龥]{2,4}\s*人"),
            re.compile(r"限\s*[一-龥]{2,4}\s*户籍"),
        ],
        "law_reference": "《就业促进法》第 3 条、第 26 条",
        "suggestion": "删除地域和户籍要求。工作地点可通过'工作地点：XX'单独说明。",
    },
    {
        "category": "学历",
        "severity": "medium",
        "patterns": [
            re.compile(r"985|211|双一流"),
            re.compile(r"仅限\s*统招|全日制本科(?:及)?以上|仅限\s*全日制"),
            re.compile(r"清北|清华|北大|C9"),
        ],
        "law_reference": "《就业促进法》第 3 条（学历歧视争议）",
        "suggestion": "如岗位确实需要，改为'本科及以上学历'或'相关专业背景'。如无硬性要求，删除具体院校标准。",
    },
    {
        "category": "婚姻生育",
        "severity": "high",
        "patterns": [
            re.compile(r"已婚(?:已育)?优先|未婚优先|已婚已育"),
            re.compile(r"无(?:生育|二胎|三胎)计划|不计划?生育"),
            re.compile(r"已?婚育?状况"),
        ],
        "law_reference": "《妇女权益保障法》第 43 条、《就业促进法》第 27 条",
        "suggestion": "删除所有与婚姻、生育相关的要求。这类信息不得作为录用条件。",
    },
    {
        "category": "外貌/身高",
        "severity": "medium",
        "patterns": [
            re.compile(r"形(?:象|貌)\s*(?:好|佳|佳者)"),
            re.compile(r"\d{3}\s*cm\s*以上|身高\s*\d{3}"),
            re.compile(r"五官端正|容貌端庄"),
        ],
        "law_reference": "《就业促进法》第 3 条",
        "suggestion": "除非岗位（如前台、演艺）确有硬性要求，否则删除外貌描述。",
    },
    {
        "category": "健康/残障",
        "severity": "high",
        "patterns": [
            re.compile(r"无\s*传染病|无\s*残疾|身体健?康(?:无)?残"),
            re.compile(r"要求?\s*身体健?康(?:，|,|。|$)"),
        ],
        "law_reference": "《残疾人保障法》第 38 条、《就业促进法》第 29 条",
        "suggestion": "删除健康/残障相关描述。如岗位有特殊要求，需明确列出具体岗位能力要求，不能笼统排除。",
    },
]


SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def check_compliance(jd_text: str) -> dict:
    """Run the rule library against `jd_text` and return a structured report.

    Returns a dict shaped like:
        {
            "risk_level": "high" | "medium" | "low" | "none",
            "issues": [Issue, ...],
            "summary": str,
        }
    """
    issues: list[Issue] = []
    for rule in RULES:
        for pattern in rule["patterns"]:
            for match in pattern.finditer(jd_text):
                issues.append({
                    "category": rule["category"],
                    "severity": rule["severity"],
                    "matched_text": match.group(0),
                    "position": match.start(),
                    "law_reference": rule["law_reference"],
                    "suggestion": rule["suggestion"],
                })

    # Dedupe: same category + same matched text collapses into one issue.
    # (Two rules can match the same substring, e.g. "35 岁" hits both an
    # age rule and a generic digit rule; we keep only the first hit.)
    issues.sort(key=lambda x: (x["position"], -len(x["matched_text"])))
    deduped: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    for i in issues:
        key = (i["category"], i["matched_text"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(i)

    if not deduped:
        risk_level = "none"
    else:
        max_sev = max(SEVERITY_WEIGHT[i["severity"]] for i in deduped)
        if max_sev >= 3:
            risk_level = "high"
        elif max_sev >= 2:
            risk_level = "medium"
        else:
            risk_level = "low"

    if not deduped:
        summary = "未发现明显的合规风险。"
    else:
        cats = sorted({i["category"] for i in deduped})
        summary = f"发现 {len(deduped)} 处潜在合规问题，涉及 {'、'.join(cats)}。"

    return {
        "risk_level": risk_level,
        "issues": deduped,
        "summary": summary,
    }
