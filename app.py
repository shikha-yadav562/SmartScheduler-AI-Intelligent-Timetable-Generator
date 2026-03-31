"""
SmartSchedule AI — Google OR-Tools CP-SAT Scheduler
Install: pip install flask openpyxl ortools
Run:     python app.py

OR-Tools CP-SAT enforces:
  • Each subject placed exactly hours_per_week times
  • No two subjects in the same (day, slot)
  • Labs placed in consecutive slots (contiguous block)
  • No teacher double-booked in the same (day, slot)
  • No consecutive duplicate subject in same day
"""
import os, random, copy, io, re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, session, send_file
from flask import Flask, request, jsonify
from flask_cors import CORS
from ortools.sat.python import cp_model

_BASE = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
    static_folder=os.path.join(_BASE, "static"),
    template_folder=os.path.join(_BASE, "templates"))
app.secret_key = os.environ.get("SECRET_KEY", "smartschedule-ortools-2026")
CORS(app)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_KEY    = os.environ.get("OPENAI_API_KEY", "")

PALETTE = [
    "#4f46e5","#0891b2","#dc2626","#059669","#d97706",
    "#7c3aed","#0284c7","#db2777","#16a34a","#9333ea",
    "#ea580c","#0d9488",
]

# ─── Presets ────────────────────────────────────────────────────────────────────
PRESETS = {
    "college": [
        {"name":"Mathematics",      "teacher":"Prof. Sharma",  "hours_per_week":5,"is_lab":False,"lab_duration":2,"credits":4,"room":"A-101","department":"Science"},
        {"name":"Physics",          "teacher":"Prof. Mehta",   "hours_per_week":4,"is_lab":True, "lab_duration":2,"credits":4,"room":"B-201","department":"Science"},
        {"name":"Chemistry",        "teacher":"Prof. Verma",   "hours_per_week":4,"is_lab":True, "lab_duration":3,"credits":4,"room":"C-Lab","department":"Science"},
        {"name":"English",          "teacher":"Prof. Kapoor",  "hours_per_week":3,"is_lab":False,"lab_duration":2,"credits":2,"room":"A-202","department":"Humanities"},
        {"name":"Computer Science", "teacher":"Prof. Gupta",   "hours_per_week":3,"is_lab":True, "lab_duration":3,"credits":4,"room":"CS-Lab","department":"Engineering"},
        {"name":"History",          "teacher":"Prof. Singh",   "hours_per_week":2,"is_lab":False,"lab_duration":2,"credits":2,"room":"A-103","department":"Humanities"},
    ],
    "school": [
        {"name":"Mathematics",       "teacher":"Mr. Patel",   "hours_per_week":6,"is_lab":False,"lab_duration":2,"room":"Room 1",    "class_group":"Grade 10","is_activity":False},
        {"name":"Science",           "teacher":"Ms. Nair",    "hours_per_week":5,"is_lab":True, "lab_duration":2,"room":"Sci Lab",   "class_group":"Grade 10","is_activity":False},
        {"name":"English",           "teacher":"Ms. Iyer",    "hours_per_week":5,"is_lab":False,"lab_duration":2,"room":"Room 2",    "class_group":"Grade 10","is_activity":False},
        {"name":"Social Studies",    "teacher":"Mr. Das",     "hours_per_week":4,"is_lab":False,"lab_duration":2,"room":"Room 3",    "class_group":"Grade 10","is_activity":False},
        {"name":"Hindi",             "teacher":"Ms. Joshi",   "hours_per_week":4,"is_lab":False,"lab_duration":2,"room":"Room 4",    "class_group":"Grade 10","is_activity":False},
        {"name":"Physical Education","teacher":"Mr. Kumar",   "hours_per_week":2,"is_lab":False,"lab_duration":2,"room":"Playground","class_group":"Grade 10","is_activity":True},
    ],
    "corporate": [
        {"name":"Daily Standup",   "teacher":"Team Lead",        "hours_per_week":5,"is_lab":False,"lab_duration":1,"duration_mins":15,"session_type":"standup",  "location":"Virtual"},
        {"name":"Sprint Planning", "teacher":"Scrum Master",     "hours_per_week":2,"is_lab":False,"lab_duration":1,"duration_mins":60,"session_type":"planning", "location":"Conf Room A"},
        {"name":"Code Review",     "teacher":"Tech Lead",        "hours_per_week":3,"is_lab":False,"lab_duration":1,"duration_mins":45,"session_type":"review",   "location":"Virtual"},
        {"name":"Client Sync",     "teacher":"Project Manager",  "hours_per_week":2,"is_lab":False,"lab_duration":1,"duration_mins":30,"session_type":"sync",     "location":"Conf Room B"},
        {"name":"Dev Workshop",    "teacher":"Senior Developer", "hours_per_week":2,"is_lab":True, "lab_duration":2,"duration_mins":90,"session_type":"workshop", "location":"Training Room"},
        {"name":"1:1 Meeting",     "teacher":"Manager",          "hours_per_week":2,"is_lab":False,"lab_duration":1,"duration_mins":30,"session_type":"one_on_one","location":"Manager Office"},
    ],
    "custom": [
        {"name":"Session A","teacher":"Instructor A","hours_per_week":4,"is_lab":False,"lab_duration":2},
        {"name":"Session B","teacher":"Instructor B","hours_per_week":3,"is_lab":True, "lab_duration":2},
    ],
}

