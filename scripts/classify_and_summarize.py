#!/usr/bin/env python3
"""Classify all books and generate summaries via GLM API using curl subprocess."""
import json, time, sys, subprocess

API_KEY = "4c160474ff51415ba57cddb3444d0d46.ZIaK5ellcilq6MGT"
BATCH_SIZE = 30

def call_glm(prompt, max_retries=3):
    body = json.dumps({
        "model": "glm-4-flash",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    })
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "120",
                 "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                 "-H", f"Authorization: Bearer {API_KEY}",
                 "-H", "Content-Type: application/json",
                 "-d", body],
                capture_output=True, text=True, timeout=130
            )
            if result.returncode != 0:
                print(f"  curl error: {result.stderr[:100]}", flush=True)
                time.sleep(3)
                continue
            resp = json.loads(result.stdout)
            if "error" in resp:
                print(f"  API error: {resp['error']}", flush=True)
                if resp['error'].get('code') == 'rate_limit':
                    time.sleep(10)
                    continue
                time.sleep(3)
                continue
            return resp["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  Attempt {attempt+1} error: {e}", flush=True)
            time.sleep(5)
    return None

CATEGORY_MAP = {
    "周易": "周易/易學", "老子": "老子/道德經", "庄子": "庄子/南華",
    "列子": "列子", "文子": "文子", "陰符經": "陰符經",
    "參同契": "參同契/丹道", "悟真篇": "悟真篇", "黃庭經": "黃庭經",
    "道藏": "道藏/正統道藏", "養生": "養生/氣功/導引",
    "龍鳳": "龍鳳文化", "詩詞·文學": "詩詞/文學",
    "内丹·外丹": "内丹/外丹", "其他": "其他",
    "道教哲學·論著": "道教哲學/論著", "道教藝術/圖像/音樂": "道教藝術/圖像/音樂",
    "道教歷史/傳記": "道教歷史/傳記", "志怪·小說": "志怪/小說",
    "年譜·目錄·工具書": "年譜/目錄/工具書", "符籙·科儀/齋醮": "符籙/科儀/齋醮",
    "佛學": "佛學", "道教地理·名山宮觀": "道教地理/名山宮觀",
    "術數/占卜/堪輿": "術數/占卜/堪輿", "儒學·經學": "儒學/經學",
    "醫學·本草": "醫學/本草",
}

AVAILABLE_TAGS = sorted(set(CATEGORY_MAP.values()))

def build_prompt(books_batch):
    books_text = "\n".join(f'{b["id"]}\t{b["title"]}' for b in books_batch)
    tags_str = "、".join(AVAILABLE_TAGS)
    return f"""你是中国传统道文化古籍分类专家。对以下书目分类并生成摘要。

可用标签：{tags_str}（可新增）

要求：
1. 每本书1-3个标签
2. 摘要10-30字，以"[AI] "开头
3. 严格返回JSON数组，无其他文字

重要：必须返回一个JSON数组包含所有结果，不要每条一个数组！
格式：[{{"id":"xxx.zip","tags":["标签1"],"summary":"[AI] 摘要"}},{{"id":"yyy.zip","tags":["标签2"],"summary":"[AI] 摘要2"}}]

书目（ID\t书名）：
{books_text}"""

def parse_response(text):
    text = text.strip()
    if "```" in text:
        # Remove code fences
        parts = text.split("```")
        text = "".join(p for p in parts[1::2] if p.strip()) or text
    # API might return multiple JSON arrays, one per line
    results = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        start = line.find('[')
        end = line.rfind(']')
        if start >= 0 and end > start:
            try:
                arr = json.loads(line[start:end+1])
                results.extend(arr)
            except:
                pass
    if results:
        return results
    # Last resort: find all JSON objects with id
    import re
    matches = re.findall(r'\{[^}]*"id"\s*:\s*"[^"]*"[^}]*\}', text)
    if matches:
        return [json.loads(m) for m in matches if json.loads(m).get("id")]
    raise ValueError(f"Cannot parse: {text[:300]}")

def main():
    print("Loading books.json...", flush=True)
    with open("src/data/books.json") as f:
        data = json.load(f)

    all_books = []
    for cat, book_list in data["books"].items():
        for b in book_list:
            all_books.append({**b, "_orig_cat": cat})
    print(f"Total: {len(all_books)} books", flush=True)

    results_file = "src/data/classification_results.jsonl"
    results = {}
    try:
        with open(results_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    results[r["id"]] = r
        print(f"Loaded {len(results)} existing", flush=True)
    except FileNotFoundError:
        pass

    # Build batches of unprocessed books
    remaining = [b for b in all_books if b["id"] not in results]
    batches = [remaining[i:i+BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]
    total_batches = len(batches)
    print(f"Remaining: {len(remaining)} books, {total_batches} batches", flush=True)

    for idx, batch in enumerate(batches):
        print(f"\n[{idx+1}/{total_batches}] {len(batch)} books...", end=" ", flush=True)
        prompt = build_prompt(batch)
        response = call_glm(prompt)
        if response is None:
            print("FAILED", flush=True)
            continue
        try:
            parsed = parse_response(response)
            with open(results_file, "a") as f:
                for item in parsed:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    results[item["id"]] = item
            print(f"OK ({len(parsed)} results)", flush=True)
        except Exception as e:
            print(f"PARSE ERROR: {e}", flush=True)
            print(f"  Raw: {response[:200]}", flush=True)
        time.sleep(1)

    print(f"\nTotal results: {len(results)}", flush=True)

    # Build new data
    print("Building new books.json...", flush=True)
    new_books = []
    tag_counts = {}
    for book in all_books:
        bid = book["id"]
        orig_cat = book["_orig_cat"]
        if bid in results:
            tags = results[bid].get("tags", [CATEGORY_MAP.get(orig_cat, "其他")])
            summary = results[bid].get("summary", "")
        else:
            tags = [CATEGORY_MAP.get(orig_cat, "其他")]
            summary = "[AI] 待补充"
        new_books.append({
            "id": bid,
            "title": book["title"],
            "tags": tags,
            "format": book.get("format", "pdf"),
            "summary": summary
        })
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    new_data = {
        "lastUpdated": data["lastUpdated"],
        "source": data["source"],
        "totalEntries": len(new_books),
        "tags": tag_counts,
        "books": new_books
    }
    with open("src/data/books.json", "w") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    print(f"Done! {len(new_books)} books, {len(tag_counts)} tags", flush=True)

if __name__ == "__main__":
    main()
