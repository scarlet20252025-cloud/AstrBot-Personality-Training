#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测句式模板化程度（Template Collapse）。

三个指标：
  两段式占比   连续回复正好两行的比例 —— 模板病的最强信号
  长度变异系数 真人打字长短参差，模板则整齐（CV 越低越可疑）
  相邻同头率   连续两条用同样开头

用法：
    python measure-template.py <transcript.json>
"""
import io
import json
import re
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOT_ID = "2824447359"


def clean(s):
    s = re.sub(r"\[[^\[\]]{0,60}\][^\n]*\n?", "", s or "")
    s = re.sub(r"^\S+\(ID:\d+\)\s*:?\s*", "", s)
    return s.strip()


def load_replies(path):
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)

    replies = []

    if isinstance(data, list) and data and isinstance(data[0], dict) \
            and "message_str" in data[0]:
        for m in data:
            s = m.get("sender") or {}
            if str(s.get("user_id")) != BOT_ID:
                continue
            t = clean(m.get("message_str"))
            if t:
                replies.append(t)
        return replies, "chat_history"

    def walk(node):
        if isinstance(node, dict):
            if "a" in node and isinstance(node["a"], str):
                replies.append(node["a"])
            else:
                for v in node.values():
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return replies, "ab-result"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    replies, kind = load_replies(path)

    if not replies:
        print("没解析出回复，检查输入格式")
        sys.exit(1)

    n = len(replies)
    print("# 模板化检测  共 %d 条（来源: %s）" % (n, kind))
    print()

    # 1) 两段式
    seg_counts = {}
    for r in replies:
        k = len([x for x in r.split("\n") if x.strip()])
        seg_counts[k] = seg_counts.get(k, 0) + 1
    print("## 分段数分布")
    for k in sorted(seg_counts):
        print("   %d 段: %-3d 条 (%.0f%%)" % (k, seg_counts[k], seg_counts[k] * 100.0 / n))
    two = seg_counts.get(2, 0)
    print("   两段式占比: %.0f%%  %s"
          % (two * 100.0 / n, "⚠ 偏高（>60% 为模板病）" if two * 100.0 / n > 60 else "正常"))
    print()

    # 2) 长度变异系数
    lens = [len(r.replace("\n", "").replace(" ", "")) for r in replies]
    mean = statistics.mean(lens)
    cv = statistics.stdev(lens) / mean if mean and n > 1 else 0
    print("## 长度")
    print("   均值 %.1f 中位 %d 范围 %d-%d" % (mean, statistics.median(lens), min(lens), max(lens)))
    print("   变异系数 %.2f  %s" % (cv, "⚠ 太整齐（<0.5 一眼假）" if cv < 0.5 else "正常"))
    print()

    # 3) 相邻同头 / 同尾
    heads = [r.strip()[:2] for r in replies]
    tails = [re.sub(r"[\s，,。.！!？?~～]+$", "", r.strip())[-1:] for r in replies]
    same_head = sum(1 for i in range(1, n) if heads[i] == heads[i - 1]) / (n - 1) if n > 1 else 0
    same_tail = sum(1 for i in range(1, n) if tails[i] == tails[i - 1]) / (n - 1) if n > 1 else 0
    print("## 相邻重复")
    print("   同头率 %.0f%%  %s" % (same_head * 100, "⚠ 开头坍缩（>40%）" if same_head > 0.4 else "正常"))
    print("   同尾率 %.0f%%" % (same_tail * 100))
    print()

    # 分布
    from collections import Counter
    print("## 开头两字分布")
    for w, c in Counter(heads).most_common(8):
        print("   「%s」%d 次" % (w, c))
    print()
    print("## 结尾字分布")
    for w, c in Counter(tails).most_common(8):
        print("   「%s」%d 次" % (w, c))


if __name__ == "__main__":
    main()
