#!/usr/bin/env python3
"""Index-Dub demo web app.

Upload a video (drag & drop or file picker), pick a target language, watch
the dubbing pipeline progress live, then play the dubbed video with
bilingual subtitles — next to every previously dubbed case (nothing is
overwritten).

The app does NOT host the model itself: it talks to an S2ST HTTP service
(`--s2st-url`). To self-host the model, start deploy/serve_s2st.py on a GPU
machine first (see README.md).

Run:
    pip install -r demo/requirements.txt   # plus the pipeline requirements
    python3 demo/app.py --s2st-url http://127.0.0.1:8094 --port 8080
"""

import argparse
import collections
import os
import re
import shutil
import threading
import time
import traceback
import uuid

import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from index_dub import media, segment, separate, s2st, subtitles, timeline  # noqa: E402
from demo import case_registry  # noqa: E402

DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(DEMO_DIR, "uploads")
RESULT_DIR = os.path.join(DEMO_DIR, "results")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# Languages, aligned with the official Index S2ST service. Allowed directions:
#   zh -> en/es/ja,  en -> zh/es/ja   (source defaults to auto-detect zh/en)
TARGET_LANGS = [
    {"code": "en", "label": "英语"},
    {"code": "ja", "label": "日语"},
    {"code": "es", "label": "西语"},
    {"code": "zh", "label": "中文"},
]
SOURCE_LANGS = [
    {"code": "", "label": "自动识别"},
    {"code": "zh", "label": "中文"},
    {"code": "en", "label": "English"},
]
DIRECTIONS = {"zh": ["en", "es", "ja"], "en": ["zh", "es", "ja"]}

JOBS = {}          # id -> job dict (in-memory; results persist on disk)
JOBS_LOCK = threading.Lock()


def _log(job, msg):
    # deque(maxlen=200) trims to the tail in the same atomic C call (a list
    # append + slice assignment could interleave between worker threads)
    job["log"].append(msg)


def _set(job, **kw):
    with JOBS_LOCK:
        job.update(kw)


