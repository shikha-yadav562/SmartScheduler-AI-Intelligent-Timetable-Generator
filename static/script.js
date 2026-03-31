


/**
 * SmartSchedule AI — OR-Tools CP-SAT Edition
 * All fields always visible — no hidden rows, no display:none toggles
 */
"use strict";

/** * TOP OF FILE: System-Level Theme Injection 
 */
// 🛡️ SHIELD: Hide the page immediately
document.documentElement.style.visibility = 'hidden';

(function syncTheme() {
    const saved = localStorage.getItem("ss-theme") || "light";
    document.documentElement.dataset.theme = saved;
})();

let S = {
  type: "college", 
  subjects: [], 
  timetable: null, 
  config: null,
  chatHist: [], 
  nextId: 1,
};

const PALETTE = [
  "#4f46e5","#0891b2","#dc2626","#059669","#d97706",
  "#7c3aed","#0284c7","#db2777","#16a34a","#9333ea",
  "#ea580c","#0d9488",
];

// ── Theme ──────────────────────────────────────────────────────────────────────

function saveToBrowser() {
    localStorage.setItem("ss_app_state", JSON.stringify(S));
}

function loadFromBrowser() {
    const saved = localStorage.getItem("ss_app_state");
    if (saved) {
        const parsed = JSON.parse(saved);
        // Merge saved data into S
        Object.assign(S, parsed);
        
        // Re-render subjects so they appear on refresh
        const list = document.getElementById("subj-list");
        list.innerHTML = ""; // Clear defaults
        S.subjects.forEach(s => {
            const el = document.createElement("div");
            el.id = `sc-${s.id}`; 
            el.className = "subj-card fadeup";
            el.innerHTML = buildCardHTML(s);
            list.appendChild(el);
            attachCardEvents(el, s.id);
        });
        
        // Restore timetable if it exists
        if (S.timetable) {
            renderTT(S.timetable, S.config, "Restored from session.", "");
            enableActs(true);
        }
        syncCount();

        document.documentElement.dataset.theme = S.theme || "light";
    }
}

function attachCardEvents(el, id) {
    el.querySelectorAll("input, select").forEach(i => {
        i.addEventListener("change", () => syncCard(id));
        i.addEventListener("input", () => syncCard(id));
        // Also save to browser whenever an input changes
        i.addEventListener("change", saveToBrowser); 
    });
}

function setTheme(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem("ss-theme", t);
  if (S) S.theme = t; // Sync with state
  saveToBrowser();
}

// ── Init ───────────────────────────────────────────────────────────────────────
// ── Init: The Traffic Controller ──
document.addEventListener("DOMContentLoaded", () => {
    // 1. Load from Browser first
    loadFromBrowser();

    // 2. ONLY if no subjects exist in memory, load the defaults
    if (S.subjects.length === 0) {
        console.log("Memory empty, loading presets...");
        loadPresets(S.type || "college");
    } else {
        console.log("Memory found, subjects restored.");
    }

    // 3. Setup UI listeners
    document.querySelectorAll(".day-chip").forEach(c => 
        c.addEventListener("click", () => c.classList.toggle("on"))
    );
    
    // 4. Show the page (if you used the 'hidden' shield)
    document.documentElement.style.visibility = 'visible';
});
// ── Tabs ───────────────────────────────────────────────────────────────────────
function switchTab(t){
  document.getElementById("pane-setup").style.display=t==="setup"?"flex":"none";
  document.getElementById("pane-chat").style.display =t==="chat" ?"flex":"none";
  document.getElementById("t-setup").classList.toggle("on",t==="setup");
  document.getElementById("t-chat").classList.toggle("on",t==="chat");
  if(t==="chat")document.getElementById("chat-in").focus();
}

// ── Type ───────────────────────────────────────────────────────────────────────
function setType(t){
  S.type=t;
  document.querySelectorAll(".type-chip").forEach(c=>c.classList.toggle("on",c.dataset.type===t));
  document.getElementById("subj-section-title").textContent =
    t==="corporate"?"Sessions / Meetings":"Subjects / Sessions";

  loadPresets(t);
}



function setMF(){
  document.querySelectorAll(".day-chip").forEach(c=>
    c.classList.toggle("on",["Monday","Tuesday","Wednesday","Thursday","Friday"].includes(c.dataset.day)));
}

