const $ = (id) => document.getElementById(id);
let token = sessionStorage.getItem("rog_access_token") || "";
let activeRequest = null;
let activeAgent = "orchestrator";

function showAuthenticated(value) {
  $("login").hidden = value; $("chat").hidden = !value; $("logout").hidden = !value;
}
function addMessage(role, text) {
  const item = document.createElement("div"); item.className = `message ${role}`; item.textContent = text; $("messages").append(item); item.scrollIntoView({behavior:"smooth"}); return item;
}
async function api(path, options={}) {
  const headers = {"Content-Type":"application/json", ...(options.headers||{})}; if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(path, {...options, headers, cache:"no-store"});
}
async function loadAgents() {
  const response = await api("/v1/agents"); if (!response.ok) { logout(); return; }
  const data = await response.json(); $("agent").replaceChildren(...data.agents.map(agent => { const option=document.createElement("option"); option.value=agent.id; option.textContent=agent.name; return option; }));
}
async function login() {
  $("loginError").textContent=""; const response = await api("/v1/auth/login", {method:"POST", body:JSON.stringify({profile:$("profile").value,password:$("password").value})});
  if (!response.ok) { $("loginError").textContent="Não foi possível entrar."; return; }
  const data=await response.json(); token=data.access_token; sessionStorage.setItem("rog_access_token",token); sessionStorage.setItem("rog_refresh_token",data.refresh_token||""); $("password").value=""; showAuthenticated(true); await loadAgents();
}
function logout() { token=""; activeRequest=null; sessionStorage.clear(); $("messages").replaceChildren(); showAuthenticated(false); }

async function sendMessage(event) {
  event.preventDefault(); const text=$("message").value.trim(); if (!text) return; activeAgent=$("agent").value; addMessage("user",text); $("message").value=""; $("send").disabled=true; $("cancel").hidden=false;
  const assistant=addMessage("assistant","");
  try {
    const response=await api("/v1/chat/stream",{method:"POST",body:JSON.stringify({agent_id:activeAgent,message:text,history:[]})}); if(!response.ok) throw new Error("request failed");
    const reader=response.body.getReader(), decoder=new TextDecoder(); let buffer="";
    while(true){const {value,done}=await reader.read(); if(done)break; buffer+=decoder.decode(value,{stream:true}); const blocks=buffer.split("\n\n"); buffer=blocks.pop(); for(const block of blocks){const eventLine=block.split("\n").find(line=>line.startsWith("event:")); const dataLine=block.split("\n").find(line=>line.startsWith("data:")); if(!eventLine||!dataLine)continue; const kind=eventLine.slice(6).trim(),data=JSON.parse(dataLine.slice(5)); if(kind==="start")activeRequest=data.request_id; if(kind==="token")assistant.textContent+=data.text; if(kind==="done"&&!assistant.textContent)assistant.textContent=data.answer; if(kind==="error")assistant.textContent="A geração falhou. Tente novamente."; }}
  } catch { assistant.textContent="Não foi possível concluir a resposta."; }
  finally { activeRequest=null; $("send").disabled=false; $("cancel").hidden=true; }
}
async function cancel(){if(activeRequest)await api(`/v1/chat/${activeRequest}?agent_id=${encodeURIComponent(activeAgent)}`,{method:"DELETE"});}

$("loginButton").addEventListener("click",login); $("logout").addEventListener("click",logout); $("composer").addEventListener("submit",sendMessage); $("cancel").addEventListener("click",cancel);
if("serviceWorker" in navigator) navigator.serviceWorker.register("./sw.js"); showAuthenticated(Boolean(token)); if(token)loadAgents();
