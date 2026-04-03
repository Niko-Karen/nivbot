function send() {
    let msgInput = document.getElementById("msg");
    let msg = msgInput.value.trim();
    let deep = document.getElementById("deep").checked;
    let chatBox = document.getElementById("chat");

    if (!msg) return;

    // 显示用户消息
    chatBox.innerHTML += `<div class="msg user">${msg}</div>`;
    msgInput.value = "";
    chatBox.scrollTop = chatBox.scrollHeight;

    // 发送请求（修复422错误）
    fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ msg: msg, deep_mode: deep })
    })
    .then(res => res.json())
    .then(data => {
        chatBox.innerHTML += `<div class="msg ai">${data.reply}</div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
    });
}

// 回车发送
document.getElementById("msg").addEventListener("keypress", function(e) {
    if (e.key === "Enter") send();
});