// ── Presets ────────────────────────────────────────────────────────────────────
async function loadPresets(type){
  try{
    const r=await fetch(`/presets?type=${type}`);
    const d=await r.json();
    clearSubjects();
    (d.subjects||[]).forEach(s=>addCard(s));
  }catch{ showToast("⚠ Server not reachable."); }
}

function clearSubjects(){
  S.subjects=[]; S.nextId=1;
  document.getElementById("subj-list").innerHTML="";
  syncCount();
}

// ── Add subject card — ALL FIELDS ALWAYS VISIBLE ──────────────────────────────
function addCard(data={}){
  const id   =S.nextId++;
  const color=PALETTE[(id-1)%PALETTE.length];
  const s={
    id, color,
    name:           data.name||"",
    teacher:        data.teacher||data.host||"",
    hours_per_week: data.hours_per_week||3,
    is_lab:         data.is_lab||false,
    lab_duration:   data.lab_duration||2,
    credits:        data.credits||"",
    room:           data.room||data.location||"",
    department:     data.department||"",
    class_group:    data.class_group||"",
    is_activity:    data.is_activity||false,
    duration_mins:  data.duration_mins||"",
    session_type:   data.session_type||data.meeting_type||"",
    location:       data.location||data.room||"",
  };
  S.subjects.push(s);

  const list=document.getElementById("subj-list");
  const el=document.createElement("div");
  el.id=`sc-${id}`; el.className="subj-card fadeup";
  el.innerHTML=buildCardHTML(s);
  list.appendChild(el);

  // Sync on every input/change — no toggles, no hiding
  el.querySelectorAll("input,select").forEach(i=>{
    i.addEventListener("change",()=>syncCard(id));
    i.addEventListener("input", ()=>syncCard(id));
  });
  syncCount();
  saveToBrowser();
}

// ── Build card HTML — ALL FIELDS RENDERED, NOTHING HIDDEN ─────────────────────
function buildCardHTML(s){
  const isCorp=S.type==="corporate";
  const isSchool=S.type==="school";
  const isCollege=S.type==="college" || S.type==="custom";

  const subjLabel  = isCorp ? "Session Name"     : "Subject Name";
  const teachLabel = isCorp ? "Host / Organiser"  : isSchool ? "Teacher" : "Professor / Teacher";
  const labLabel   = isCorp ? "Multi-slot session": "Lab Session";
  const durLabel   = isCorp ? "Lab / Multi Slots" : "Lab Duration";

  // Row 1: Subject + Teacher + h/wk + delete
  let h=`
  <div class="s-bar" style="background:${s.color};"></div>
  <div class="s-body">

    <div class="s-row-3">
      <div class="field">
        <label>${subjLabel}</label>
        <input class="inp sc-name" value="${esc(s.name)}" placeholder="${subjLabel}" style="font-weight:600;"/>
      </div>
      <div class="field">
        <label>${teachLabel}</label>
        <input class="inp sc-teacher" value="${esc(s.teacher)}" placeholder="${teachLabel}"/>
      </div>
      <div class="field">
        <label>Hours / Week</label>
        <input class="inp sc-hours" type="number" min="1" max="20" value="${s.hours_per_week}" style="text-align:center;"/>
      </div>
      <button class="del" onclick="removeSubj(${s.id})" title="Remove subject">✕</button>
    </div>`;

  // Row 2a: College-specific fields
  if(isCollege){
    h+=`
    <div class="s-row-3">
      <div class="field">
        <label>Credits</label>
        <input class="inp sc-credits" type="number" min="0" max="10" value="${esc(s.credits)}" placeholder="e.g. 4"/>
      </div>
      <div class="field">
        <label>Room / Venue</label>
        <input class="inp sc-room" value="${esc(s.room)}" placeholder="e.g. A-101"/>
      </div>
      <div class="field">
        <label>Department</label>
        <input class="inp sc-dept" value="${esc(s.department)}" placeholder="e.g. Science"/>
      </div>
    </div>`;
  }

  // Row 2b: School-specific fields
  if(isSchool){
    h+=`
    <div class="s-row-3">
      <div class="field">
        <label>Room / Space</label>
        <input class="inp sc-room" value="${esc(s.room)}" placeholder="e.g. Room 1"/>
      </div>
      <div class="field">
        <label>Class Group</label>
        <input class="inp sc-cgroup" value="${esc(s.class_group)}" placeholder="e.g. Grade 10-A"/>
      </div>
      <div class="field">
        <label>Activity Period</label>
        <select class="inp sc-activity">
          <option value="false" ${!s.is_activity?"selected":""}>Regular Period</option>
          <option value="true"  ${s.is_activity ?"selected":""}>PT / Activity</option>
        </select>
      </div>
    </div>`;
  }

  // Row 2c: Corporate-specific fields
  if(isCorp){
    h+=`
    <div class="s-row-3">
      <div class="field">
        <label>Duration (mins)</label>
        <input class="inp sc-dur" type="number" min="5" max="480" step="5" value="${esc(s.duration_mins)||30}" placeholder="e.g. 30"/>
      </div>
      <div class="field">
        <label>Location / Room</label>
        <input class="inp sc-room" value="${esc(s.location||s.room)}" placeholder="e.g. Virtual"/>
      </div>
      <div class="field">
        <label>Session Type</label>
        <select class="inp sc-mtype">
          <option value="">Select type…</option>
          ${["standup","planning","review","sync","workshop","one_on_one","training","retrospective","brainstorm","demo"]
            .map(v=>`<option value="${v}" ${(s.session_type||s.meeting_type)===v?"selected":""}>${v.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase())}</option>`).join("")}
        </select>
      </div>
    </div>`;
  }

  // Row 3: Lab / Multi-slot — ALWAYS VISIBLE, no toggle hiding
  h+=`
    <div class="s-row-lab">
      <div class="field" style="flex:0 0 auto;">
        <label>${labLabel}</label>
        <select class="inp sc-lab">
          <option value="false" ${!s.is_lab?"selected":""}>No</option>
          <option value="true"  ${ s.is_lab?"selected":""}>Yes</option>
        </select>
      </div>
      <div class="field" style="flex:0 0 auto;">
        <label>${durLabel}</label>
        <input class="inp sc-lab-dur" type="number" min="2" max="6" value="${s.lab_duration}" style="width:80px;text-align:center;" title="Number of consecutive slots needed"/>
      </div>
      <div class="field" style="flex:1;">
        <label>Notes / Description</label>
        <input class="inp sc-notes" value="${esc(s.notes||'')}" placeholder="Optional notes…"/>
      </div>
    </div>
  </div>`;

  return h;
}

