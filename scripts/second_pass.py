#!/usr/bin/env python3
"""Second pass: classify remaining unclassified books."""
import json, time, subprocess, re

API_KEY = "4c160474ff51415ba57cddb3444d0d46.ZIaK5ellcilq6MGT"

with open("src/data/books.json") as f:
    data = json.load(f)

missing = [b for b in data["books"] if not b.get("summary") or b.get("summary") == "[AI] 待补充"]
print(f"Missing: {len(missing)} books", flush=True)

def call_glm(prompt, retries=3):
    body = json.dumps({"model": "glm-4-flash", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3})
    for i in range(retries):
        try:
            r = subprocess.run(
                ["curl", "-s", "--max-time", "120",
                 "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                 "-H", f"Authorization: Bearer {API_KEY}",
                 "-H", "Content-Type: application/json", "-d", body],
                capture_output=True, text=True, timeout=130)
            if r.returncode != 0:
                time.sleep(3); continue
            resp = json.loads(r.stdout)
            if "error" in resp:
                print(f"  API err: {resp['error'].get('code','')}", flush=True)
                time.sleep(5); continue
            return resp["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  Err: {e}", flush=True)
            time.sleep(5)
    return None

def parse(text):
    # Remove markdown code fences
    text = re.sub(r'```(?:json)?\n?', '', text)
    text = text.strip()
    # Find all JSON objects with "id" field
    results = []
    # Try as single array first
    try:
        s, e = text.find('['), text.rfind(']')
        if s >= 0 and e > s:
            results = json.loads(text[s:e+1])
            if isinstance(results, list) and results and isinstance(results[0], dict) and "id" in results[0]:
                return results
    except:
        pass
    # Try line by line
    for line in text.split('\n'):
        line = line.strip()
        if not line or '[' not in line: continue
        s, e = line.find('['), line.rfind(']')
        if s >= 0 and e > s:
            try:
                arr = json.loads(line[s:e+1])
                if isinstance(arr, list):
                    for item in arr:
                        if isinstance(item, dict) and "id" in item:
                            results.append(item)
            except:
                pass
    # Last resort: regex for individual objects
    if not results:
        for m in re.finditer(r'\{[^{}]*"id"\s*:\s*"[^"]*"[^{}]*\}', text):
            try:
                obj = json.loads(m.group())
                if "id" in obj:
                    results.append(obj)
            except:
                pass
    return results

TAGS = "周易/易學、老子/道德經、庄子/南華、列子、文子、陰符經、參同契/丹道、悟真篇、黃庭經、内丹/外丹、道藏/正統道藏、養生/氣功/導引、符籙/科儀/齋醮、術數/占卜/堪輿、醫學/本草、道教哲學/論著、道教歷史/傳記、道教地理/名山宮觀、道教藝術/圖像/音樂、龍鳳文化、儒學/經學、佛學、詩詞/文學、志怪/小說、年譜/目錄/工具書、其他"

updated = 0
for i in range(0, len(missing), 20):
    batch = missing[i:i+20]
    bn = i // 20 + 1
    total_b = (len(missing) + 19) // 20
    print(f"[{bn}/{total_b}] {len(batch)} books...", end=" ", flush=True)
    
    books_text = "\n".join(f'{b["id"]}\t{b["title"]}' for b in batch)
    prompt = f"""对以下古籍分类并写摘要。
标签:{TAGS}
返回一个JSON数组:[{{"id":"xxx","tags":["标签"],"summary":"[AI] 摘要"}}]
所有结果放在同一个数组中！

书目:
{books_text}"""
    
    resp = call_glm(prompt)
    if not resp:
        print("FAILED", flush=True)
        continue
    
    parsed = parse(resp)
    if not parsed:
        print("PARSE ERROR", flush=True)
        # Debug: save raw response
        with open("/tmp/glm_debug.txt", "a") as f:
            f.write(f"--- Batch {bn} ---\n{resp[:500]}\n\n")
        continue
    
    id_map = {p["id"]: p for p in parsed if "id" in p}
    for b in batch:
        if b["id"] in id_map:
            p = id_map[b["id"]]
            b["tags"] = p.get("tags", b.get("tags", ["其他"]))
            b["summary"] = p.get("summary", "")
            updated += 1
    print(f"OK ({len(parsed)} parsed, {sum(1 for b in batch if b['id'] in id_map)} matched)", flush=True)
    time.sleep(1)

print(f"\nUpdated: {updated}/{len(missing)}", flush=True)

# For any still missing, set default
for b in data["books"]:
    if not b.get("summary"):
        b["summary"] = "[AI] 道文化古籍文献"

# Rewrite
tag_counts = {}
for b in data["books"]:
    for t in b.get("tags", ["其他"]):
        tag_counts[t] = tag_counts.get(t, 0) + 1
data["tags"] = tag_counts

with open("src/data/books.json", "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

no_sum = sum(1 for b in data["books"] if not b.get("summary"))
print(f"Remaining no-summary: {no_sum}", flush=True)
print(f"Total books: {len(data['books'])}, Tags: {len(tag_counts)}", flush=True)