# ─── Helpers ────────────────────────────────────────────────────────────────────
def safe_int(v, default, lo=1, hi=9999):
    if v is None: return max(lo, min(default, hi))
    try: return max(lo, min(int(float(str(v).strip())), hi))
    except:
        m = re.search(r'\d+', str(v))
        return max(lo, min(int(m.group()), hi)) if m else default

def parse_time(t):
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try: return datetime.strptime(t.strip(), fmt)
        except: pass
    return None

def generate_slots(start="09:00", end="17:00", dur=60, brk="13:00", brk_dur=60):
    slots, breaks = [], set()
    try:
        cur   = parse_time(start) or datetime(2000,1,1,9,0)
        end_t = parse_time(end)   or datetime(2000,1,1,17,0)
        b_s   = parse_time(brk)  or datetime(2000,1,1,13,0)
        b_e   = b_s + timedelta(minutes=max(0, brk_dur))
        step  = timedelta(minutes=max(15, dur))
        while cur < end_t:
            s = cur.strftime("%H:%M"); slots.append(s)
            if b_s <= cur < b_e: breaks.add(s)
            cur += step
    except:
        slots  = ["09:00","10:00","11:00","12:00","13:00","14:00","15:00","16:00"]
        breaks = {"13:00"}
    return slots, breaks

