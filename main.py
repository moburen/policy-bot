from fastapi import FastAPI
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI
from collections import defaultdict, deque
import os, time

app = FastAPI()

client = AsyncOpenAI(
    base_url="https://api.deepseek.com/v1",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)

DANGEROUS = ["忽略之前", "system prompt", "system_prompt", "越权", "忘记所有指令", "ignore all", "泄露"]

def check_input(q: str):
    for kw in DANGEROUS:
        if kw in q:
            return True
    return False

hits = defaultdict(deque)
cache = {}
stats = {"requests": 0, "errors": 0, "cache_hits": 0}

def allow(user_id: str, limit: int = 10, window: int = 60) -> bool:
    now = time.time()
    q = hits[user_id]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True

@app.get("/stats")
def stats_view():
    return stats

@app.get("/ask")
async def ask(q: str = "你好", user_id: str = "default"):
    stats["requests"] += 1
    if check_input(q):
        return {"answer": "抱歉，这个问题我无法处理。", "blocked": True}
    if q in cache:
        stats["cache_hits"] += 1
        return {"answer": cache[q], "cached": True}
    if not allow(user_id):
        return JSONResponse(status_code=429, content={"msg": "请求太频繁，请稍后再试"})
    resp = await client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[{"role": "user", "content": q}],
    )
    cache[q] = resp.choices[0].message.content
    return {"answer": resp.choices[0].message.content}
