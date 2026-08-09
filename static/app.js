const STORAGE_KEY = "allan-ai-conversations-v1";
const agents = window.ALLAN_AGENTS || {};
let currentAgentId = "orchestrator";
let conversations = loadConversations();
let isLoading = false;
let isTtsEnabled = true;

const messagesEl = document.getElementById("messages");
const messageInput = document.getElementById("messageInput");
const chatForm = document.getElementById("chatForm");
const sendButton = document.getElementById("sendButton");
const micButton = document.getElementById("micButton");
const toggleTtsBtn = document.getElementById("toggleTtsBtn");
const typingEl = document.getElementById("typing");
const agentList = document.getElementById("agentList");
const currentAgentAvatar = document.getElementById("currentAgentAvatar");
const currentAgentName = document.getElementById("currentAgentName");
const currentAgentDescription = document.getElementById("currentAgentDescription");
const sidebar = document.getElementById("sidebar");
const overlay = document.getElementById("overlay");

// Web Speech API - Reconhecimento de Voz (Microfone)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let isRecording = false;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'pt-BR';

    recognition.onstart = () => {
        isRecording = true;
        micButton.classList.add("recording");
        messageInput.placeholder = "Ouvindo...";
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        messageInput.value = transcript;
        sendMessage();
    };

    recognition.onerror = (event) => {
        console.error("Erro na gravação:", event.error);
        stopRecording();
    };

    recognition.onend = () => {
        stopRecording();
    };
} else {
    micButton.style.display = "none";
}

function stopRecording() {
    isRecording = false;
    micButton.classList.remove("recording");
    messageInput.placeholder = "Digite ou fale uma mensagem...";
}

micButton.addEventListener("click", () => {
    if (!recognition) return;
    if (isRecording) {
        recognition.stop();
    } else {
        recognition.lang = currentAgentId === 'english' ? 'en-US' : 'pt-BR';
        recognition.start();
    }
});

// Sintetizador de Voz (Leitura da Resposta)
function speakText(text, lang = 'pt-BR') {
    if (!isTtsEnabled || !('speechSynthesis' in window)) return;
    
    window.speechSynthesis.cancel();
    const cleanText = text.replace(/[*#_]/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = lang;
    utterance.rate = 1.0;
    
    window.speechSynthesis.speak(utterance);
}

toggleTtsBtn.addEventListener("click", () => {
    isTtsEnabled = !isTtsEnabled;
    toggleTtsBtn.classList.toggle("off", !isTtsEnabled);
    toggleTtsBtn.textContent = isTtsEnabled ? "🔊 Voz On" : "🔇 Voz Off";
    if (!isTtsEnabled) window.speechSynthesis.cancel();
});

marked.setOptions({ breaks: true, gfm: true });
function renderMarkdown(text) { return DOMPurify.sanitize(marked.parse(text || "")); }

function loadConversations() {
    try { const saved = localStorage.getItem(STORAGE_KEY); return saved ? JSON.parse(saved) : {}; }
    catch { return {}; }
}
function saveConversations() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations)); } catch {}
}
function getConversation(agentId) {
    if (!conversations[agentId]) conversations[agentId] = [];
    return conversations[agentId];
}

function selectAgent(agentId) {
    if (!agents[agentId]) return;
    currentAgentId = agentId;
    window.speechSynthesis.cancel();
    updateAgentHeader();
    updateAgentList();
    renderMessages();
    closeSidebarMobile();
}

function updateAgentHeader() {
    const agent = agents[currentAgentId];
    currentAgentAvatar.textContent = agent.icon;
    currentAgentName.textContent = agent.name;
    currentAgentDescription.textContent = agent.description;
}

function updateAgentList() {
    document.querySelectorAll(".agent-item").forEach(item => {
        item.classList.toggle("active", item.dataset.agent === currentAgentId);
    });
}

function renderMessages() {
    const conversation = getConversation(currentAgentId);
    messagesEl.innerHTML = "";
    if (conversation.length === 0) {
        const agent = agents[currentAgentId];
        messagesEl.innerHTML = <div style="text-align:center; padding: 40px; color:#8696a0;"><h2> </h2><p></p></div>;
        return;
    }
    conversation.forEach(msg => renderMessage(msg.role, msg.content, msg.agent));
    scrollToBottom();
}

function renderMessage(role, content, agentData = null) {
    const row = document.createElement("div");
    row.className = message-row ;
    const msg = document.createElement("div");
    msg.className = message ;

    if (role === "assistant" && agentData) {
        const meta = document.createElement("div");
        meta.className = "message-meta";
        const langCode = currentAgentId === 'english' ? 'en-US' : 'pt-BR';
        meta.innerHTML = 
            <div><span></span> <span></span></div>
            <button class="play-audio-btn" onclick="speakText(\${escapeQuote(content)}\, '')" title="Ouvir Resposta">🔊</button>
        ;
        msg.appendChild(meta);
    }

    const contentEl = document.createElement("div");
    contentEl.className = "message-content";
    contentEl.innerHTML = renderMarkdown(content);
    msg.appendChild(contentEl);

    const time = document.createElement("span");
    time.className = "message-time";
    time.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    msg.appendChild(time);

    row.appendChild(msg);
    messagesEl.appendChild(row);
}

function escapeQuote(str) {
    return (str || '').replace(//g, '\\').replace(/"/g, '&quot;');
}

async function sendMessage() {
    if (isLoading) return;
    const text = messageInput.value.trim();
    if (!text) return;

    const conversation = getConversation(currentAgentId);
    conversation.push({ role: "user", content: text, timestamp: Date.now() });
    saveConversations();
    messageInput.value = "";
    renderMessages();

    isLoading = true;
    setLoading(true);

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ agent_id: currentAgentId, messages: conversation.map(m => ({ role: m.role, content: m.content })) })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Erro de API");

        conversation.push({ role: "assistant", content: data.content, agent: data.agent, timestamp: Date.now() });
        saveConversations();
        renderMessages();

        const langCode = currentAgentId === 'english' ? 'en-US' : 'pt-BR';
        speakText(data.content, langCode);

    } catch (err) {
        conversation.push({ role: "assistant", content: **Erro:** , agent: { name: "Allan AI", icon: "⚠️" } });
        saveConversations();
        renderMessages();
    } finally {
        isLoading = false;
        setLoading(false);
    }
}

function setLoading(val) {
    typingEl.classList.toggle("hidden", !val);
    sendButton.disabled = val;
    messageInput.disabled = val;
    if (val) scrollToBottom();
}

function scrollToBottom() { messagesEl.scrollTop = messagesEl.scrollHeight; }

messageInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

chatForm.addEventListener("submit", e => { e.preventDefault(); sendMessage(); });
agentList.addEventListener("click", e => {
    const btn = e.target.closest(".agent-item");
    if (btn) selectAgent(btn.dataset.agent);
});

function closeSidebarMobile() { sidebar.classList.remove("open"); overlay.classList.remove("open"); }
document.getElementById("openSidebar").addEventListener("click", () => { sidebar.classList.add("open"); overlay.classList.add("open"); });
document.getElementById("closeSidebar").addEventListener("click", closeSidebarMobile);
overlay.addEventListener("click", closeSidebarMobile);

selectAgent("orchestrator");