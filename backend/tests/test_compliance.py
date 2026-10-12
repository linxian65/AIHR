"""Unit test for the JD compliance rules (spec 20A).

Runs the rule library directly — no LLM, no MCP — to verify the regex
patterns catch the expected categories and don't false-positive on a
clean JD.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.compliance_rules import check_compliance

BAD_JD = """
招聘高级后端工程师
- 限男性，35 岁以下
- 985/211 全日制本科及以上
- 本地户口优先
- 已婚已育优先
- 形象气质佳，身高 170cm 以上
"""

GOOD_JD = """
招聘高级后端工程师
- 5 年以上后端开发经验
- 熟悉 Kubernetes、Ray、Python
- 有大规模分布式系统经验者优先
- 工作地点：南京
"""


def test_bad() -> None:
    r = check_compliance(BAD_JD)
    assert r["risk_level"] == "high", r
    cats = {i["category"] for i in r["issues"]}
    assert "性别" in cats, r
    assert "年龄" in cats, r
    assert "学历" in cats, r
    assert "地域/户籍" in cats, r
    assert "婚姻生育" in cats, r
    assert "外貌/身高" in cats, r
    print(f"[BAD] {r['summary']}")
    for i in r["issues"]:
        print(f"  - {i['category']} [{i['severity']}]: {i['matched_text']}")


def test_good() -> None:
    r = check_compliance(GOOD_JD)
    assert r["risk_level"] == "none", r
    assert len(r["issues"]) == 0, r
    print(f"[GOOD] {r['summary']}")


if __name__ == "__main__":
    test_bad()
    test_good()
    print("=== compliance rules PASS ===")
