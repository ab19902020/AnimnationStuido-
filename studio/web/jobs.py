"""The queue that runs the engine for the web studio: one job at a time (a render takes every core), each a list of
commands run from the repository root, logged to build/web/jobs/<id>.log. The page polls a job's state and the end
of its log."""
import itertools
import json
import os
import subprocess
import sys
import threading
import time

from studio.paths import BUILD, ROOT

PY = sys.executable
LOGS = BUILD / "web" / "jobs"


class Job:
    _ids = itertools.count(1)

    def __init__(self, title, steps, kind="", ref="", env=None, after=None):
        self.id = f"{int(time.time())}-{next(self._ids)}"
        self.title, self.steps, self.kind, self.ref = title, steps, kind, ref
        self.env = env or {}
        self.after = after                       # called with the job when it has finished well
        self.state = "queued"                    # queued, running, done, failed, cancelled
        self.step = 0
        self.started = self.ended = None
        self.error = ""
        self.result = {}
        self.proc = None
        LOGS.mkdir(parents=True, exist_ok=True)
        self.log = LOGS / f"{self.id}.log"
        self.log.write_text("")

    def view(self, tail=60):
        lines = self.log.read_text(errors="replace").splitlines()[-tail:] if self.log.exists() else []
        return dict(id=self.id, title=self.title, kind=self.kind, ref=self.ref, state=self.state, step=self.step,
                    steps=[s[0] for s in self.steps], started=self.started, ended=self.ended, error=self.error,
                    result=self.result, log=lines)


class Queue:
    def __init__(self):
        self.jobs = {}
        self.order = []
        self.lock = threading.Lock()
        self.wake = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def add(self, job):
        with self.lock:
            self.jobs[job.id] = job
            self.order.append(job.id)
        self.wake.set()
        return job

    def list(self, n=30):
        return [self.jobs[i].view(tail=4) for i in reversed(self.order[-n:])]

    def get(self, jid):
        return self.jobs.get(jid)

    def cancel(self, jid):
        j = self.jobs.get(jid)
        if not j:
            return
        if j.state == "queued":
            j.state = "cancelled"
        elif j.state == "running" and j.proc:
            j.state = "cancelled"
            try:
                os.killpg(j.proc.pid, 9)
            except OSError:
                pass

    def _next(self):
        with self.lock:
            return next((self.jobs[i] for i in self.order if self.jobs[i].state == "queued"), None)

    def _run(self):
        while True:
            j = self._next()
            if j is None:
                self.wake.wait(1.0)
                self.wake.clear()
                continue
            j.state, j.started = "running", time.time()
            env = dict(os.environ, PYTHONUNBUFFERED="1", **j.env)
            with open(j.log, "a") as log:
                for k, (label, cmd) in enumerate(j.steps):
                    if j.state == "cancelled":
                        break
                    j.step = k
                    log.write(f"\n=== {label}\n" + ("" if callable(cmd) else f"$ {' '.join(cmd)}\n"))
                    log.flush()
                    if callable(cmd):
                        try:
                            cmd(j)
                        except Exception as e:  # noqa: BLE001  (shown to the user)
                            if j.state != "cancelled":
                                j.state, j.error = "failed", f"{label}: {e}"
                            break
                        continue
                    j.proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                              start_new_session=True)
                    rc = j.proc.wait()
                    j.proc = None
                    if j.state == "cancelled":
                        break
                    if rc:
                        j.state, j.error = "failed", f"{label} failed (exit {rc}): see the log"
                        break
                else:
                    j.step = len(j.steps)
                    j.state = "done"
                    if j.after:
                        try:
                            j.after(j)
                        except Exception as e:  # noqa: BLE001
                            j.state, j.error = "failed", str(e)
            j.ended = time.time()
            (LOGS / f"{j.id}.json").write_text(json.dumps(j.view(tail=0)))


QUEUE = Queue()


def film(slug, *args):
    return [PY, "-m", "studio.film", slug, *args]


def web(slug, *args):
    return [PY, "-m", "studio.web.steps", slug, *args]


def make_episode(slug, draft=True, pack=False):
    """the whole film: (the pack read and filed,) the drawings, the voices and lip sync, the edit, the mix, the
    picture"""
    cores = str(os.cpu_count() or 4)
    steps = ([("Read the pack: script, cast, sets, voices", [PY, "-m", "studio.web.autoprod", slug])] if pack else []) + [("Cut out the cast", web(slug, "cast")),
             ("Voices and lip sync", web(slug, "voices")),
             ("The edit", film(slug, "timeline")),
             ("The mix", film(slug, "sound"))]
    if draft:
        steps += [("Render (draft, 960 x 540)", lambda j: _draft(j, slug)),
                  ("Keep the draft", web(slug, "finish", "--draft"))]
        env = {"EP_RES": "960x540"}
    else:
        steps += [("Render (1920 x 1080)", film(slug, "render", "--jobs", cores)),
                  ("Contact sheet", film(slug, "sheet")),
                  ("Lip sheet", film(slug, "lips"))]
        env = {}
    return Job(f"{'Production' if pack else 'Draft' if draft else 'Final'}{' (draft)' if pack and draft else ''}: {slug}",
               steps, "episode", slug, env)


def _draft(job, slug):
    """the engine's preview render over the whole film (it leaves the finished <slug>.mp4 alone)"""
    tl = json.loads(subprocess.run([PY, "-c", "import json,sys;from studio.film import ep;d=ep.use(sys.argv[1]);"
                                    "sys.path.insert(0,str(d));import importlib;"
                                    "print(importlib.import_module('film.timeline').TL['total'])", slug],
                                   cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    cmd = film(slug, "render", "--jobs", str(os.cpu_count() or 4), "--range", "0", f"{tl:.3f}")
    env = dict(os.environ, PYTHONUNBUFFERED="1", **job.env)
    with open(job.log, "a") as log:
        log.write(f"$ {' '.join(cmd)}\n")
        log.flush()
        job.proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        rc = job.proc.wait()
        job.proc = None
    if rc and job.state != "cancelled":
        raise RuntimeError(f"the render failed (exit {rc}): see the log")


def stills(slug, ts):
    return Job(f"Stills: {slug}", [("Cut out the cast", web(slug, "cast")), ("Voices and lip sync", web(slug, "voices")),
                                   ("Stills", web(slug, "stills", *[f"{t:.2f}" for t in ts]))],
               "stills", slug, {"EP_RES": "960x540"})


def build_character(cid, drawing):
    return Job(f"Cut out {cid}: {drawing}", [("Cut out, upscale, find the face",
                                               [PY, "-m", "studio.film.art", cid, drawing, "--force"])],
               "character", cid)