function syncCard(id){
  const el=document.getElementById(`sc-${id}`); if(!el) return;
  const s=S.subjects.find(x=>x.id===id); if(!s) return;

  s.name           = el.querySelector(".sc-name")?.value.trim()    || "";
  s.teacher        = el.querySelector(".sc-teacher")?.value.trim() || "";
  s.hours_per_week = parseInt(el.querySelector(".sc-hours")?.value) || 3;
  s.is_lab         = el.querySelector(".sc-lab")?.value === "true";
  s.lab_duration   = parseInt(el.querySelector(".sc-lab-dur")?.value) || 2;
  s.credits        = el.querySelector(".sc-credits")?.value         || "";
  s.room           = el.querySelector(".sc-room")?.value.trim()     || "";
  s.department     = el.querySelector(".sc-dept")?.value.trim()     || "";
  s.class_group    = el.querySelector(".sc-cgroup")?.value.trim()   || "";
  s.is_activity    = el.querySelector(".sc-activity")?.value === "true";
  s.duration_mins  = el.querySelector(".sc-dur")?.value             || "";
  s.session_type   = el.querySelector(".sc-mtype")?.value           || "";
  s.location       = el.querySelector(".sc-room")?.value.trim()     || "";
  s.notes          = el.querySelector(".sc-notes")?.value.trim()    || "";
}

function removeSubj(id) {
  S.subjects = S.subjects.filter(s => s.id !== id);
  const el = document.getElementById(`sc-${id}`);
  if (el) { 
      el.style.opacity = "0"; 
      el.style.transform = "translateX(-8px)"; 
      setTimeout(() => {
          el.remove();
          saveToBrowser(); // CRITICAL: Save after deleting
      }, 200); 
  }
  syncCount();
}

function syncCount(){ document.getElementById("subj-count").textContent=S.subjects.length; }
function esc(s){ return String(s??"").replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;"); }

// ── AI Fill ────────────────────────────────────────────────────────────────────
async function aiSuggest(){
  const btn=document.getElementById("btn-ai");
  btn.disabled=true; btn.textContent="⏳ Loading…";
  try{
    const r=await fetch("/suggest",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({type:S.type})});
    const d=await r.json();
    clearSubjects();
    (d.subjects||[]).forEach(s=>addCard(s));
    showToast("✨ AI subjects loaded!");
  }catch{ showToast("AI fill failed."); loadPresets(S.type); }
  finally{ btn.disabled=false; btn.textContent="✨ AI Fill"; }
}

