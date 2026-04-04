from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import json
import os
import requests
import redis

app = FastAPI()

# 环境变量
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "qwen-plus-2025-07-28"

# Redis 连接（Vercel Redis / Upstash）
redis_client = None
try:
    redis_client = redis.from_url(
        os.getenv("REDIS_URL", ""),
        decode_responses=True,
        socket_timeout=3,
        socket_connect_timeout=3
    )
except Exception:
    redis_client = None

# Redis 持久化存储
def get_memory():
    try:
        if redis_client:
            return json.loads(redis_client.get("memory") or "{}")
    except:
        pass
    return {}

def set_memory(mem):
    try:
        if redis_client:
            redis_client.set("memory", json.dumps(mem, ensure_ascii=False))
    except:
        pass

def get_context():
    try:
        if redis_client:
            return json.loads(redis_client.get("context") or "[]")
    except:
        pass
    return []

def set_context(ctx):
    try:
        if redis_client:
            redis_client.set("context", json.dumps(ctx, ensure_ascii=False))
    except:
        pass

# AI 对话
def ai_chat(user_msg, deep_mode):
    memory = get_memory()
    context = get_context()

    mem_text = "；".join(memory.values())
    ctx_text = "\n".join([f"U:{c['user']}\nA:{c['ai']}" for c in context[-6:]])
    prompt = f"""记忆：{mem_text}\n上下文：{ctx_text}\n用户：{user_msg}\n要求：{"详细深度思考" if deep_mode else "简短清晰"}"""

    try:
        r = requests.post(
            f"{AI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {AI_API_KEY}"},
            json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5
            },
            timeout=10
        )
        res = r.json()
        if "choices" not in res:
            return f"API 错误：{res}"

        content = res["choices"][0]["message"]["content"].strip()
        usage = res.get("usage", {})
        token = f"\n\n📊 Token：提示词={usage.get('prompt_tokens',0)} | 生成={usage.get('completion_tokens',0)} | 总计={usage.get('total_tokens',0)}"
        return content + token
    except Exception as e:
        return f"调用失败：{str(e)[:60]}"

# 首页
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Personal AI</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
body{background:#121213;color:#fff;padding:10px}
.container{max-width:440px;margin:0 auto}
.chat{height:70vh;background:#1c1c1e;border-radius:10px;padding:10px;overflow-y:auto;margin-bottom:10px}
.msg{margin:6px 0;padding:9px 12px;border-radius:14px;max-width:74%}
.user{background:#007aff;margin-left:auto}
.ai{background:#38383a;margin-right:auto}
.tools{display:flex;gap:8px;margin-bottom:8px}
#msg{width:100%;padding:10px;border-radius:20px;background:#2c2c2e;color:#fff;border:none;margin-bottom:8px}
button{padding:10px 14px;background:#007aff;color:#fff;border:none;border-radius:20px}
</style>
</head>
<body>
<div class="container">
<div class="tools">
<label><input type="checkbox" id="deep">深度思考</label>
<button onclick="window.open('/watch','_blank')">手表版</button>
<button onclick="window.open('/memory','_blank')">记忆</button>
</div>
<div class="chat" id="chat"></div>
<input id="msg" placeholder="输入...">
<button onclick="send()" style="width:100%">发送</button>
</div>
<script>
function send(){
  let m = document.getElementById('msg').value.trim();
  let d = document.getElementById('deep').checked;
  if(!m)return;
  chat.innerHTML += `<div class='msg user'>${m}</div>`;
  document.getElementById('msg').value='';
  fetch('/api/chat',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({msg:m, deep_mode:d})
  }).then(r=>r.json()).then(j=>{
    chat.innerHTML += `<div class='msg ai'>${j.reply}</div>`;
    chat.scrollTop = chat.scrollHeight;
  });
}
</script>
</body>
</html>
"""

# 手表版 + 语音输入
@app.get("/watch", response_class=HTMLResponse)
def watch():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Watch AI</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;color:#fff}
#chat{height:60vh;background:#111;padding:8px;border-radius:8px;overflow-y:auto}
.msg{margin:4px;padding:6px;border-radius:10px;max-width:80%}
.user{background:#007aff;margin-left:auto}
.ai{background:#222;margin-right:auto}
input{width:65%;padding:8px;background:#222;color:#fff;border:none;border-radius:20px}
button{padding:8px;background:#007aff;color:#fff;border:none;border-radius:20px}
</style>
</head>
<body>
<div id="chat"></div>
<br>
<button id="voice">🎤语音</button>
<input id="msg" placeholder="...">
<button onclick="send()">发送</button>
<script>
const rec = new (window.SpeechRecognition||window.webkitSpeechRecognition)();
rec.lang='zh-CN';
voice.onclick=()=>rec.start();
rec.onresult=e=>document.getElementById('msg').value=e.results[0][0].transcript;
function send(){
  let m=document.getElementById('msg').value.trim();
  if(!m)return;
  fetch('/api/chat',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({msg:m,deep_mode:false})
  }).then(r=>r.json()).then(j=>{
    chat.innerHTML+=`<div class='msg user'>${m}</div><div class='msg ai'>${j.reply}</div>`;
    document.getElementById('msg').value='';
  });
}
</script>
</body>
</html>
"""

# 记忆面板
@app.get("/memory", response_class=HTMLResponse)
def memory():
    mem = get_memory()
    lines = "".join([f"<div style='margin:4px'>• {v}</div>" for k, v in mem.items()])
    return f"""
    <div style='background:#121213;color:#fff;padding:20px'>
    <h3>永久记忆</h3>{lines}</div>
    """

# 聊天接口
class ChatReq(BaseModel):
    msg: str
    deep_mode: bool

def chat_api(req: ChatReq):
    msg = req.msg
    deep = req.deep_mode
    reply = ai_chat(msg, deep)

    # 存储到 Redis
    ctx = get_context()
    ctx.append({"user": msg, "ai": reply})
    if len(ctx) > 6:
        ctx.pop(0)
    set_context(ctx)

    mem = get_memory()
    mem[str(len(mem) + 1)] = msg[:80]
    set_memory(mem)

    return {"reply": reply}

app.post("/api/chat")(chat_api)

# Vercel 入口
handler = app
