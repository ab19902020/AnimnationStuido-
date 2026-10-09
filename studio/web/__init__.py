"""The studio as a web app: upload characters and backgrounds, cast and stage a scene, write the lines, give each
character a recording or a stand-in voice, and the engine (studio/film) does the rest: the cut-outs, the lip sync,
the acting, the camera, the mix and the render.

    python3 -m studio.web [--port 8000] [--host 127.0.0.1]      then open http://localhost:8000

server.py (the API and the page), jobs.py (the queue that runs the engine), projects.py (the library and the
episodes on disk), steps.py (the steps the engine's own CLI doesn't have), auto/ (the auto-director: a web episode's
studio.json -> its film/ package)."""