// ── Generate ───────────────────────────────────────────────────────────────────
function getSubjects(){
  S.subjects.forEach(s=>{const el=document.getElementById(`sc-${s.id}`);if(el)syncCard(s.id);});
  return S.subjects.filter(s=>s.name.trim());
}
function getSettings(){
  return{
    start_time:    document.getElementById("s-start").value,
    end_time:      document.getElementById("s-end").value,
    slot_duration: parseInt(document.getElementById("s-slot").value),
    break_start:   document.getElementById("s-brk").value,
    break_duration:parseInt(document.getElementById("s-brk-dur").value),
    days:[...document.querySelectorAll(".day-chip.on")].map(c=>c.dataset.day),
  };
}

async function generate(){
  const subjects=getSubjects();
  if(!subjects.length){ showToast("⚠ Add at least one subject."); return; }
  const settings=getSettings();
  if(!settings.days.length){ showToast("⚠ Select at least one working day."); return; }

  setGL(true);
  try{
    const r=await fetch("/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...settings,subjects})});
    const d=await r.json();
    if(!r.ok){ showToast("⚠ "+(d.error||"Failed.")); return; }
    S.timetable=d.timetable; S.config=d.config;
    renderTT(d.timetable, d.config, d.explanation, d.solver);
    enableActs(true);
    showToast(`✅ Generated! Solver: ${d.solver||"OR-Tools"}`);
  }catch{ showToast("⚠ Server error — is Flask running?"); }
  finally{ setGL(false); }
}

function setGL(on){
  document.getElementById("btn-gen").disabled=on;
  document.getElementById("gen-spin").style.display=on?"inline-block":"none";
}
function enableActs(on){
  document.querySelectorAll(".action-btn").forEach(b=>b.disabled=!on);
  document.getElementById("livepill").classList.toggle("on",on);
}

// ── Render timetable ───────────────────────────────────────────────────────────
function hexA(hex,a){
  if(!hex||hex.startsWith("var")) return `rgba(79,70,229,${a})`;
  try{const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);return`rgba(${r},${g},${b},${a})`;}
  catch{ return `rgba(79,70,229,${a})`; }
}

function renderTT(tt, config, expl, solverName){
  const{days,time_slots:slots}=config;
  let sessions=0,labs=0,extras=0; const ts=new Set();
  for(const d of days) for(const s of slots){
    const e=tt[d]?.[s]; if(!e||typeof e!=="object") continue;
    if(e.type==="session") sessions++;
    if(e.type==="lab")     labs++;
    if(e.type==="extra")   extras++;
    if(e.teacher&&!["","__break__"].includes(e.teacher)) ts.add(e.teacher);
  }

  // Solver badge
  const solverBadge = solverName
    ? `<span style="background:rgba(5,150,105,.12);border:1px solid rgba(5,150,105,.3);color:var(--grn);padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap;">⚙ ${solverName}</span>`
    : "";

  document.getElementById("tt-stats").innerHTML=
    [["Sessions",sessions,"var(--acc)"],["Labs",labs,"var(--tl)"],["Extras",extras,"var(--amb)"],
     ["Teachers",ts.size,"var(--grn)"],["Days",days.length,"var(--vio)"]]
    .map(([l,v,c])=>`<div class="stat-pill"><span class="sv" style="color:${c};">${v}</span><span class="sl">${l}</span></div>`)
    .join("") + solverBadge;

  // Legend
  const cm={};
  for(const d of days) for(const s of slots){
    const e=tt[d]?.[s];
    if(e&&e.subject&&!e.subject.startsWith("__")&&e.type!=="holiday") cm[e.subject]=e.color||"var(--acc)";
  }
  document.getElementById("tt-legend").innerHTML=
    Object.entries(cm).map(([n,c])=>
      `<div style="display:flex;align-items:center;gap:5px;">
        <div style="width:9px;height:9px;border-radius:3px;background:${c};flex-shrink:0;"></div>
        <span style="font-size:11.5px;color:var(--t2);">${esc(n)}</span>
      </div>`).join("");

  // Table
  const skip={};
  let html="<thead><tr><th>Time</th>"+days.map(d=>`<th>${d}</th>`).join("")+"</tr></thead><tbody>";
  for(const slot of slots){
    html+="<tr>";
    html+=`<td style="padding:9px 8px;text-align:center;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--t3);background:var(--surf);border-radius:8px;white-space:nowrap;">${slot}</td>`;
    for(const day of days){
      const key=`${day}|${slot}`; if(skip[key]) continue;
      html+=buildCell(tt[day]?.[slot],day,slot,slots,skip);
    }
    html+="</tr>";
  }
  html+="</tbody>";
  document.getElementById("tt-table").innerHTML=html;
  document.getElementById("explanation").textContent=expl||"";
  document.getElementById("empty").style.display="none";
  const card=document.getElementById("tt-card"); card.style.display="flex";

  // Populate modals
  const teachers=[...new Set(S.subjects.map(s=>s.teacher||s.host).filter(Boolean))];
  document.getElementById("m-l-teacher").innerHTML=
    teachers.map(t=>`<option value="${esc(t)}">${esc(t)}</option>`).join("")||"<option>No teachers</option>";
  ["m-l-days","m-h-days"].forEach(id=>{
    document.getElementById(id).innerHTML=days.map(d=>`<option value="${d}">${d}</option>`).join("");
  });
  document.getElementById("m-e-day").innerHTML =days.map(d=>`<option value="${d}">${d}</option>`).join("");
  document.getElementById("m-e-slot").innerHTML=
    `<option value="">Auto</option>`+slots.map(s=>`<option value="${s}">${s}</option>`).join("");
}

