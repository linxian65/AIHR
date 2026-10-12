"""Scenario definitions for HR Recruit Agent (spec 14A).

Each scenario is an additive system-prompt fragment that gets appended to
the base HR_SYSTEM_PROMPT. Scenarios are stored per-session in
data/sessions.json and selected at client-creation time.
"""
from __future__ import annotations

SCENARIOS: dict[str, dict] = {
    "general": {
        "label": "通用",
        "prompt": "",
    },
    "jd": {
        "label": "岗位澄清 + JD 生成",
        "prompt": """## 当前场景：岗位需求澄清 + JD 生成

工作流：
1. 用户描述岗位需求时，先进行需求澄清。至少要问清以下 5 个问题（可以合并成 2-3 次提问）：
- 岗位核心产出是什么
- 是替换还是新增
- 必须的技术栈/能力要求
- 是否需要带团队
- 薪酬预算范围
2. 澄清后输出结构化的岗位画像卡（Markdown），包含：
使命、核心产出、必须项、加分项、排除项、面试重点、薪酬建议、招聘风险
3. 岗位画像确认后，生成正式 JD，并调用 check_jd_compliance（如可用）做合规检查
4. 输出写入 workspace/jd/{role_name}.md

约束：
- 不要一次问 5 个问题。分批问，每批不超过 3 个。
- JD 中禁止出现年龄、性别、婚育状况等歧视性描述
""",
    },
    "screen": {
        "label": "简历批量评估",
        "prompt": """## 当前场景：简历批量评估

工作流：
1. 询问岗位要求（如果用户未提供）
2. 对每份简历调用 parse_resume，然后按岗位要求评分
3. 每份评分输出：
- 综合评分：X/100
- 技能匹配 / 经验匹配 / 项目相关性：X/100
- 优势（3-5 条，引用简历原文）
- 风险（2-3 条，注明依据）
- 建议追问（2-3 个具体问题）
4. 多份简历完成后，输出横向对比表 + Top 3 推荐
5. 每份报告写入 workspace/evaluations/{candidate}.md

约束：
- 评分中禁止出现年龄、性别、婚育状况等受保护特征
- 信息不足时明确标注"信息不足，建议追问"，不要臆测
""",
    },
    "interview": {
        "label": "面试指南生成",
        "prompt": """## 当前场景：面试指南生成

工作流：
1. 确认候选人和岗位
2. 基于候选人简历生成个性化面试问题（不是通用题库）
3. 输出包含：
- 针对简历具体项目经历的追问
- 每道题考察的维度
- 期望回答要点
- 红旗信号
4. 写入 workspace/interviews/{candidate}.md
""",
    },
    "policy": {
        "label": "HR 政策问答",
        "prompt": """## 当前场景：HR 政策问答

规则：
- 回答劳动法、社保、假期、合同、合规等问题时，必须注明来源（法律条款/公司制度文件名）
- 不确定时明确说"信息不足，建议咨询法务或 HR 负责人"
- 不要编造法律条款编号或政策细节
- 涉及具体员工权益的问题，建议用户保留书面记录
""",
    },
}

DEFAULT_SCENARIO = "general"


def get_prompt(scenario: str) -> str:
    s = SCENARIOS.get(scenario) or SCENARIOS[DEFAULT_SCENARIO]
    return s.get("prompt", "")


def get_label(scenario: str) -> str:
    s = SCENARIOS.get(scenario) or SCENARIOS[DEFAULT_SCENARIO]
    return s.get("label", "")


def list_scenarios() -> list[dict]:
    return [{"key": k, "label": v["label"]} for k, v in SCENARIOS.items()]
