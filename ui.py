import json, os, re, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
UPLOADS = ROOT / "uploads"
STATE = {"running": False, "log": "", "skill": "", "start": 0.0}
LOCK = threading.Lock()
REPO_RE = re.compile(r"^(https?://[\w./:@~-]+|[\w.-]+/[\w.-]+|[\w:\\/. -]+)$")

PAGE = r"""<!doctype html><meta charset=utf-8><title>SkillForge</title>
<style>
body{font-family:system-ui;max-width:900px;margin:28px auto;padding:0 16px;color:#111}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:700px){.cards{grid-template-columns:1fr}}
.card{border:1px solid #ccc;border-radius:10px;padding:14px}
.card h3{margin-top:0}
input[type=text]{width:100%;padding:9px;font-size:15px;box-sizing:border-box}
button{padding:9px 16px;font-size:15px;cursor:pointer;margin-top:8px}
button:disabled{opacity:.5;cursor:not-allowed}
small{color:#555}
pre{background:#111;color:#9f9;padding:12px;height:240px;overflow:auto;white-space:pre-wrap}
pre.skill{background:#f6f6f6;color:#111;height:auto;max-height:420px}
#status{font-weight:600}
</style>
<h1>SkillForge</h1>
<p>An open-weight model (Gemma via Ollama) writes, validates and repairs an Agent Skill
(<code>SKILL.md</code>) for any code repository. Choose one input below.</p>

<div class=cards>
  <div class=card>
    <h3>Option 1: Repository link</h3>
    <input type=text id=repo placeholder="https://github.com/owner/repo  or  owner/repo">
    <small>Public GitHub URL, <code>owner/repo</code>, or a local path.</small><br>
    <button id=go>Forge from link</button>
    <button id=demo>Try demo</button>
  </div>
  <div class=card>
    <h3>Option 2: Upload a folder</h3>
    <input type=file id=pick webkitdirectory multiple>
    <br><small id=pickinfo>Pick the repo folder. Only code and text files are sent
    (.git, node_modules and similar are skipped).</small><br>
    <button id=up>Forge from folder</button>
  </div>
</div>

<p id=status>Idle</p>
<h3>Live log</h3><pre id=log></pre>
<h3>Generated SKILL.md</h3><pre id=skill class=skill>(nothing yet)</pre>
<a id=dl href="/skill" style="display:none" download="SKILL.md">Download SKILL.md</a>

<script>
const $=id=>document.getElementById(id);
const SKIP=["/.git/","node_modules","__pycache__","/venv/","/.venv/","/dist/","/build/","/.idea/"];
const OK=/\.(py|js|ts|tsx|jsx|go|rs|md|txt|toml|json|yaml|yml|cfg|ini|mod)$|^(LICENSE|Makefile)$/i;
const MAX_FILES=400, MAX_BYTES=5000000;

function keep(f){
  const p="/"+f.webkitRelativePath;
  if(SKIP.some(s=>p.includes(s))) return false;
  return OK.test(f.name) && f.size<200000;
}
function picked(){ return [...$("pick").files].filter(keep); }

$("pick").onchange=()=>{
  const fs=picked(), bytes=fs.reduce((a,f)=>a+f.size,0);
  $("pickinfo").textContent=fs.length+" files selected ("+Math.round(bytes/1024)+" KB)";
};

async function post(url,obj){
  try{
    const r=await fetch(url,{method:"POST",body:JSON.stringify(obj)});
    const j=await r.json();
    if(!j.ok) $("status").textContent=j.error;
  }catch(e){ $("status").textContent="Request failed: "+e; }
}

$("go").onclick=()=>post("/run",{repo:$("repo").value.trim()});
$("demo").onclick=()=>post("/run",{repo:"demo_repo"});

$("up").onclick=async()=>{
  const fs=picked();
  if(!fs.length){ $("status").textContent="Pick a folder first."; return; }
  const bytes=fs.reduce((a,f)=>a+f.size,0);
  if(fs.length>MAX_FILES||bytes>MAX_BYTES){
    $("status").textContent="Folder too large ("+fs.length+" files). Pick a smaller repo (max "+MAX_FILES+" files, 5 MB).";
    return;
  }
  $("status").textContent="Uploading "+fs.length+" files...";
  const files=[];
  for(const f of fs) files.push({path:f.webkitRelativePath,content:await f.text()});
  const name=fs[0].webkitRelativePath.split("/")[0];
  await post("/upload",{name:name,files:files});
};

async function poll(){
  try{
    const s=await (await fetch("/status")).json();
    if(s.running) $("status").textContent="Running... (CPU model, this can take a few minutes)";
    else if($("status").textContent.startsWith("Running")) $("status").textContent="Finished";
    for(const id of ["go","demo","up"]) $(id).disabled=s.running;
    $("log").textContent=s.log; $("log").scrollTop=1e9;
    if(s.skill){ $("skill").textContent=s.skill; $("dl").style.display="inline"; }
  }catch(e){}
  setTimeout(poll,2000);
}
poll();
</script>"""