function buildCell(e,day,slot,slots,skip){
  if(!e||typeof e!=="object") return`<td class="c-empty">—</td>`;
  const{type,subject,teacher,color="#4f46e5",span=1,substituted,orig_teacher,room=""}=e;
  if(type==="break")    return`<td class="c-break">🍽 Lunch Break</td>`;
  if(type==="holiday")  return`<td class="c-holiday">🏖 Holiday</td>`;
  if(type==="continuation") return"";
  const bg=hexA(color,.1),brd=hexA(color,.28);
  const sub=substituted?`<div class="sub-badge">SUB · was ${esc(orig_teacher||"")}</div>`:"";
  const ext=type==="extra"?`<div class="extra-badge">EXTRA</div>`:"";
  const rm=room?`<div class="cell-room">${esc(room)}</div>`:"";
  if(type==="lab"&&span>1){
    const si=slots.indexOf(slot);
    for(let k=1;k<span;k++){ if(si+k<slots.length) skip[`${day}|${slots[si+k]}`]=true; }
    return`<td class="c-lab" rowspan="${span}" style="background:${bg};border:1px solid ${brd};vertical-align:top;">
      <div class="lab-badge">LAB · ${span}×</div>
      <div class="cell-subj" style="color:${color};">${esc(subject)}</div>
      <div class="cell-teacher">${esc(teacher)}</div>
      ${rm}${sub}
    </td>`;
  }
  return`<td class="c-session" style="background:${bg};border:1px solid ${brd};">
    <div class="cell-subj" style="color:${color};">${esc(subject)}</div>
    <div class="cell-teacher">${esc(teacher)}</div>
    ${rm}${ext}${sub}
  </td>`;
}

// ── Modals ─────────────────────────────────────────────────────────────────────
function openModal(type){
  if(!S.timetable){ showToast("⚠ Generate a timetable first."); return; }
  const titles={leave:"✋ Apply Leave",holiday:"🏖 Mark Holiday",extra:"⚡ Add Extra Session"};
  document.getElementById("modal-title").textContent=titles[type]||type;
  document.querySelectorAll(".m-form").forEach(f=>f.style.display="none");
  const f=document.getElementById(`m-${type}`); if(f) f.style.display="flex";
  document.getElementById("modal-bg").classList.add("open");
}
function closeModal(e){
  if(e&&e.target!==document.getElementById("modal-bg")) return;
  document.getElementById("modal-bg").classList.remove("open");
}
document.addEventListener("keydown",e=>{
  if(e.key==="Escape"){
    document.getElementById("modal-bg").classList.remove("open");
    document.getElementById("conflict-panel").classList.remove("open");
  }
});

