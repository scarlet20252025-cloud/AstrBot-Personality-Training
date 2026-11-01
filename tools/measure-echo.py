#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测「首句复述对方」的比例（Echo Rate）。

这是「她喜欢附属别人话」这个投诉的唯一量化口径。

用法：
    python measure-echo.py <transcript.json> [--persona-file <人格文件>]

输入两种格式任一：
  A) chat_history 格式（AstrBot group_chat_plus 的 chat_history/*.json）
     —— 直接读真实群聊记录，BOT_ID 自动取 2824447359
  B) 测试结果格式（ab 脚本产出的 json，含 q / a 字段）

输出：2-gram / 3-gram 复述率 + 例子
"""
import io
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOT_ID = "2824447359"


def frags(s, n):
    c = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")
    return {c[i:i + n] for i in range(max(0, len(c) - n + 1))}


def clean(s):
    s = re.sub(r"\[[^\]]{0,80}\]", "", s or "")
    s = re.sub(r"^\S+\(ID:\d+\)\s*:?\s*", "", s)
    s = re.sub(r"\[引用[^\]]*\]", "", s)
    return s.strip()


def load_pairs(path):
    """统一成 [(user_msg, bot_reply), ...]"""
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)

    pairs = []

    # A) chat_history：list of message dicts
    if isinstance(data, list) and data and isinstance(data[0], dict) \
            and "message_str" in data[0]:
        for i in range(1, len(data)):
            cur, prev = data[i], data[i - 1]
            cs = cur.get("sender") or {}
            ps = prev.get("sender") or {}
            if str(cs.get("user_id")) != BOT_ID:
                continue
            if str(ps.get("user_id")) == BOT_ID:
                continue
            ct = clean(cur.get("message_str"))
            pt = clean(prev.get("message_str"))
            if ct and pt:
                pairs.append((pt, ct))
        return pairs, "chat_history"

    # B) ab 测试结果：{tag: {rows: [{q,a}]}} 或 [[q,a],...]
    def walk(node):
        if isinstance(node, dict):
            if "q" in node and "a" in node:
                pairs.append((str(node["q"]), str(node["a"])))
            else:
                for v in node.values():
                    walk(v)
        elif isinstance(node, list):
            if len(node) == 2 and all(isinstance(x, str) for x in node):
                pairs.append((node[0], node[1]))
            else:
                for v in node:
                    walk(v)

    walk(data)
    return pairs, "ab-result"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    pairs, kind = load_pairs(path)

    if not pairs:
        print("没解析出配对，检查输入格式")
        sys.exit(1)

    print("# 复述检测  共 %d 对（来源: %s）" % (len(pairs), kind))
    print()

    hit2 = hit3 = 0
    examples = []
    for pt, ct in pairs:
        first = re.split(r"[ 　,，。！？\n]", ct)[0] if ct else ""
        f2 = frags(first, 2) & frags(pt, 2)
        f3 = frags(first, 3) & frags(pt, 3)
        if f2:
            hit2 += 1
        if f3:
            hit3 += 1
            if len(examples) < 12:
                examples.append((pt, ct, sorted(f3)))

    n = len(pairs)
    print("首句含对方 2-gram: %d/%d = %.0f%%" % (hit2, n, hit2 * 100.0 / n))
    print("首句含对方 3-gram: %d/%d = %.0f%%" % (hit3, n, hit3 * 100.0 / n))
    print()
    print("目标：3-gram < 10%")
    print()
    if examples:
        print("## 复述例子")
        for pt, ct, ov in examples:
            print("  对方: %s" % pt.replace("\n", " ")[:80])
            print("  她  : %s" % ct.replace("\n", " ")[:80])
            print("        搬用: %s" % ov)
            print()


if __name__ == "__main__":
    main()