def run_job(target):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.Popen([sys.executable, "-u", "harness.py", target], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:
        with LOCK:
            STATE["log"] += line
    p.wait()
    found = [f for f in (ROOT / "output").rglob("SKILL.md")
             if f.stat().st_mtime >= STATE["start"]]
    with LOCK:
        if found:
            newest = max(found, key=lambda f: f.stat().st_mtime)
            STATE["skill"] = newest.read_text(encoding="utf-8", errors="replace")
        else:
            STATE["log"] += "\n[ui] No SKILL.md was produced for this run.\n"
        STATE["running"] = False


def start_job(target):
    with LOCK:
        STATE.update(running=True, log=f"$ python harness.py {target}\n",
                     skill="", start=time.time())
    threading.Thread(target=run_job, args=(target,), daemon=True).start()


def save_upload(name, files):
    safe = re.sub(r"[^\w.-]", "_", name)[:40] or "repo"
    dest = UPLOADS / f"{safe}_{int(time.time())}" / safe
    dest.mkdir(parents=True, exist_ok=True)
    base = dest.resolve()
    written = 0
    for f in files:
        rel = Path(f.get("path", "").replace("\\", "/"))
        parts = [x for x in rel.parts if x not in ("", ".")]
        if not parts or rel.is_absolute() or ".." in parts or ":" in f.get("path", ""):
            continue
        # drop the top-level folder name so the repo root is `dest`
        sub = Path(*parts[1:]) if len(parts) > 1 else Path(parts[0])
        out = (base / sub).resolve()
        if base not in out.parents:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f.get("content", ""), encoding="utf-8", errors="replace")
        written += 1
    return str(dest), written


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _json(self, obj):
        self._send(json.dumps(obj), "application/json")

    def do_GET(self):
        if self.path == "/status":
            with LOCK:
                self._json(STATE)
        elif self.path == "/skill":
            with LOCK:
                self._send(STATE["skill"], "text/markdown; charset=utf-8")
        else:
            self._send(PAGE)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(n))
        except Exception:
            return self._json({"ok": False, "error": "Bad request."})
        with LOCK:
            busy = STATE["running"]
        if busy:
            return self._json({"ok": False, "error": "A run is already in progress."})

        if self.path == "/run":
            repo = str(data.get("repo", "")).strip()
            if not repo or repo.startswith("-") or not REPO_RE.match(repo):
                return self._json({"ok": False, "error": "Enter a valid repo link, owner/repo, or folder path."})
            start_job(repo)
            return self._json({"ok": True})

        if self.path == "/upload":
            files = data.get("files", [])
            if not isinstance(files, list) or not files:
                return self._json({"ok": False, "error": "No files received."})
            target, count = save_upload(str(data.get("name", "repo")), files)
            if not count:
                return self._json({"ok": False, "error": "No usable files in that folder."})
            start_job(target)
            return self._json({"ok": True})

        self._json({"ok": False, "error": "Unknown action."})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("SkillForge UI on http://127.0.0.1:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), H).serve_forever()