async function submitUpdate(action){
  let payload={action};
  if(action==="leave"){
    payload.teacher=document.getElementById("m-l-teacher").value;
    payload.days=[...document.getElementById("m-l-days").selectedOptions].map(o=>o.value);
    payload.replacement=document.getElementById("m-l-repl").value.trim()||"Substitute";
    if(!payload.teacher||!payload.days.length){ showToast("⚠ Pick teacher and day(s)."); return; }
  }else if(action==="holiday"){
    payload.days=[...document.getElementById("m-h-days").selectedOptions].map(o=>o.value);
    if(!payload.days.length){ showToast("⚠ Select at least one day."); return; }
  }else if(action==="extra"){
    payload.subject =document.getElementById("m-e-subj").value.trim()   ||"Extra Session";
    payload.teacher =document.getElementById("m-e-teacher").value.trim()||"TBD";
    payload.day     =document.getElementById("m-e-day").value;
    payload.slot    =document.getElementById("m-e-slot").value;
  }
  try{
    const r=await fetch("/update",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const d=await r.json();
    if(!r.ok){ showToast("⚠ "+(d.error||"Failed.")); return; }
    S.timetable=d.timetable;
    renderTT(d.timetable,S.config,d.explanation,"");
    showToast(d.message||"✅ Updated!");
    if(action==="leave"&&d.log?.length) showConflictLog(d.log);
    document.getElementById("modal-bg").classList.remove("open");
  }catch{ showToast("⚠ Server error."); }
}

function showConflictLog(log){
  document.getElementById("conflict-log").innerHTML=log.map(l=>`
    <div style="background:var(--surf);border:1px solid var(--bd);border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:4px;">
      <div style="display:flex;align-items:center;gap:6px;">
        <div style="width:7px;height:7px;border-radius:50%;background:${l.ok?"var(--grn)":"var(--red)"};flex-shrink:0;"></div>
        <span style="font-size:12px;font-weight:600;color:var(--th);">${esc(l.day)} · ${esc(l.slot)}</span>
      </div>
      <div style="font-size:12px;color:var(--t2);">${esc(l.subject)}</div>
      <div style="font-size:11.5px;color:${l.ok?"var(--grn)":"var(--red)"};">${l.ok?`✓ → <strong>${esc(l.assigned)}</strong>`:"✗ Unassigned"}</div>
    </div>`).join("");
  document.getElementById("conflict-panel").classList.add("open");
}

// ── Export ─────────────────────────────────────────────────────────────────────
function exportExcel(){
  if(!S.timetable){ showToast("⚠ Generate first."); return; }
  showToast("📊 Preparing…"); window.location.href="/export-excel";
}
async function doShot(){
  if(!S.timetable){ showToast("⚠ Generate first."); return; }
  showToast("📸 Capturing…");
  try{
    const dark=document.documentElement.dataset.theme==="dark";
    const c=await html2canvas(document.getElementById("tt-card"),{backgroundColor:dark?"#0d0d1c":"#f0f4f9",scale:2,useCORS:true});
    const a=document.createElement("a"); a.download=`SmartSchedule_${Date.now()}.png`; a.href=c.toDataURL("image/png"); a.click();
    showToast("✅ Screenshot saved!");
  }catch(e){ showToast("⚠ "+e.message); }
}

// ── Chat ───────────────────────────────────────────────────────────────────────
function addBub(role,text){
  const log=document.getElementById("chat-log");
  const d=document.createElement("div"); d.className=`bub bub-${role} fadeup`;
  d.innerHTML=text.replace(/\*\*(.*?)\*\*/g,"<strong>$1</strong>").replace(/\n/g,"<br/>");
  log.appendChild(d); log.scrollTop=log.scrollHeight;
}
async function sendMsg(){
  const inp=document.getElementById("chat-in"); const msg=inp.value.trim(); if(!msg) return;
  inp.value=""; addBub("user",msg); S.chatHist.push({role:"user",content:msg});
  document.getElementById("typing").style.display="flex";
  try{
    const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:msg,history:S.chatHist.slice(-10)})});
    const d=await r.json();
    document.getElementById("typing").style.display="none";
    await new Promise(x=>setTimeout(x,180));
    addBub("ai",d.reply||"Sorry, couldn't process that.");
    S.chatHist.push({role:"assistant",content:d.reply||""});
  }catch{
    document.getElementById("typing").style.display="none";
    addBub("ai","⚠ Server not reachable.");
  }
}
function sendQ(q){ document.getElementById("chat-in").value=q; switchTab("chat"); sendMsg(); }

// ── Toast ──────────────────────────────────────────────────────────────────────
let _t=null;
function showToast(msg,ms=2800){
  const el=document.getElementById("toast"); el.textContent=msg; el.classList.add("show");
  clearTimeout(_t); _t=setTimeout(()=>el.classList.remove("show"),ms);
}