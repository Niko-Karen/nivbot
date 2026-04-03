# 私人记忆聊天智能体 · 完整功能版
from fastapi import FastAPI, UploadFile, File, Form ,Cookie,Request
from fastapi.responses import HTMLResponse,RedirectResponse
from pydantic import BaseModel
import json
import os
import requests

app = FastAPI()

# ====================== 配置区（你只改这里）======================
AI_API_KEY = "sk-7bd482a591c04dee85e363ddd33b3fde"
AI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 国内可填：https://api.deepseek.com
MODEL_NAME = "qwen-plus-2025-07-28"  # qwen
LOGIN_PASSWORD = "200992"
MAX_MEMORY = 20  # 最大记忆条数（省Token）
MAX_CONTEXT = 12  # 最大上下文轮数


# ===============================================================

# 安全读写JSON
def load_json(path, default={}):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

# 记忆压缩
def compress_memory():
    mem = load_json("memory.json", {})
    if len(mem) > MAX_MEMORY:
        new_mem = {}
        keys = sorted(mem.keys())[-MAX_MEMORY:]
        for i, k in enumerate(keys):
            new_mem[str(i+1)] = mem[k]
        save_json("memory.json", new_mem)

# 提取记忆
def extract_memory(user_msg, ai_reply):
    memory = load_json("memory.json", {})
    prompt = f"""从对话提取1-2条关键信息，极简：
用户：{user_msg}
AI：{ai_reply}
输出一行一条"""
    try:
        r = requests.post(
            f"{AI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {AI_API_KEY}"},
            json={"model": MODEL_NAME,"messages": [{"role": "user", "content": prompt}],"temperature": 0.1},
            timeout=10
        )
        res = r.json()
        # lines = res["choices"][0]["message"]["content"].strip().split("\n")
        if "choices" not in res:
            return
        content = res["choices"][0]["message"]["content"].strip()
        lines = content.split("\n")
        for line in lines[:2]:
            line = line.strip()
            if line and len(line) > 2:
                memory[str(len(memory)+1)] = line[:90]
        compress_memory()
        save_json("memory.json", memory)
    except:
        pass


def ai_chat(user_msg, deep_mode):
    memory = load_json("memory.json", {})
    ctx = load_json("context.json", [])
    mem_text = "；".join(memory.values())
    ctx_text = "\n".join([f"U:{x['user']}\nA:{x['ai']}" for x in ctx[-MAX_CONTEXT:]])
    prompt = f"""记忆：{mem_text}\n上下文：{ctx_text}\n用户：{user_msg}\n要求：{"详细深度思考回答" if deep_mode else "简短清晰回答"}"""

    try:
        r = requests.post(
            f"{AI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {AI_API_KEY}"},
            json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5
            },
            timeout=20
        )
        res = r.json()
        content = res["choices"][0]["message"]["content"].strip()
        usage = res.get("usage", {})
        token_info = f"\n\n\n📊 Token用量：提示词={usage.get('prompt_tokens', 0)} | 生成={usage.get('completion_tokens', 0)} | 总计={usage.get('total_tokens', 0)}"
        return content + token_info
    except Exception as e:
        return f"Qwen调用失败：{str(e)[:50]}"

