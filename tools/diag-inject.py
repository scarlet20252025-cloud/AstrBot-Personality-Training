#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查谁在往 prompt 里注东西 / 人格 tools 是否被关成 []。

这是「改了人格没效果」的第一道排查。

用法：
    python diag-inject.py <token>

输出：
  1. 人格 tools / skills 的真实类型（必须 None）
  2. 所有注册了 on_llm_request 钩子的插件
  3. 当前 self_learning 危险开关
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import httpx
except ImportError:
    print("需要 httpx: pip install httpx")
    sys.exit(1)

BASE = "http://127.0.0.1:6185"
PERSONA_ID = "dafeiyu"
PLUGINS = r"D:\AstrBot\astrbot-root\data\plugins"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    token = sys.argv[1]
    h = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

    print("=" * 72)
    print("1) 人格 tools / skills（必须是 None）")
    print("=" * 72)
    try:
        r = httpx.get(BASE + "/api/v1/personas/by-id", headers=h,
                      params={"persona_id": PERSONA_ID}, timeout=60)
        d = r.json().get("data") or {}
        for k in ("tools", "skills"):
            v = d.get(k)
            status = "✅ 全部工具可用" if v is None else (
                "❌ 零个工具！" if v == [] else "⚠ 白名单 %d 个" % len(v))
            print("  %-8s = %r   (%s)  %s" % (k, v, type(v).__name__, status))
        sp = d.get("system_prompt") or ""
        print("  system_prompt = %d 字" % len(sp))
    except Exception as e:
        print("  查询失败 %s" % e)

    print()
    print("=" * 72)
    print("2) 注册了 on_llm_request 钩子的插件（会在人格之后注入）")
    print("=" * 72)
    if os.path.isdir(PLUGINS):
        for name in sorted(os.listdir(PLUGINS)):
            d = os.path.join(PLUGINS, name)
            if not os.path.isdir(d):
                continue
            hits = []
            for dp, dns, fns in os.walk(d):
                if "__pycache__" in dp:
                    continue
                for fn in fns:
                    if not fn.endswith(".py"):
                        continue
                    fp = os.path.join(dp, fn)
                    try:
                        s = io.open(fp, encoding="utf-8", errors="ignore").read()
                    except Exception:
                        continue
                    if "@filter.on_llm_request" in s:
                        targets = re.findall(
                            r"(extra_user_content|system_prompt|req\.prompt)", s)
                        hits.append((os.path.relpath(fp, d),
                                     sorted(set(targets))))
            if hits:
                print("  ★ %s" % name)
                for f, tg in hits[:4]:
                    print("      %-46s 注入目标: %s" % (f, tg or "未识别"))

    print()
    print("=" * 72)
    print("3) self_learning 危险开关（True 即开启，应当全 False）")
    print("=" * 72)
    SL = r"D:\AstrBot\astrbot-root\data\config\astrbot_plugin_self_learning_config.json"
    if os.path.exists(SL):
        with io.open(SL, encoding="utf-8-sig") as f:
            cfg = json.load(f)
        DANGER = [
            ("MaiBot_Enhancement", "enable_expression_patterns", "注入学到的台词到用户消息之后"),
            ("MaiBot_Enhancement", "enable_realtime_expression_learning", "实时学习表达"),
            ("Social_Context_Settings", "enable_social_context_injection", "注入社交上下文"),
            ("Persona_Evolution_Settings", "enable_persona_evolution", "自动演化人格"),
            ("Persona_Evolution_Settings", "auto_apply_persona_updates", "自动套用改后的人格"),
            ("Self_Learning_Basic", "enable_auto_learning", "自动学习总开关"),
        ]
        for sec, key, desc in DANGER:
            v = (cfg.get(sec) or {}).get(key)
            mark = "❌ 危险" if v is True else "✅"
            print("  %s %-30s %-38s %s" % (mark, sec, key, desc))

        # expression_patterns 行数
        MSG = r"D:\AstrBot\astrbot-root\data\plugin_data\astrbot_plugin_self_learning\messages.db"
        if os.path.exists(MSG):
            import sqlite3
            try:
                c = sqlite3.connect("file:%s?mode=ro" % MSG.replace("\\", "/"), uri=True)
                n = c.execute("SELECT COUNT(*) FROM expression_patterns").fetchone()[0]
                c.close()
                print("\n  expression_patterns 行数: %d  %s"
                      % (n, "❌ 有污染，需清空" if n > 0 else "✅ 干净"))
            except Exception as e:
                print("  查表失败 %s" % e)
    else:
        print("  配置文件不存在")


if __name__ == "__main__":
    main()
