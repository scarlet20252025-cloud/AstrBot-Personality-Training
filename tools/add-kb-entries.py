#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""往 AstrBot 知识库批量添加词条（预切块导入，一条 chunk 一个词条）。

这是「抽象黑话」的正确落地方式：进知识库走检索，不要写进人格。
写进人格会被当成台词逐字照抄。

用法：
    python add-kb-entries.py <token> --kb "网络流行语释义库" --file entries.txt
    python add-kb-entries.py <token> --kb "网络流行语释义库" --text "词条|释义|详解"

条目文件格式（每段用空行分隔，三段一行）：
    词条A
    释义（一句话）
    详解（可以长一点，说明用法和别按字面理解的地方）

    词条B
    释义
    详解
"""
import io
import json
import sys
import time

try:
    import httpx
except ImportError:
    print("需要 httpx: pip install httpx")
    sys.exit(1)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:6185"


def find_kb(token, name):
    h = {"Authorization": "Bearer " + token}
    r = httpx.get(BASE + "/api/v1/knowledge-bases", headers=h,
                  params={"page": 1, "page_size": 100}, timeout=60)
    d = r.json().get("data") or {}
    for it in (d.get("items") or []):
        if it.get("kb_name") == name or it.get("name") == name:
            return it.get("kb_id")
    return None


def parse_entries(text):
    """三段一组（词条/释义/详解），空行分隔段落。"""
    blocks = [b.strip() for b in text.strip().split("\n\n") if b.strip()]
    out = []
    for b in blocks:
        lines = [x.strip() for x in b.split("\n") if x.strip()]
        if len(lines) >= 2:
            title = lines[0]
            short = lines[1]
            detail = "\n".join(lines[2:]) if len(lines) > 2 else ""
            out.append("【词条】%s\n【释义】%s\n【详解】%s" % (title, short, detail))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    token = sys.argv[1]

    kb_name = None
    file_path = None
    inline = None
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--kb" and i + 1 < len(args):
            kb_name = args[i + 1]; i += 2
        elif args[i] == "--file" and i + 1 < len(args):
            file_path = args[i + 1]; i += 2
        elif args[i] == "--text" and i + 1 < len(args):
            inline = args[i + 1]; i += 2
        else:
            i += 1

    if not kb_name:
        print("必须指定 --kb")
        sys.exit(1)

    if file_path:
        raw = io.open(file_path, encoding="utf-8").read()
    elif inline:
        raw = inline.replace("|", "\n")
    else:
        print("必须给 --file 或 --text")
        sys.exit(1)

    chunks = parse_entries(raw)
    if not chunks:
        print("没解析出任何词条，检查格式")
        sys.exit(1)

    kb_id = find_kb(token, kb_name)
    print("知识库 %s -> %s" % (kb_name, kb_id))
    if not kb_id:
        sys.exit(1)

    print("待导入 %d 条：" % len(chunks))
    for c in chunks:
        print("   - %s" % c.split("\n")[0].replace("【词条】", ""))

    h = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    body = {
        "documents": [{
            "file_name": "补充词条-%s" % time.strftime("%m%d%H%M"),
            "file_type": "txt",
            "chunks": chunks,
        }],
        "batch_size": 16, "tasks_limit": 2, "max_retries": 3,
    }
    r = httpx.post(BASE + "/api/v1/knowledge-bases/%s/documents/import" % kb_id,
                   headers=h, json=body, timeout=180)
    print("\n提交: %d %s" % (r.status_code, r.text[:200]))

    tid = None
    try:
        tid = (r.json().get("data") or {}).get("task_id")
    except Exception:
        pass

    if tid:
        for _ in range(60):
            time.sleep(3)
            rr = httpx.get(BASE + "/api/v1/knowledge-bases/tasks/%s" % tid,
                           headers=h, timeout=60)
            st = (rr.json().get("data") or {}).get("status")
            print("  status=%s" % st)
            if st in ("completed", "failed"):
                break

    rr = httpx.get(BASE + "/api/v1/knowledge-bases/%s/stats" % kb_id,
                   headers=h, timeout=60)
    d = rr.json().get("data") or {}
    print("\n当前库: doc=%s chunk=%s" % (d.get("doc_count"), d.get("chunk_count")))


if __name__ == "__main__":
    main()
