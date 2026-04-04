from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import json
import os
import requests
import redis

app = FastAPI()

AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "qwen-plus-2025-07-28"

# Redis
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

def get_memory():
    try:
        if redis_client:
            return json.loads(redis_client.get("memory") or "{}")
    except:
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
        return []

def set_context(ctx):
    try:
        if redis_client:
            redis_client.set("context", json.dumps(ctx, ensure_ascii=False))
    except:
        pass

# 替换原来的 ai_chat 函数
def ai_chat(user_msg, deep_mode):
    memory = get_memory()
    context = get_context()
    mem_text = "；".join(memory.values())
    ctx_text = "\n".join([f"U:{c['user']}\nA:{c['ai']}" for c in context[-6:]])
    prompt = f"""记忆：{mem_text}\n上下文：{ctx_text}\n用户：{user_msg}\n要求：{"详细深度思考" if deep_mode else "简短清晰"}"""

    try:
        # 关键修复：强制 TLS、超时、SNI、关闭代理
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        from urllib3.exceptions import InsecureRequestWarning

        # 禁用SSL警告（Vercel环境证书问题）
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)

        r = session.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={
                "Authorization": "Bearer " + AI_API_KEY, 
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            json={
                "model": "qwen-plus",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.6
            },
            timeout=15,
            verify=False,  # 关键：Vercel环境证书不兼容
            allow_redirects=True
        )

        res = r.json()

        # --------------------------
        # ✅ 在这里计算并显示 Token
        # --------------------------
        if "choices" not in res:
            return f"API错误：{res}"
        
        content = res["choices"][0]["message"]["content"].strip()
        usage = res.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        token_info = f"\n\n📊 Token 消耗\n• 提示词：{prompt_tokens}\n• 生成：{completion_tokens}\n• 总计：{total_tokens}"
        return content + token_info

    except Exception as e:
        return f"调用失败：{str(e)[:100]}"

# PWA Manifest
@app.get("/manifest.json")
def manifest():
    data = {
        "name": "Personal AI",
        "short_name": "AI",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#121213",
        "theme_color": "#007aff",
        "icons": [{
            "src": "https://cdn-icons-png.flaticon.com/512/5996/5996926.png",
            "sizes": "512x512",
            "type": "image/png"
        }]
    }
    return HTMLResponse(json.dumps(data), media_type="application/json")

# 主页美化版
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Personal AI</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#007aff">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial}
body{background:#0c0c0e;color:#e3e3e3;min-height:100vh;padding:12px}
.container{max-width:540px;margin:0 auto}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.header h1{font-size:20px;color:#fff}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.btn{padding:8px 12px;border-radius:14px;background:#1c1c1e;border:none;color:#fff;font-size:14px}
.btn-primary{background:#007aff;color:white}
.chat{height:72vh;background:#141417;border-radius:18px;padding:14px;overflow-y:auto;display:flex;flex-direction:column;gap:10px}
.msg{padding:10px 14px;border-radius:16px;max-width:80%;line-height:1.5}
.user{align-self:flex-end;background:#007aff;color:white}
.ai{align-self:flex-start;background:#24242a;color:#e3e3e3}
.input-bar{position:sticky;bottom:0;background:#0c0c0e;padding-top:10px}
.input-wrap{display:flex;gap:8px}
input{flex:1;padding:14px 16px;border-radius:24px;background:#1c1c1e;border:none;color:#fff;font-size:15px}
.send-btn{width:48px;height:48px;border-radius:50%;background:#007aff;border:none;color:white;font-size:18px}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>Personal AI</h1>
</div>
<div class="toolbar">
<label style="display:flex;align-items:center;gap:6px;background:#1c1c1e;padding:6px 10px;border-radius:12px">
<input type="checkbox" id="deep">深度思考
</label>
<button class="btn" onclick="window.open('/watch','_blank')">⌚ 手表版</button>
<button class="btn" onclick="window.open('/memory','_blank')">🧠 记忆</button>
</div>
<div class="chat" id="chat"></div>
<div class="input-bar">
<div class="input-wrap">
<input id="msg" placeholder="输入消息..." autocomplete="off">
<button class="send-btn" onclick="send()">↑</button>
</div>
</div>
</div>
<script>
function send(){
  const m = document.getElementById('msg').value.trim();
  const d = document.getElementById('deep').checked;
  if(!m)return;
  const chat = document.getElementById('chat');
  chat.innerHTML += `<div class='msg user'>${m}</div>`;
  document.getElementById('msg').value='';
  fetch('/api/chat',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({msg:m,deep_mode:d})
  }).then(res=>res.json()).then(j=>{
    chat.innerHTML += `<div class='msg ai'>${j.reply}</div>`;
    chat.scrollTop = chat.scrollHeight;
  });
}
document.getElementById('msg').addEventListener('keypress',e=>{
  if(e.key==='Enter')send()
})
</script>
</body>
</html>
"""

# 手表美化版
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
body{background:#000;color:#fff;font-family:-apple-system}
#chat{height:55vh;background:#111;border-radius:12px;padding:10px;overflow-y:auto}
.msg{margin:4px;padding:6px 10px;border-radius:12px;max-width:80%;font-size:14px}
.user{background:#007aff;margin-left:auto}
.ai{background:#222;margin-right:auto}
.input{display:flex;gap:6px;margin-top:10px}
#msg{flex:1;padding:10px;border-radius:20px;background:#222;color:#fff;border:none}
button{padding:10px 12px;background:#007aff;color:#fff;border:none;border-radius:20px}
</style>
</head>
<body>
<div id="chat"></div>
<div class="input">
<button id="voice">🎤</button>
<input id="msg" placeholder="...">
<button onclick="send()">发送</button>
</div>
<script>
const rec = new (window.SpeechRecognition||window.webkitSpeechRecognition)();
rec.lang='zh-CN';
voice.onclick=()=>rec.start();
rec.onresult=e=>document.getElementById('msg').value=e.results[0][0].transcript;
function send(){
  const m=document.getElementById('msg').value.trim();
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
    items = "".join([f"<div style='padding:8px;background:#1c1c1e;border-radius:12px;margin:4px'>• {v}</div>" for k,v in mem.items()])
    return f"""
<div style='background:#0c0c0e;color:#fff;padding:20px;min-height:100vh'>
<h2 style='margin-bottom:14px'>🧠 永久记忆</h2>
{items}
</div>
"""

# 接口
class ChatReq(BaseModel):
    msg: str
    deep_mode: bool

def chat_api(req: ChatReq):
    msg = req.msg
    deep = req.deep_mode
    reply = ai_chat(msg, deep)

    ctx = get_context()
    ctx.append({"user": msg, "ai": reply})
    if len(ctx) > 6:
        ctx.pop(0)
    set_context(ctx)

    mem = get_memory()
    mem[str(len(mem)+1)] = msg[:80]
    set_memory(mem)

    return {"reply": reply}

app.post("/api/chat")(chat_api)

# Vercel
handler = app