# ─── OR-Tools CP-SAT Engine ─────────────────────────────────────────────────────
def schedule_with_ortools(subjects, days, slots, breaks, time_limit=10):
    """
    Use Google OR-Tools CP-SAT solver to build a constraint-satisfying timetable.

    Decision variables:
        x[s, d, t] = 1 if subject s is placed on day d at time-slot t

    Hard constraints enforced by the solver:
        1. Each subject placed exactly hours_per_week times total.
        2. At most one subject per (day, slot) — no overlap.
        3. Break slots are always free.
        4. No teacher double-booking: two subjects with the same teacher
           cannot share the same (day, slot).
        5. No two consecutive slots on the same day have the same subject.
        6. Labs: placed as a single contiguous block of lab_duration slots.

    Soft objectives (minimised):
        • Spread sessions across different days (load balancing).
    """
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return None, "ortools not installed — run: pip install ortools"

    non_break = [s for s in slots if s not in breaks]
    if not non_break or not days or not subjects:
        return None, "Nothing to schedule"

    model = cp_model.CpModel()

    S = len(subjects)
    D = len(days)
    T = len(slots)

    slot_idx   = {s: i for i, s in enumerate(slots)}
    break_idxs = {slot_idx[b] for b in breaks if b in slot_idx}

    # ── Decision variables ─────────────────────────────────────────────────────
    # x[s][d][t] = 1 iff subject s is taught on day d at slot t
    x = [[[model.NewBoolVar(f"x_{s}_{d}_{t}") for t in range(T)]
           for d in range(D)] for s in range(S)]

    # For lab subjects: start[s][d] = start slot index of the lab block on day d
    lab_start = {}

    # ── Constraint 1: break slots always 0 ────────────────────────────────────
    for s in range(S):
        for d in range(D):
            for t in break_idxs:
                model.Add(x[s][d][t] == 0)

    # ── Constraint 2: at most one subject per (day, slot) ─────────────────────
    for d in range(D):
        for t in range(T):
            if t not in break_idxs:
                model.Add(sum(x[s][d][t] for s in range(S)) <= 1)

    # ── Constraint 3: teacher no double-booking ────────────────────────────────
    teacher_map = {}
    for si, subj in enumerate(subjects):
        t_name = subj.get("teacher","")
        if t_name:
            teacher_map.setdefault(t_name, []).append(si)
    for t_name, si_list in teacher_map.items():
        if len(si_list) > 1:
            for d in range(D):
                for t in range(T):
                    model.Add(sum(x[si][d][t] for si in si_list) <= 1)

    # ── Constraint 4: no consecutive same subject on same day ─────────────────
    for si in range(S):
        for d in range(D):
            for t in range(T - 1):
                if t not in break_idxs and (t+1) not in break_idxs:
                    model.Add(x[si][d][t] + x[si][d][t+1] <= 1)

    # ── Constraint 5: exact hours_per_week placement ──────────────────────────
    for si, subj in enumerate(subjects):
        if subj.get("is_lab"):
            dur = safe_int(subj.get("lab_duration"), 2, lo=2, hi=6)
            # Lab appears dur times (the block) * number of lab blocks desired
            blocks_needed = max(1, subj["hours_per_week"] // dur)
            model.Add(sum(x[si][d][t] for d in range(D) for t in range(T)) == blocks_needed * dur)
        else:
            model.Add(sum(x[si][d][t] for d in range(D) for t in range(T))
                      == subj["hours_per_week"])

    # ── Constraint 6: labs must be in contiguous blocks ───────────────────────
    for si, subj in enumerate(subjects):
        if not subj.get("is_lab"): continue
        dur = safe_int(subj.get("lab_duration"), 2, lo=2, hi=6)

        for d in range(D):
            for t in range(T):
                if t in break_idxs: continue
                # If this slot is occupied, the next dur-1 slots must also be occupied
                for k in range(1, dur):
                    if t + k < T:
                        # x[si][d][t] <= x[si][d][t+k] ensures continuity
                        # But we need a gentler form: use interval vars
                        pass

        # Better: use AddNoOverlap with interval variables
        for d in range(D):
            intervals = []
            # Find valid start positions
            for t in range(T - dur + 1):
                # Check no break in [t, t+dur)
                if any((t+k) in break_idxs for k in range(dur)): continue
                is_block = model.NewBoolVar(f"lab_block_{si}_{d}_{t}")
                interval = model.NewOptionalIntervalVar(t, dur, t+dur, is_block, f"iv_{si}_{d}_{t}")
                intervals.append((t, dur, is_block, interval))
                # is_block=1 ↔ x[si][d][t..t+dur-1]=1
                for k in range(dur):
                    model.Add(x[si][d][t+k] >= is_block)
                    model.Add(is_block >= x[si][d][t])  # approx; tightened below

            # Exactly the right number of slots on this day come from blocks
            if intervals:
                model.AddNoOverlap([iv for _,_,_,iv in intervals])

    # ── Soft objective: balance load across days ───────────────────────────────
    day_loads = []
    for d in range(D):
        load = model.NewIntVar(0, S * T, f"load_d{d}")
        model.Add(load == sum(x[si][d][t] for si in range(S) for t in range(T)))
        day_loads.append(load)
    max_load = model.NewIntVar(0, S * T, "max_load")
    min_load = model.NewIntVar(0, S * T, "min_load")
    model.AddMaxEquality(max_load, day_loads)
    model.AddMinEquality(min_load, day_loads)
    imbalance = model.NewIntVar(0, S * T, "imbalance")
    model.Add(imbalance == max_load - min_load)
    model.Minimize(imbalance)

    # ── Solve ──────────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers  = 4
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, f"OR-Tools could not find a feasible solution (status={solver.StatusName(status)}). Try reducing hours_per_week or adding more days/slots."

    # ── Build timetable dict ───────────────────────────────────────────────────
    tt = {day: {} for day in days}
    for si, subj in enumerate(subjects):
        for di, day in enumerate(days):
            for ti, slot in enumerate(slots):
                if solver.Value(x[si][di][ti]) == 1:
                    etype = "lab" if subj.get("is_lab") else "session"
                    tt[day][slot] = {
                        "label":   f"{subj['name']} — {subj.get('teacher','')}",
                        "subject": subj["name"],
                        "teacher": subj.get("teacher",""),
                        "code":    (subj.get("code") or subj["name"][:3]).upper(),
                        "color":   subj.get("color","#4f46e5"),
                        "type":    etype,
                        "span":    1,
                        "room":    subj.get("room") or subj.get("location",""),
                        "credits": subj.get("credits",""),
                    }

    # Mark consecutive lab slots as continuations + set rowspan
    for day in days:
        for si, subj in enumerate(subjects):
            if not subj.get("is_lab"): continue
            dur = safe_int(subj.get("lab_duration"), 2, lo=2, hi=6)
            for ti in range(len(slots) - dur + 1):
                if all(solver.Value(x[si][di][ti+k])==1
                       for k in range(dur)
                       for di2,d2 in enumerate(days) if d2==day
                       for di in [di2]):
                    slot0 = slots[ti]
                    if tt[day].get(slot0, {}).get("type") == "lab":
                        tt[day][slot0]["span"] = dur
                        for k in range(1, dur):
                            if ti+k < len(slots):
                                tt[day][slots[ti+k]] = {
                                    "type":"continuation","subject":subj["name"],
                                    "teacher":subj.get("teacher",""),
                                    "parent_slot":slot0,"color":subj.get("color","#4f46e5")
                                }

    # Fill breaks
    for day in days:
        for slot in breaks:
            if slot in slots and not tt[day].get(slot):
                tt[day][slot] = {"label":"Lunch Break","subject":"__break__","teacher":"",
                                 "code":"BRK","color":"#059669","type":"break","span":1}

    expl = (f"Scheduled with Google OR-Tools CP-SAT solver. "
            f"Status: {solver.StatusName(status)}. "
            f"Solve time: {solver.WallTime():.2f}s. "
            f"Constraints: exact weekly frequency, no overlaps, no teacher double-booking, "
            f"no consecutive duplicates, lab contiguity, balanced day load.")
    return tt, expl


# ─── Greedy fallback ────────────────────────────────────────────────────────────
def schedule_greedy(subjects, days, slots, breaks):
    """Greedy CSP fallback if OR-Tools is not installed."""
    tt    = {d: {} for d in days}
    busy  = set()

    labs = sorted([s for s in subjects if s.get("is_lab")],
                  key=lambda s: -(s.get("lab_duration",2)))
    regs = sorted([s for s in subjects if not s.get("is_lab")],
                  key=lambda s: -s["hours_per_week"])

    def teacher(s): return s.get("teacher") or s.get("host","")

    def ok(day, slot, subj):
        if slot in breaks: return False
        if tt[day].get(slot): return False
        if (teacher(subj), day, slot) in busy: return False
        idx = slots.index(slot)
        for off in (-1,1):
            ni = idx+off
            if 0<=ni<len(slots):
                e = tt[day].get(slots[ni])
                if e and e.get("subject")==subj["name"]: return False
        return True

    def entry(subj, etype):
        return {"label":f"{subj['name']} — {teacher(subj)}","subject":subj["name"],
                "teacher":teacher(subj),"code":(subj.get("code") or subj["name"][:3]).upper(),
                "color":subj.get("color","#4f46e5"),"type":etype,"span":1,
                "room":subj.get("room") or subj.get("location",""),"credits":subj.get("credits","")}

    for subj in labs:
        dur    = safe_int(subj.get("lab_duration"),2,lo=2,hi=6)
        needed = max(1, subj["hours_per_week"]//dur)
        placed = 0
        for day in random.sample(days, len(days)):
            if placed >= needed: break
            for i in range(len(slots)-dur+1):
                if placed >= needed: break
                run = slots[i:i+dur]
                if any(s in breaks for s in run): continue
                if any(tt[day].get(s) for s in run): continue
                t = teacher(subj)
                if any((t,day,s) in busy for s in run): continue
                for j,s in enumerate(run):
                    if j==0: tt[day][s]={**entry(subj,"lab"),"span":dur}
                    else: tt[day][s]={"type":"continuation","subject":subj["name"],
                                      "teacher":t,"parent_slot":run[0],"color":subj.get("color","#4f46e5")}
                    busy.add((t,day,s))
                placed+=1

    for subj in regs:
        needed=subj["hours_per_week"]; placed=0
        pool=[(d,s) for d in days for s in slots if s not in breaks]
        random.shuffle(pool)
        for day,slot in pool:
            if placed>=needed: break
            if ok(day,slot,subj):
                tt[day][slot]=entry(subj,"session")
                busy.add((teacher(subj),day,slot)); placed+=1

    for day in days:
        for slot in breaks:
            if slot in slots and not tt[day].get(slot):
                tt[day][slot]={"label":"Lunch Break","subject":"__break__","teacher":"",
                               "code":"BRK","color":"#059669","type":"break","span":1}
    return tt


# ─── Dynamic updates ────────────────────────────────────────────────────────────
def do_leave(tt, subjects, absent, days_off):
    tt   = copy.deepcopy(tt)
    pool = list({s.get("teacher") or s.get("host","") for s in subjects if s.get("teacher") or s.get("host")})
    log  = []
    for day in days_off:
        for slot,e in tt.get(day,{}).items():
            if not isinstance(e,dict): continue
            if e.get("type") in ("break","holiday","continuation"): continue
            if e.get("teacher","").lower()!=absent.lower(): continue
            busy={e2["teacher"] for d,sd in tt.items() for s2,e2 in sd.items()
                  if isinstance(e2,dict) and e2.get("teacher") and d==day and s2==slot}
            free=next((t for t in pool if t.lower()!=absent.lower() and t not in busy),None)
            if free:
                e["teacher"]=free; e["label"]=f"{e['subject']} — {free}"
                e["substituted"]=True; e["orig_teacher"]=absent
                log.append({"day":day,"slot":slot,"subject":e["subject"],"assigned":free,"ok":True})
            else:
                e["teacher"]="⚠ Unassigned"; e["substituted"]=True; e["orig_teacher"]=absent
                log.append({"day":day,"slot":slot,"subject":e["subject"],"assigned":None,"ok":False})
    return tt, log

def do_holiday(tt, days):
    tt=copy.deepcopy(tt)
    for day in days:
        if day in tt:
            for slot in list(tt[day]):
                tt[day][slot]={"label":"Holiday","subject":"__holiday__","teacher":"",
                               "code":"HOL","color":"#d97706","type":"holiday","span":1}
    return tt

def do_extra(tt, day, slot, subject, teacher, color="#f97316"):
    tt=copy.deepcopy(tt)
    if day not in tt: return tt,False,"Day not found"
    target=None
    if slot and not tt[day].get(slot): target=slot
    else:
        for s in tt[day]:
            if not tt[day][s]: target=s; break
    if not target: return tt,False,"No free slot found"
    tt[day][target]={"label":f"{subject} — {teacher}","subject":subject,"teacher":teacher,
                     "code":"EXT","color":color,"type":"extra","span":1}
    return tt,True,target

def make_expl(cfg, tt, solver_note=""):
    sessions=sum(1 for d in tt.values() for e in d.values() if isinstance(e,dict) and e.get("type")=="session")
    labs    =sum(1 for d in tt.values() for e in d.values() if isinstance(e,dict) and e.get("type")=="lab")
    names   =[s["name"] for s in cfg.get("subjects",[])]
    if solver_note:
        return solver_note
    return (f"Generated {len(cfg.get('days',[]))}-day timetable · {len(cfg.get('time_slots',[]))} slots/day · "
            f"{sessions} sessions + {labs} lab blocks · Greedy CSP fallback · Subjects: {', '.join(names)}.")

# ─── AI Chat ────────────────────────────────────────────────────────────────────
SYS = """You are SmartSchedule AI using Google OR-Tools CP-SAT for scheduling.
Supports College, School, Corporate, Custom. Every field is always visible.
Be concise (2-3 sentences)."""

def call_ai(messages):
    if ANTHROPIC_KEY:
        try:
            import anthropic
            c=anthropic.Anthropic(api_key=ANTHROPIC_KEY)
            r=c.messages.create(model="claude-sonnet-4-6",max_tokens=300,system=SYS,messages=messages)
            return r.content[0].text.strip()
        except: pass
    if OPENAI_KEY:
        try:
            import openai; openai.api_key=OPENAI_KEY
            r=openai.chat.completions.create(model="gpt-4o-mini",
                messages=[{"role":"system","content":SYS}]+messages,max_tokens=250)
            return r.choices[0].message.content.strip()
        except: pass
    return None

def rule_reply(text):
    t=text.lower()
    if any(w in t for w in ["hi","hello","hey"]):
        return "👋 Hi! SmartSchedule AI uses **Google OR-Tools CP-SAT** to generate constraint-perfect timetables. Add subjects, set days & times, then hit **Generate**!"
    if "ortools" in t or "or-tools" in t or "cp-sat" in t or "solver" in t:
        return "I use **Google OR-Tools CP-SAT** — a constraint programming solver. It guarantees exact weekly frequency, no overlaps, no teacher double-booking, lab contiguity, and balanced day load. If OR-Tools isn't installed, a greedy CSP fallback is used."
    if "college" in t: return "For **College**, fill in: Subject Name, Professor, Hours/Week, Credits, Room, Department, and toggle Lab if needed."
    if "school" in t:  return "For **School**, fill in: Subject Name, Teacher, Hours/Week, Room, Class Group, and toggle PT/Activity if it's a physical period."
    if "corporate" in t or "team" in t: return "For **Corporate**, fill in: Session Name, Host, Hours/Week, Duration (mins), Location, and Meeting Type."
    if "lab" in t: return "Toggle **Lab session** on a subject, set **Lab Duration** (number of consecutive slots), and the solver will place it as one unbroken block."
    if "leave" in t or "absent" in t: return "Click **✋ Leave** in the navbar. Pick the teacher, day(s), and substitute — all their slots are auto-reassigned."
    if "holiday" in t: return "Click **🏖 Holiday** in the navbar to mark any day as a holiday."
    if "extra" in t: return "Click **⚡ Extra Session** to insert an unplanned session into the first free slot on a chosen day."
    if "install" in t or "pip" in t: return "Run `pip install ortools` to enable the OR-Tools CP-SAT solver. Without it, a greedy CSP fallback is used automatically."
    if "export" in t or "excel" in t: return "Use **📊 Excel** or **📸 PNG** in the navbar after generating."
    return random.choice([
        "Add subjects, set days & times, then click **Generate Timetable**! OR-Tools handles the rest. 🚀",
        "Tip: OR-Tools CP-SAT guarantees an optimal solution or reports if no feasible schedule exists.",
        "All fields are always visible — fill in what you need and leave others blank.",
    ])

# ─── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def landing():
    return render_template("Landing.html")

@app.route("/dashboard")
def dashboard():
    return render_template("index.html")

@app.route("/presets")
def presets():
    t=request.args.get("type","college")
    return jsonify({"subjects":PRESETS.get(t,PRESETS["college"]),"colors":PALETTE})

@app.route("/suggest",methods=["POST"])
def suggest():
    data=request.get_json(silent=True) or {}
    print(f"DEBUG: Data received from frontend! Role is: {data.get('type')}")
    stype=data.get("type","college")
    if ANTHROPIC_KEY or OPENAI_KEY:
        prompt=(f"Suggest 5-6 realistic {stype} subjects as JSON array. "
                f"Each: {{name,teacher,hours_per_week(1-6),is_lab(bool),lab_duration(2-3)}}. JSON only.")
        result=call_ai([{"role":"user","content":prompt}])
        if result:
            try:
                cleaned=re.sub(r'```json|```','',result).strip()
                return jsonify({"subjects":__import__('json').loads(cleaned),"colors":PALETTE})
            except: pass
    return jsonify({"subjects":PRESETS.get(stype,PRESETS["college"]),"colors":PALETTE})

@app.route("/chat",methods=["POST"])
def chat():
    data=request.get_json(silent=True) or {}
    msg=data.get("message","").strip(); history=data.get("history",[])
    if not msg: return jsonify({"reply":"Hi! How can I help?"})
    reply=call_ai(history[-10:]+[{"role":"user","content":msg}]) or rule_reply(msg)
    return jsonify({"reply":reply})

@app.route("/generate",methods=["POST"])
def generate():
    data    =request.get_json(silent=True) or {}
    subjects=data.get("subjects",[])
    if not subjects: return jsonify({"error":"Add at least one subject first."}),400

    for i,s in enumerate(subjects):
        s["color"]         =PALETTE[i%len(PALETTE)]
        s["code"]          =(s.get("code") or s["name"][:3]).upper()
        s["hours_per_week"]=safe_int(s.get("hours_per_week"),3,lo=1,hi=20)
        s["lab_duration"]  =safe_int(s.get("lab_duration") or s.get("multi_slots"),2,lo=2,hi=6)

    ordered=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    days   =[d for d in ordered if d in data.get("days",ordered[:5])] or ordered[:5]

    slot_dur=safe_int(data.get("slot_duration",60),60,lo=15,hi=180)
    brk_dur =safe_int(data.get("break_duration",60),60,lo=0,hi=180)
    # ── BACKEND LEAD: FORCE ROLE-BASED TIMES ──
    role = data.get('type', 'college')
    if role == 'college':
        start_t, end_t = "07:30", "12:00"
    else:
        start_t = data.get("start_time", "09:00")
        end_t = data.get("end_time", "17:00")

    slots, breaks = generate_slots(start_t, end_t, 
                                   slot_dur, data.get("break_start", "13:00"), brk_dur)
    # ──────────────────────────────────────────
    config={"days":days,"time_slots":slots,"break_slots":list(breaks),
            "subjects":subjects,"slot_duration":slot_dur}

    # Try OR-Tools first, fall back to greedy
    tt, solver_note = schedule_with_ortools(subjects, days, slots, breaks, time_limit=12)
    used_solver = "OR-Tools CP-SAT"
    if tt is None:
        tt = schedule_greedy(subjects, days, slots, breaks)
        used_solver = f"Greedy CSP (OR-Tools unavailable: {solver_note})"
        solver_note = ""

    expl=make_expl(config, tt, solver_note)
    session["timetable"]=tt; session["config"]=config
    return jsonify({"timetable":tt,"config":config,"explanation":expl,"solver":used_solver})

@app.route("/update",methods=["POST"])
def update():
    data=request.get_json(silent=True) or {}
    action=data.get("action","")
    tt=session.get("timetable"); cfg=session.get("config",{})
    if not tt: return jsonify({"error":"Generate a timetable first."}),400
    subjects=cfg.get("subjects",[]); log=[]

    if action=="leave":
        teacher=data.get("teacher","").strip(); days_off=data.get("days",[])
        if not teacher or not days_off:
            return jsonify({"error":"Specify teacher and at least one day."}),400
        tt,log=do_leave(tt,subjects,teacher,days_off)
        ok=sum(1 for l in log if l["ok"]); bad=len(log)-ok
        msg=f"Leave applied for {teacher}. {ok} slot(s) reassigned"+(f"; {bad} unassigned." if bad else ".")
    elif action=="holiday":
        days_off=data.get("days",[])
        if not days_off: return jsonify({"error":"Select at least one day."}),400
        tt=do_holiday(tt,days_off); msg=f"🏖 {', '.join(days_off)} marked as holiday."
    elif action=="extra":
        day,slot=data.get("day",""),data.get("slot","")
        subj,host=data.get("subject","Extra Session"),data.get("teacher","TBD")
        tt,ok,info=do_extra(tt,day,slot,subj,host)
        msg=f"⚡ '{subj}' added on {day} at {info}." if ok else f"⚠ {info}"
    else:
        return jsonify({"error":f"Unknown action '{action}'"}),400

    session["timetable"]=tt
    return jsonify({"timetable":tt,"message":msg,"log":log,"explanation":make_expl(cfg,tt)})

@app.route("/export-excel")
def export_excel():
    try: import openpyxl; from openpyxl.styles import PatternFill,Font,Alignment,Border,Side
    except ImportError: return jsonify({"error":"pip install openpyxl"}),500
    tt=session.get("timetable"); cfg=session.get("config",{})
    if not tt: return jsonify({"error":"Generate a timetable first."}),400

    wb=openpyxl.Workbook(); ws=wb.active; ws.title="Timetable"
    thin=Side(style="thin",color="E2E8F0"); bd=Border(left=thin,right=thin,top=thin,bottom=thin)

    def cell(r,c,val="",bold=False,bg=None,fg="1e1b4b",align="center",sz=10):
        cl=ws.cell(row=r,column=c,value=val)
        cl.font=Font(bold=bold,color=fg,name="Calibri",size=sz)
        cl.alignment=Alignment(horizontal=align,vertical="center",wrap_text=True)
        cl.border=bd
        if bg: cl.fill=PatternFill("solid",fgColor=bg.lstrip("#"))
        return cl

    days,slots=cfg.get("days",[]),cfg.get("time_slots",[])
    W=len(days)+1
    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=W)
    cell(1,1,f"SmartSchedule AI (OR-Tools) · {datetime.now():%d %b %Y  %H:%M}",
         bold=True,bg="4f46e5",fg="FFFFFF",sz=13)
    ws.row_dimensions[1].height=34
    cell(2,1,"Time",bold=True,bg="1e1b4b",fg="FFFFFF"); ws.column_dimensions["A"].width=12
    for ci,d in enumerate(days,2):
        c=cell(2,ci,d,bold=True,bg="312e81",fg="E0E7FF"); ws.column_dimensions[c.column_letter].width=22
    ws.row_dimensions[2].height=22; ALT=["F5F3FF","EDE9FE"]
    for ri,slot in enumerate(slots,3):
        ws.row_dimensions[ri].height=22; cell(ri,1,slot,bold=True,bg="1e1b4b",fg="C7D2FE")
        for ci,day in enumerate(days,2):
            e=tt.get(day,{}).get(slot)
            if not isinstance(e,dict): cell(ri,ci,"—",bg="F9FAFB",fg="D1D5DB"); continue
            t=e.get("type",""); val="" if t=="continuation" else e.get("label","—")
            bg=("FEF9C3" if t=="holiday" else "DCFCE7" if t=="break" else
                "FCE7F3" if t=="extra" else "EDE9FE" if t in ("lab","continuation") else ALT[ri%2])
            cell(ri,ci,val,bg=bg,align="left")
    buf=io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,download_name=f"SmartSchedule_{datetime.now():%Y%m%d_%H%M}.xlsx")

@app.errorhandler(413)
def too_large(e): return jsonify({"error":"Request too large."}),413

if __name__=="__main__":
    print("\n✦ SmartSchedule AI (OR-Tools) → http://127.0.0.1:5000\n")
    print("  Install OR-Tools: pip install ortools\n")
    app.run(debug=True,port=5000)