# ====================== 登录密码保护 ======================
@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>登录</title></head>
    <body style="background:#121213;color:#fff;text-align:center;padding-top:50px">
        <h2>私人AI登录</h2>
        <form method="post" action="/login">
            <input type="password" name="pwd" placeholder="输入密码" style="padding:10px;width:200px;margin:10px">
            <button style="padding:10px 20px;background:#007aff;color:#fff;border:none;border-radius:8px">登录</button>
        </form>
    </body></html>
    """

@app.post("/login")
def login(pwd: str = Form(...)):
    if pwd == LOGIN_PASSWORD:
        res = RedirectResponse("/", status_code=302)
        res.set_cookie(key="auth", value="ok", max_age=7*24*3600)
        return res
    return RedirectResponse("/login", status_code=302)

# 鉴权中间件
async def check_auth(auth: str = Cookie(None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=302)

# ====================== 主界面 ======================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, auth: str = Cookie(None)):
    if auth != "ok":
        return RedirectResponse("/login")
    return """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>记忆AI</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
        html,body{background:#121213;color:#fff;height:100vh;padding:8px}
        .container{max-width:440px;margin:0 auto;height:100%;display:flex;flex-direction:column}
        .chat{flex:1;overflow-y:auto;padding:10px;background:#1c1c1e;border-radius:10px;margin-bottom:8px}
        .msg{margin:6px 0;padding:9px 12px;border-radius:14px;max-width:74%;line-height:1.4}
        .msg.user{background:#007aff;margin-left:auto}
        .msg.ai{background:#38383a;margin-right:auto}
        .tools{font-size:13px;color:#888;display:flex;gap:8px;margin-bottom:4px;flex-wrap:wrap}
        .input-bar{display:flex;gap:8px}
        #msg{flex:1;padding:10px 12px;border-radius:20px;border:none;background:#2c2c2e;color:#fff}
        button{padding:10px 14px;border-radius:20px;border:none;background:#007aff;color:#fff}
    </style>
</head>
<body>
<div class="container">
    <div class="tools">
        <label><input type="checkbox" id="deep">深度思考</label>
        <button onclick="window.open('/watch','_blank')">手表版</button>
        <button onclick="window.open('/memory','_blank')">记忆面板</button>
    </div>
    <div class="chat" id="chat"></div>
    <div class="input-bar">
        <input id="msg" placeholder="输入...">
        <button onclick="send()">发送</button>
    </div>
</div>
<script>
function send(){
    let m = document.getElementById('msg').value.trim();
    let d = document.getElementById('deep').checked;
    if(!m)return;
    chat.innerHTML += `<div class='msg user'>${m}</div>`;
    document.getElementById('msg').value='';
    fetch('/api/chat',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({msg:m, deep_mode:d})
    }).then(r=>r.json()).then(j=>{
        chat.innerHTML += `<div class='msg ai'>${j.reply}</div>`;
        chat.scrollTop=chat.scrollHeight;
    });
}
document.getElementById('msg').addEventListener('keypress',e=>{if(e.key==='Enter')send()});
</script>
</body>
</html>
"""

# ====================== 记忆查看/编辑面板 ======================
@app.get("/memory", response_class=HTMLResponse)
async def memory_panel(auth: str = Cookie(None)):
    if auth != "ok":
        return RedirectResponse("/login")
    mem = load_json("memory.json", {})
    items = ""
    for k, v in mem.items():
        items += f'''
        <div style="background:#2c2c2e;padding:8px;margin:6px;border-radius:8px">
            <input type="text" id="k{k}" value="{v}" style="width:70%;padding:6px;background:#333;color:#fff;border:none;border-radius:6px">
            <button onclick="edit('{k}')" style="background:#007aff;color:#fff;border:none;padding:6px 8px;border-radius:6px">保存</button>
            <button onclick="del('{k}')" style="background:#ff3b30;color:#fff;border:none;padding:6px 8px;border-radius:6px">删除</button>
        </div>
        '''
    return f"""
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>记忆面板</title></head>
    <body style="background:#121213;color:#fff;padding:10px">
        <h3>我的记忆</h3>
        <div style="margin:10px 0">
            <input id="newMem" placeholder="添加新记忆" style="width:70%;padding:8px;background:#2c2c2e;color:#fff;border:none;border-radius:8px">
            <button onclick="add()" style="background:#007aff;color:#fff;border:none;padding:8px 12px;border-radius:8px">添加</button>
        </div>
        <div>{items}</div>
        <script>
        function add(){{let t=document.getElementById('newMem').value;fetch('/api/memory/add?text='+t).then(()=>location.reload())}}
        function edit(k){{let t=document.getElementById('k'+k).value;fetch('/api/memory/edit?k='+k+'&v='+t).then(()=>location.reload())}}
        function del(k){{fetch('/api/memory/del?k='+k).then(()=>location.reload())}}
        </script>
    </body></html>
    """

@app.get("/api/memory/add")
async def add_mem(text: str):
    mem = load_json("memory.json", {})
    mem[str(len(mem)+1)] = text.strip()[:120]
    save_json("memory.json", mem)
    return {"ok":1}

@app.get("/api/memory/edit")
async def edit_mem(k: str, v: str):
    mem = load_json("memory.json", {})
    if k in mem: mem[k] = v.strip()
    save_json("memory.json", mem)
    return {"ok":1}

@app.get("/api/memory/del")
async def del_mem(k: str):
    mem = load_json("memory.json", {})
    if k in mem: del mem[k]
    save_json("memory.json", mem)
    return {"ok":1}

# ====================== 手表版+语音输入 ======================
@app.get("/watch", response_class=HTMLResponse)
async def watch_page(auth: str = Cookie(None)):
    if auth != "ok":
        return RedirectResponse("/login")
    return """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>WatchAI</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        html,body{background:#000;color:#fff;height:100vh;font-family:sans-serif}
        .wrap{height:100%;display:flex;flex-direction:column;padding:6px}
        #chat{flex:1;background:#111;border-radius:8px;padding:6px;font-size:12px;overflow-y:auto;margin-bottom:6px}
        .msg{margin:4px 0;padding:6px 8px;border-radius:10px;max-width:80%}
        .user{background:#007aff;margin-left:auto}
        .ai{background:#222;margin-right:auto}
        .input{display:flex;gap:6px}
        #msg{flex:1;padding:8px;border-radius:30px;border:none;background:#222;color:#fff;font-size:14px}
        button{padding:8px 10px;border-radius:30px;border:none;background:#007aff;color:#fff}
    </style>
</head>
<body>
<div class="wrap">
    <div id="chat"></div>
    <div class="input">
        <button id="voiceBtn">🎤</button>
        <input id="msg" placeholder="...">
        <button onclick="send()">发送</button>
    </div>
</div>
<script>
const vBtn = document.getElementById('voiceBtn');
const msgInput = document.getElementById('msg');
const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
recognition.lang = 'zh-CN';

vBtn.onclick = ()=>{recognition.start()};
recognition.onresult = (e)=>{msgInput.value = e.results[0][0].transcript};

function send(){
    let m = msgInput.value.trim();
    if(!m)return;
    fetch('/api/chat',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({msg:m, deep_mode:false})
    }).then(r=>r.json()).then(j=>{
        document.getElementById('chat').innerHTML += `<div class='msg user'>${m}</div><div class='msg ai'>${j.reply}</div>`;
        msgInput.value='';
    });
}
</script>
</body>
</html>
"""

# ====================== 聊天接口 ======================
class ChatReq(BaseModel):
    msg: str
    deep_mode: bool

@app.post("/api/chat")
async def api_chat(req: ChatReq, auth: str = Cookie(None)):
    if auth != "ok":
        return {"reply": "请先登录"}
    msg = req.msg
    deep = req.deep_mode
    reply = ai_chat(msg, deep)
    ctx = load_json("context.json", [])
    ctx.append({"user": msg, "ai": reply})
    save_json("context.json", ctx[-MAX_CONTEXT:])
    extract_memory(msg, reply)
    return {"reply": reply}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    return {"name": file.filename}

app = app