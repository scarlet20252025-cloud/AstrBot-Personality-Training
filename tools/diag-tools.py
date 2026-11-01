#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查人格 tools 是否被关成 []（这个坑反复复发）。

⚠ 本脚本用 API/ORM 判断，不要用裸 sqlite 读：
   tools 是 JSON 列，SQLite 里存的是文本 'null'，
   裸读会误判成字符串 'null'（六个字符），实际 ORM 解出来是 None。

用法：
    python diag-tools.py <token>
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import httpx
except ImportError:
    print("需要 httpx: pip install httpx")
    sys.exit(1)

BASE = "http://127.0.0.1:6185"
PERSONA_ID = "dafeiyu"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    token = sys.argv[1]
    h = {"Authorization": "Bearer " + token}

    r = httpx.get(BASE + "/api/v1/personas/by-id", headers=h,
                  params={"persona_id": PERSONA_ID}, timeout=60)
    if r.status_code != 200:
        print("HTTP %d: %s" % (r.status_code, r.text[:200]))
        sys.exit(1)

    d = r.json().get("data") or {}
    print("=" * 66)
    print("人格: %s" % d.get("persona_id"))
    print("字数: %d" % len(d.get("system_prompt") or ""))
    print("=" * 66)

    ok = True
    for k in ("tools", "skills"):
        v = d.get(k)
        if v is None:
            print("  %-8s = None  → ✅ 使用全部工具（get_full_tool_set）" % k)
        elif v == []:
            print("  %-8s = []    → ❌ 零个工具！所有能力都会失效" % k)
            ok = False
        else:
            print("  %-8s = %r  → ⚠ 白名单，只有这 %d 个" % (k, v, len(v)))

    print()
    if ok:
        print("✅ tools 正常")
    else:
        print("❌ tools 异常，修复方法：")
        print("   python -c \"import ...\"  # 或直接跑本仓库的 fix 脚本")
        print("   把 persona 的 tools/skills 改回 None（不是 []）")
        print()
        print("   原因：astr_main_agent.py:651")
        print("     tools is None → 全部工具")
        print("     tools == []   → 零个工具")


if __name__ == "__main__":
    main()