def run_pipeline(job):
    """The dub_video.py pipeline, with progress reporting into the job dict."""
    tmp = job["workdir"]
    lang = job["lang"]
    try:
        client = s2st.S2STClient(job["s2st_url"])

        _set(job, step="extract", step_label="提取音频")
        full_wav = os.path.join(tmp, "audio16k.wav")
        media.extract_audio(job["upload"], full_wav, sr=16000)
        total_dur = media.probe_duration(job["upload"])
        _log(job, f"duration: {total_dur:.1f}s")

        speech_wav, instr_wav = full_wav, None
        if job["separate"]:
            _set(job, step="separate", step_label="人声分离 (demucs)")
            try:
                vocals, instr = separate.separate_vocals(full_wav, os.path.join(tmp, "demucs"))
                speech_wav = os.path.join(tmp, "vocals16k.wav")
                media.run(["ffmpeg", "-y", "-i", vocals, "-ac", "1", "-ar", "16000",
                           "-c:a", "pcm_s16le", speech_wav])
                instr_wav = instr
            except RuntimeError as e:
                _log(job, f"vocal separation unavailable: {e}; using raw audio")
                speech_wav, instr_wav = full_wav, None

        _set(job, step="segment", step_label="VAD 切句")
        spans = segment.segment_audio(speech_wav, backend="auto", max_dur=9.5)
        if not spans:
            raise RuntimeError("no speech detected, nothing to dub")
        _set(job, seg_total=len(spans), seg_done=0)
        _log(job, f"{len(spans)} segments")

        _set(job, step="dub", step_label="S2ST 配音")
        seg_dir = os.path.join(tmp, "segs")
        os.makedirs(seg_dir, exist_ok=True)
        n = len(spans)
        dub_wavs, translations, sources = [None] * n, [None] * n, [None] * n
        done = [0]

        def dub_one(i, s, e):
            seg_in = os.path.join(seg_dir, f"in_{i:04d}.wav")
            try:
                media.extract_segment(speech_wav, seg_in, s, e)
                r = client.dub(seg_in, lang)
                wav_bytes = r.get("_wav_bytes")
                if wav_bytes is None:
                    # text-only endpoint (/s2tt): no audio came back; keep the
                    # original voice in the slot but still record the
                    # translation (mirrors dub_video.py)
                    dub_wavs[i] = seg_in
                    _log(job, f"[{i + 1}/{n}] {s:.1f}-{e:.1f}s text-only response, "
                              f"original kept | {str(r.get('zh', ''))[:30]} -> "
                              f"{str(r.get('text', ''))[:30]}")
                else:
                    seg_out = os.path.join(seg_dir, f"out_{i:04d}.wav")
                    with open(seg_out, "wb") as f:
                        f.write(wav_bytes)
                    dub_wavs[i] = seg_out
                    _log(job, f"[{i + 1}/{n}] {s:.1f}-{e:.1f}s "
                              f"{str(r.get('zh', ''))[:30]} -> "
                              f"{str(r.get('text', ''))[:30]}")
                translations[i] = r.get("text", "")
                sources[i] = r.get("zh", "")
            except Exception as err:  # noqa: BLE001
                # one bad segment must never kill the whole job: keep the
                # original voice in its slot (e.g. source==target 422, effect
                # sounds the service rejects, or an extract that failed). If the
                # extract itself failed there is nothing to fall back to, and
                # the slot is left empty (timeline skips None).
                dub_wavs[i] = seg_in if os.path.exists(seg_in) else None
                translations[i] = ""
                sources[i] = ""
                _log(job, f"[{i + 1}/{n}] {s:.1f}-{e:.1f}s failed, original kept: {err}")
            finally:
                with JOBS_LOCK:
                    done[0] += 1
                    job["seg_done"] = done[0]

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=job["workers"]) as pool:
            futs = [pool.submit(dub_one, i, s, e) for i, (s, e) in enumerate(spans)]
            for f in futs:
                f.result()

        # transcribe source==target segments so the subtitle list has no gaps:
        # in a zh->en job those are English lines (en->en rejected); fetch the
        # English transcription via the reverse text endpoint.
        back_lang = {"en": "zh", "zh": "en"}.get(lang)
        kept_src = {}
        if back_lang:
            for i, (s, e) in enumerate(spans):
                if translations[i] != "" or dub_wavs[i] is None:
                    continue
                try:
                    r = client.dub(dub_wavs[i], back_lang, endpoint="/s2tt")
                    if r.get("zh"):
                        kept_src[i] = r["zh"]
                        _log(job, f"[{i + 1}/{n}] original-language line: {r['zh'][:40]}")
                except RuntimeError:
                    pass  # genuinely unusable segment; subtitle stays empty

        _set(job, step="assemble", step_label="时间轴合成")
        track, sr = timeline.build_track(spans, dub_wavs, total_dur, tmp,
                                         sr=24000, max_stretch=1.5)
        dub_track = os.path.join(tmp, "dub_track.wav")
        sf.write(dub_track, track, sr, subtype="PCM_16")
        if instr_wav:
            mixed = os.path.join(tmp, "final_track.wav")
            media.mix_audio(instr_wav, dub_track, mixed, base_vol=0.9, over_vol=1.0, sr=sr)
            dub_track = mixed

        _set(job, step="mux", step_label="封装输出")
        case_id = job["id"]
        rdir = os.path.join(RESULT_DIR, case_id)
        os.makedirs(rdir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(job["filename"]))[0]
        out_mp4 = os.path.join(rdir, f"{stem}.{lang}.mp4")
        media.mux_video_audio(job["upload"], dub_track, out_mp4)

        ok_rows = [(sp, src, t) for sp, src, t in zip(spans, sources, translations) if t]
        subtitles.write_srt(os.path.join(rdir, f"{stem}.{lang}.srt"),
                            [sp for sp, _, _ in ok_rows], [t for _, _, t in ok_rows])
        if any(src for _, src, _ in ok_rows):
            subtitles.write_bilingual_srt(os.path.join(rdir, f"{stem}.{lang}.bilingual.srt"),
                                          [sp for sp, _, _ in ok_rows],
                                          [src for _, src, _ in ok_rows],
                                          [t for _, _, t in ok_rows])
        manifest = [{"start": s, "end": e, "src": src, "text": t}
                    for (s, e), src, t in zip(spans, sources, translations)]
        with open(os.path.join(rdir, f"{stem}.{lang}.segments.json"), "w", encoding="utf-8") as f:
            import json as _json
            _json.dump(manifest, f, ensure_ascii=False, indent=1)

        # register the case for the showcase page
        case_segments = []
        for i, row in enumerate(manifest):
            if not row["text"].strip() and kept_src.get(i):
                case_segments.append({"start": row["start"], "end": row["end"],
                                      "src": kept_src[i], "text": kept_src[i],
                                      "kept": True})
            else:
                case_segments.append(row)
        n_dubbed = sum(1 for s_ in case_segments if s_["text"].strip() and not s_.get("kept"))
        meta = {
            "video": f"results/{case_id}/{stem}.{lang}.mp4",
            "title": f"{stem}（→ {lang}）",
            "meta": (f"全片 {int(total_dur // 60)}:{int(total_dur % 60):02d} · "
                     f"{len(spans)} 句（配音 {n_dubbed} · 原声保留 {len(kept_src)}） · "
                     f"{'人声分离' if instr_wav else '未分离'}"),
        }
        case_registry.register_case(DEMO_DIR, case_id, meta, case_segments,
                                    tab=f"{stem} → {lang}")

        _set(job, status="done", step="done", step_label="完成",
             result={"case_id": case_id, "video": meta["video"]})
        _log(job, f"done: {out_mp4}")

    except Exception as e:
        traceback.print_exc()
        _set(job, status="error", step_label="失败", error=str(e))
        _log(job, f"ERROR: {e}")
    finally:
        # Every finished job releases scratch files, including failed jobs.
        # Final artefacts are siblings of work/ and remain available.
        shutil.rmtree(tmp, ignore_errors=True)


