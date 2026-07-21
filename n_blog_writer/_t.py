import threading, time
from workspace import Workspace
ev = threading.Event(); logs = []
def log(m):
    logs.append(m); print("LOG:", m, flush=True)
ws = Workspace(log=log, stop_event=ev)
t = threading.Thread(target=ws.run); t.start()
for _ in range(90):
    time.sleep(1)
    if any("준비 완료" in m or "오류" in m for m in logs): break
if ws.editor:
    print("EDITOR title box:", ws.editor.locator(".se-documentTitle").count())
    print("EDITOR popup left:", ws.editor.locator(".se-popup:visible").count())
ev.set(); t.join(30); print("alive:", t.is_alive())
