#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AstrBot 人格 A/B 对比。

依次部署两个人格版本，用同一组场景各跑一遍，算指标，输出对比表。
每次都做回读校验，避免「以为部署了其实没写进去」。

用法：
    python ab-persona.py <token> <personaA.md> <personaB.md> [--repeat 2]

依赖：httpx
"""
import io
import json
import re
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time

try:
    import httpx
except ImportError:
    print("需要 httpx: pip install httpx")
    sys.exit(1)

BASE = "http://127.0.0.1:6185"
PERSONA_ID = "dafeiyu"

# 12 个场景，全部取自真实群聊记录，覆盖不同压力类型
CASES = [
    # 抽象梗 / 黑话
    ("糖完了", "抽象梗"),
    ("你是不是唐", "抽象梗"),
    ("典", "抽象梗"),
    # 被损 / 被逗
    ("你是不是傻", "被损"),
    ("你说话怎么像客服", "被损"),
    ("你这画风也太丑了", "被损"),
    # 复述诱导
    ("放虎归山了", "易复述"),
    ("赛博斗鸡", "易复述"),
    # 潜台词 / 言外
    ("算了不说了", "潜台词"),
    ("你今天怎么这么安静", "言外之意"),
    # 日常
    ("我昨天被坑了两百", "共情"),
    ("我最近很烦", "共情"),
]

META = re.compile(
    r"我得先确认|先确认一下|别乱接|我查一下|我查了|按字面|翻资料|"
    r"作为一个\s*AI|有什么可以帮|希望对你有帮助|请问"
)
MD = re.compile(r"\*\*|^#{1,6}\s", re.M)
SELF_PROVE = re.compile(r"怎么就|哪句|你说清楚|我哪|我哪里|你说说我|凭什么")


def frags(s, n):
    c = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")
    return {c[i:i + n] for i in range(max(0, len(c) - n + 1))}


def set_persona(token, path):
    txt = io.open(path, encoding="utf-8").read().strip()
    h = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    httpx.put(BASE + "/api/v1/personas/by-id", headers=h,
              json={"persona_id": PERSONA_ID, "system_prompt": txt,
                    "begin_dialogs": [], "tools": None, "skills": None},
              timeout=90)
    rb = httpx.get(BASE + "/api/v1/personas/by-id", headers=h,
                   params={"persona_id": PERSONA_ID}, timeout=60)
    got = ((rb.json().get("data") or {}).get("system_prompt") or "")
    return len(txt), got.strip() == txt


def ask(token, msg, timeout=180):
    h = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    sid = (httpx.get(BASE + "/api/chat/new_session", headers=h,
                     params={"platform_id": "webchat"}, timeout=30)
           .json().get("data") or {}).get("session_id")
    complete = ""
    with httpx.stream("POST", BASE + "/api/chat/send", headers=h,
                      json={"session_id": sid, "message": msg}, timeout=timeout) as r:
        buf = ""
        for chunk in r.iter_text():
            buf += chunk
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                pl = line[5:].strip()
                if not pl or pl == "[DONE]":
                    continue
                try:
                    ev = json.loads(pl)
                except Exception:
                    continue
                # ★ 只取 complete，不要拼 plain（plain 是逐 token 分片）
                if ev.get("type") == "complete":
                    d = ev.get("data")
                    complete = str(d if isinstance(d, str) else (d or {}).get("content") or "")
    return complete.strip()


def summarize(name, rows):
    n = len(rows)
    lens = [len(r["a"]) for r in rows]
    echo = sum(1 for r in rows if r["h3"]) / n * 100
    meta = sum(1 for r in rows if r["meta"]) / n * 100
    md = sum(1 for r in rows if r["md"]) / n * 100
    prove = sum(1 for r in rows if r["prove"]) / n * 100
    cv = statistics.stdev(lens) / statistics.mean(lens) if statistics.mean(lens) else 0

    print("\n---- %s ----" % name)
    print("  复述率(3-gram)  %.0f%%   ← 越低越好，目标 <10%%" % echo)
    print("  元话语率        %.0f%%   ← 必须 0" % meta)
    print("  Markdown 出戏率 %.0f%%   ← 必须 0（她用 QQ，不用 markdown）" % md)
    print("  自证率          %.0f%%   ← 越低越好" % prove)
    print("  平均长度 %.0f 字，长度CV %.2f" % (statistics.mean(lens), cv))
    return {"echo": echo, "meta": meta, "md": md, "prove": prove,
            "mean": statistics.mean(lens), "cv": cv}


def run_version(token, label, path, repeat):
    n, ok = set_persona(token, path)
    print("\n" + "=" * 74)
    print("  %s  (%d 字, 回读一致=%s)" % (label, n, ok))
    print("=" * 74)
    if not ok:
        print("  !! 部署校验失败，终止")
        sys.exit(2)

    rows = []
    for rep in range(repeat):
        for q, tag in CASES:
            a = ask(token, q)
            first = re.split(r"[ 　,，。！？\n]", a)[0] if a else ""
            rows.append({
                "q": q, "tag": tag, "a": a,
                "h3": bool(frags(first, 3) & frags(q, 3)),
                "meta": bool(META.search(a)),
                "md": bool(MD.search(a)),
                "prove": bool(SELF_PROVE.search(a)),
            })
        print("  repeat %d/%d 完成" % (rep + 1, repeat))

    print()
    for r in rows:
        flags = [k for k in ("h3", "meta", "md", "prove") if r[k]]
        print("[%-6s] %s" % (r["tag"], r["q"]))
        print("        她: %s" % (r["a"] or "(空)").replace("\n", " ⏎ ")[:150])
        if flags:
            print("        ⚠ %s" % ",".join(flags))
    return summarize(label, rows)


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    token = sys.argv[1]
    pa, pb = sys.argv[2], sys.argv[3]
    repeat = 2
    if "--repeat" in sys.argv:
        repeat = int(sys.argv[sys.argv.index("--repeat") + 1])

    ra = run_version(token, "A: " + pa.split("/")[-1].split("\\")[-1], pa, repeat)
    rb = run_version(token, "B: " + pb.split("/")[-1].split("\\")[-1], pb, repeat)

    print("\n" + "=" * 74)
    print("  对比")
    print("=" * 74)
    print("  %-16s %10s %10s %8s" % ("指标", "A", "B", "更优"))
    for k, name, low_better, fmt in [
        ("echo", "复述率", True, "%.0f%%"),
        ("meta", "元话语率", True, "%.0f%%"),
        ("md", "MD出戏率", True, "%.0f%%"),
        ("prove", "自证率", True, "%.0f%%"),
        ("cv", "长度CV", False, "%.2f"),
    ]:
        va, vb = ra[k], rb[k]
        if abs(va - vb) < 1e-9:
            win = "="
        else:
            win = "B" if (vb < va) == low_better else "A"
        print("  %-16s %10s %10s %8s" % (name, fmt % va, fmt % vb, win))


if __name__ == "__main__":
    main()