def create_app(s2st_url):
    app = FastAPI(title="Index-Dub Demo")

    @app.get("/api/langs")
    def get_langs():
        return {"targets": TARGET_LANGS, "sources": SOURCE_LANGS,
                "directions": DIRECTIONS}

    @app.get("/api/cases")
    def get_cases():
        return {"cases": case_registry.list_cases(DEMO_DIR)}

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str):
        data = case_registry.load_case(DEMO_DIR, case_id)
        if data is None:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        return data

    @app.post("/api/dub")
    def post_dub(file: UploadFile = File(...), lang: str = Form(...),
                 src_lang: str = Form(""), separate: bool = Form(True),
                 workers: int = Form(4)):
        if lang not in {l["code"] for l in TARGET_LANGS}:
            return JSONResponse({"ok": False, "error": f"unsupported lang {lang}"},
                                status_code=400)
        if src_lang:
            allowed = DIRECTIONS.get(src_lang)
            if allowed is None:
                return JSONResponse({"ok": False,
                                     "error": f"unsupported source lang {src_lang}"},
                                    status_code=400)
            if lang not in allowed:
                return JSONResponse({"ok": False,
                                     "error": f"unsupported direction {src_lang}->{lang}"},
                                    status_code=400)
        job_id = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6]
        safe_name = re.sub(r"[^\w.\-]+", "_", file.filename or "upload.mp4")
        upload_path = os.path.join(UPLOAD_DIR, f"{job_id}_{safe_name}")
        with open(upload_path, "wb") as f:
            while True:
                chunk = file.file.read(8 * 1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        workdir = os.path.join(RESULT_DIR, job_id, "work")
        os.makedirs(workdir, exist_ok=True)
        job = {"id": job_id, "filename": safe_name, "lang": lang,
               "separate": separate, "workers": max(1, min(workers, 16)),
               "s2st_url": s2st_url, "upload": upload_path, "workdir": workdir,
               "status": "running", "step": "queued", "step_label": "排队中",
               "seg_done": 0, "seg_total": 0,
               "log": collections.deque(maxlen=200), "error": None,
               "result": None, "created": time.time()}
        with JOBS_LOCK:
            JOBS[job_id] = job
        threading.Thread(target=run_pipeline, args=(job,), daemon=True).start()
        return {"ok": True, "job_id": job_id}

    @app.get("/api/jobs")
    def get_jobs():
        with JOBS_LOCK:
            jobs = [{k: j[k] for k in ("id", "filename", "lang", "status",
                                       "step", "step_label", "seg_done",
                                       "seg_total", "error", "created")}
                    for j in JOBS.values()]
        return {"jobs": sorted(jobs, key=lambda j: j["created"], reverse=True)}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        job = JOBS.get(job_id)
        if not job:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        with JOBS_LOCK:
            data = {k: job[k] for k in ("id", "filename", "lang", "status", "step",
                                        "step_label", "seg_done", "seg_total",
                                        "error", "result")}
            data["log"] = list(job["log"])  # deque -> JSON list
            return data

    @app.get("/api/healthz")
    def healthz():
        try:
            return {"ok": True, "s2st": client_health(s2st_url)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def client_health(url):
        return s2st.S2STClient(url).healthz()

    # static files with HTTP Range support (needed for video seeking)
    class RangeStaticFiles(StaticFiles):
        async def __call__(self, scope, receive, send):
            await super().__call__(scope, receive, send)

    app.mount("/", RangeStaticFiles(directory=DEMO_DIR, html=True), name="static")
    return app


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--s2st-url", default=os.environ.get("S2ST_URL",
                                                         "http://127.0.0.1:8094"),
                    help="base URL of the S2ST service (env S2ST_URL)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    import uvicorn
    app = create_app(args.s2st_url)
    print(f"S2ST service: {args.s2st_url}")
    print(f"Demo: http://{args.host}:{args.port}/")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
