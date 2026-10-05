#!/usr/bin/env python3
"""Offline checks for the video-dub review fixes (no GPU, no network, no model).

Covers the items that can be exercised without an S2ST service:
  * case_registry: concurrent register_case() must not lose cases
    (the same test is also run against the pre-fix module as a red baseline)
  * demo/app.py run_pipeline: text-only /s2tt response, per-segment failure,
    failed extract, and cleanup of the per-job work dir with the final
    artefacts preserved
  * dub_video.py: temp dir removed on success / early exit / crash, kept with
    --keep-temp, and --max-seg <= 0 rejected
  * index_dub/segment.py: non-positive max_dur raises instead of splitting
    forever (the pre-fix module is shown hanging in a subprocess)
  * deploy/serve_s2st.py: --device overrides CUDA_VISIBLE_DEVICES and the
    Content-Length pre-check answers 413

Run:
    python tests/test_videodub_fixes.py
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # video-dub/
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

BASE_COMMIT = "9cc5ee7"
FAILURES = []
CHECKS = [0]


def check(name, cond, detail=""):
    CHECKS[0] += 1
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILURES.append(name)


def load_module_from_source(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git_show(rel_path, dest):
    src = subprocess.run(["git", "show", f"{BASE_COMMIT}:{rel_path}"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    with open(dest, "w", encoding="utf-8") as f:
        f.write(src)
    return dest


def concurrent_register(registry, demo_dir, n_threads=8, per_thread=10):
    """Register n_threads*per_thread distinct cases from n_threads threads."""
    ids = [f"case-{t}-{i}" for t in range(n_threads) for i in range(per_thread)]
    errs = []

    def worker(chunk):
        try:
            for cid in chunk:
                registry.register_case(demo_dir, cid,
                                       {"video": f"{cid}.mp4", "title": cid},
                                       [{"start": 0.0, "end": 1.0, "src": "a", "text": "b"}],
                                       tab=cid)
        except Exception as e:  # noqa: BLE001
            errs.append(e)

    threads = [threading.Thread(target=worker, args=(ids[t::n_threads],))
               for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    listed = {c.get("id") for c in registry.list_cases(demo_dir)}
    return set(ids), listed, errs


def test_registry_concurrency(tmp):
    print("[1] case_registry: concurrent register_case")
    from demo import case_registry

    demo_dir = os.path.join(tmp, "reg-new")
    os.makedirs(demo_dir, exist_ok=True)
    want, got, errs = concurrent_register(case_registry, demo_dir)
    check("no worker raised", not errs, repr(errs[:1]))
    check("all cases registered (fixed module)", want == got,
          f"missing={len(want - got)} extra={len(got - want)}")
    check("manifest is valid JSON", isinstance(case_registry.list_cases(demo_dir), list))
    check("load_case round-trips",
          all(case_registry.load_case(demo_dir, cid) is not None for cid in want))

    old_path = git_show("video-dub/demo/case_registry.py", os.path.join(tmp, "old_registry.py"))
    old = load_module_from_source(old_path, "old_case_registry")
    old_dir = os.path.join(tmp, "reg-old")
    os.makedirs(old_dir, exist_ok=True)
    try:
        _, old_got, _ = concurrent_register(old, old_dir)
        print(f"        pre-fix module lost {len(want - old_got)}/{len(want)} cases "
              f"(red baseline, informational)")
    except Exception as e:  # noqa: BLE001
        # The pre-fix race can also corrupt the manifest, which then makes its own
        # reader raise - that unreadable-manifest failure mode is exactly what the
        # fix above prevents, so record it instead of failing the test run.
        print(f"        pre-fix manifest unreadable ({type(e).__name__}: {e}) "
              f"(red baseline, informational)")


def _patch_app_pipeline(app_mod, seen):
    """Stub the ffmpeg/service layers of demo/app.py run_pipeline."""
    from index_dub import media, segment, s2st, timeline

    def fake_extract_audio(src, dst, sr=16000):
        open(dst, "wb").close()

    def fake_extract_segment(src, dst, start, end):
        if round(start, 1) == 3.0:             # segment 3: extraction itself fails
            raise RuntimeError("simulated ffmpeg failure")
        open(dst, "wb").close()

    class FakeClient:
        def __init__(self, base_url):
            pass

        def dub(self, wav_path, lang, endpoint="/s2st"):
            name = os.path.basename(wav_path)
            if name.startswith("in_0000"):
                # audio endpoint returning text only (no _wav_bytes): the pre-fix
                # code raised KeyError here and killed the whole job
                return {"zh": "原文0", "text": "译文0"}
            if name.startswith("in_0001"):
                raise RuntimeError("simulated 422")
            return {"zh": "原文2", "text": "译文2", "_wav_bytes": b"RIFF-fake"}

    def fake_build_track(spans, dub_wavs, total_dur, workdir, sr=24000, max_stretch=1.5):
        seen["dub_wavs"] = list(dub_wavs)
        return np.zeros(int(total_dur * sr), dtype=np.float32), sr

    def fake_mux(video, audio, out):
        open(out, "wb").close()

    media.extract_audio = fake_extract_audio
    media.extract_segment = fake_extract_segment
    media.probe_duration = lambda path: 4.0
    media.mux_video_audio = fake_mux
    segment.segment_audio = lambda wav, backend="auto", max_dur=9.5: [
        (0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 4.0)]
    s2st.S2STClient = FakeClient
    timeline.build_track = fake_build_track


def test_app_pipeline(tmp):
    print("[2] demo/app.py run_pipeline: text-only response, per-segment failures, cleanup")
    import demo.app as app_mod
    from index_dub import media, segment, s2st, timeline

    orig = (media.extract_audio, media.extract_segment, media.probe_duration,
            media.mux_video_audio, segment.segment_audio, s2st.S2STClient,
            timeline.build_track, app_mod.DEMO_DIR, app_mod.UPLOAD_DIR,
            app_mod.RESULT_DIR)
    demo_dir = os.path.join(tmp, "demo")
    results = os.path.join(demo_dir, "results")
    uploads = os.path.join(demo_dir, "uploads")
    os.makedirs(results, exist_ok=True)
    os.makedirs(uploads, exist_ok=True)
    app_mod.DEMO_DIR, app_mod.UPLOAD_DIR, app_mod.RESULT_DIR = demo_dir, uploads, results
    seen = {}
    try:
        _patch_app_pipeline(app_mod, seen)
        job_id = "job-test-1"
        upload = os.path.join(uploads, f"{job_id}_sample.mp4")
        open(upload, "wb").close()
        workdir = os.path.join(results, job_id, "work")
        os.makedirs(os.path.join(workdir, "segs"), exist_ok=True)
        job = {"id": job_id, "filename": "sample.mp4", "lang": "en", "separate": False,
               "workers": 2, "s2st_url": "http://127.0.0.1:1", "upload": upload,
               "workdir": workdir, "status": "running", "step": "queued",
               "step_label": "", "seg_done": 0, "seg_total": 0,
               "log": app_mod.collections.deque(maxlen=200), "error": None,
               "result": None, "created": 0.0}
        app_mod.run_pipeline(job)

        check("job finished, not killed by a per-segment error",
              job["status"] == "done", f"status={job['status']} error={job['error']}")
        rdir = os.path.join(results, job_id)
        out_mp4 = os.path.join(rdir, "sample.en.mp4")
        check("final mp4 kept", os.path.exists(out_mp4))
        check("job['result'] points at the kept mp4",
              job["result"] == {"case_id": job_id,
                                "video": f"results/{job_id}/sample.en.mp4"},
              repr(job["result"]))
        check("per-job work dir cleaned", not os.path.exists(workdir))
        check("sibling artefacts kept",
              os.path.exists(os.path.join(rdir, "sample.en.srt"))
              and os.path.exists(os.path.join(rdir, "sample.en.segments.json")))

        manifest = json.load(open(os.path.join(rdir, "sample.en.segments.json"),
                                  encoding="utf-8"))
        check("text-only response keeps the translation",
              manifest[0]["text"] == "译文0" and manifest[0]["src"] == "原文0",
              repr(manifest[0]))
        check("failed segment recorded as empty, job alive", manifest[1]["text"] == "")
        check("audio segment dubbed", manifest[2]["text"] == "译文2")
        check("failed extract leaves the slot empty (dub_wav is None)",
              seen["dub_wavs"][3] is None and seen["dub_wavs"][0] is not None,
              repr([os.path.basename(p) if p else None for p in seen["dub_wavs"]]))
        logs = "\n".join(job["log"])
        check("log records the text-only fallback", "text-only response" in logs)
        check("log records the per-segment failure", "failed, original kept" in logs)
        check("case registered in the manifest",
              any(c["id"] == job_id for c in app_mod.case_registry.list_cases(demo_dir)))
    finally:
        (media.extract_audio, media.extract_segment, media.probe_duration,
         media.mux_video_audio, segment.segment_audio, s2st.S2STClient,
         timeline.build_track, app_mod.DEMO_DIR, app_mod.UPLOAD_DIR,
         app_mod.RESULT_DIR) = orig


def test_app_failure_cleanup(tmp):
    print("[2b] demo/app.py: failed jobs release scratch files")
    import demo.app as app_mod
    from index_dub import media, segment, s2st, timeline

    orig = (media.extract_audio, media.extract_segment, media.probe_duration,
            media.mux_video_audio, segment.segment_audio, s2st.S2STClient,
            timeline.build_track)
    try:
        for stage in ("extract", "assemble"):
            _patch_app_pipeline(app_mod, {})
            rdir = os.path.join(tmp, f"failed-{stage}")
            workdir = os.path.join(rdir, "work")
            os.makedirs(workdir, exist_ok=True)
            with open(os.path.join(workdir, "scratch.wav"), "wb") as f:
                f.write(b"scratch")
            sibling = os.path.join(rdir, "preserved.txt")
            with open(sibling, "w") as f:
                f.write("keep")
            if stage == "extract":
                def fail_extract(*args, **kwargs):
                    raise RuntimeError("simulated extraction failure")
                media.extract_audio = fail_extract
            else:
                def fail_assemble(*args, **kwargs):
                    raise RuntimeError("simulated assembly failure")
                timeline.build_track = fail_assemble
            job = {"id": f"failed-{stage}", "filename": "sample.mp4", "lang": "en",
                   "separate": False, "workers": 2, "s2st_url": "http://127.0.0.1:1",
                   "upload": "stub.mp4", "workdir": workdir, "status": "running",
                   "log": app_mod.collections.deque(maxlen=200)}
            with contextlib.redirect_stderr(io.StringIO()):
                app_mod.run_pipeline(job)
            check(f"{stage} failure is recorded", job["status"] == "error")
            check(f"{stage} failure cleans work dir", not os.path.exists(workdir))
            check(f"{stage} failure preserves siblings", os.path.exists(sibling))
    finally:
        (media.extract_audio, media.extract_segment, media.probe_duration,
         media.mux_video_audio, segment.segment_audio, s2st.S2STClient,
         timeline.build_track) = orig


def test_dub_video_tempdir_and_cli(tmp):
    print("[3] dub_video.py: temp dir lifecycle + --max-seg validation")
    import dub_video
    from index_dub import media, segment, s2st, timeline

    orig = (media.extract_audio, media.probe_duration, media.mux_video_audio,
            segment.segment_audio, s2st.S2STClient, timeline.build_track,
            dub_video.tempfile)
    tmpdirs = []

    class FakeTmp:
        @staticmethod
        def mkdtemp(prefix=""):
            path = tempfile.mkdtemp(prefix=prefix, dir=tmp)
            tmpdirs.append(path)
            return path

    try:
        def _write_silent_wav(path, sr=16000, seconds=2.0):
            # a real wav so the un-stubbed media.extract_segment can run ffmpeg on it
            import wave
            with wave.open(path, "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(sr)
                handle.writeframes(b"\x00\x00" * int(sr * seconds))

        media.extract_audio = lambda src, dst, sr=16000: _write_silent_wav(dst, sr)
        media.probe_duration = lambda path: 2.0
        media.mux_video_audio = lambda v, a, o: open(o, "wb").close()

        class FakeClient:
            def __init__(self, base_url):
                pass

            def healthz(self):
                return {"ok": True}

            def dub(self, wav_path, lang, endpoint="/s2st"):
                return {"zh": "源", "text": "译", "_wav_bytes": b"RIFF-fake"}

        s2st.S2STClient = FakeClient
        timeline.build_track = lambda spans, wavs, dur, wd, sr=24000, max_stretch=1.5: (
            np.zeros(int(dur * sr), dtype=np.float32), sr)
        dub_video.tempfile = FakeTmp
        inp = os.path.join(tmp, "in.mp4")
        open(inp, "wb").close()

        def run(args):
            argv = sys.argv
            sys.argv = ["dub_video.py"] + args
            try:
                return dub_video.main()
            finally:
                sys.argv = argv

        segment.segment_audio = lambda wav, backend="auto", max_dur=9.5: [(0.0, 1.0), (1.0, 2.0)]
        out = os.path.join(tmp, "ok.mp4")
        with contextlib.redirect_stdout(io.StringIO()):
            run([inp, "--lang", "en", "--no-separate", "-o", out])
        check("success path: outputs written",
              os.path.exists(out)
              and os.path.exists(os.path.join(tmp, "ok.segments.json")))
        check("success path: temp dir removed", not os.path.exists(tmpdirs[-1]), tmpdirs[-1])

        out2 = os.path.join(tmp, "keep.mp4")
        with contextlib.redirect_stdout(io.StringIO()):
            run([inp, "--lang", "en", "--no-separate", "-o", out2, "--keep-temp"])
        check("--keep-temp: temp dir kept", os.path.exists(tmpdirs[-1]), tmpdirs[-1])

        # early exit: no speech detected -> sys.exit, temp dir must still go
        segment.segment_audio = lambda wav, backend="auto", max_dur=9.5: []
        try:
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                run([inp, "--lang", "en", "--no-separate",
                     "-o", os.path.join(tmp, "none.mp4")])
            exited = False
        except SystemExit:
            exited = True
        check("early exit still cleaned the temp dir",
              exited and not os.path.exists(tmpdirs[-1]), tmpdirs[-1])

        # crash mid-pipeline: build_track blows up after the temp dir was filled
        segment.segment_audio = lambda wav, backend="auto", max_dur=9.5: [(0.0, 1.0)]
        good_build = timeline.build_track
        timeline.build_track = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                run([inp, "--lang", "en", "--no-separate",
                     "-o", os.path.join(tmp, "crash.mp4")])
            crashed = False
        except RuntimeError:
            crashed = True
        finally:
            timeline.build_track = good_build
        check("crash still cleaned the temp dir",
              crashed and not os.path.exists(tmpdirs[-1]), tmpdirs[-1])

        cli = subprocess.run([sys.executable, "dub_video.py", inp, "--lang", "en",
                              "--max-seg", "0"], cwd=ROOT, capture_output=True, text=True)
        check("--max-seg 0 rejected with exit code 2", cli.returncode == 2,
              f"rc={cli.returncode}")
        check("--max-seg 0 message is explicit", "greater than 0" in cli.stderr,
              cli.stderr.strip()[-120:])
    finally:
        (media.extract_audio, media.probe_duration, media.mux_video_audio,
         segment.segment_audio, s2st.S2STClient, timeline.build_track,
         dub_video.tempfile) = orig


def test_segment_max_dur_guard(tmp):
    print("[4] index_dub/segment.py: max_dur <= 0 refuses instead of splitting forever")
    from index_dub import segment

    for bad in (0.0, -1.0):
        try:
            segment.segment_audio("missing.wav", max_dur=bad)
            check(f"segment_audio(max_dur={bad}) raises", False)
        except ValueError:
            check(f"segment_audio(max_dur={bad}) raises ValueError", True)
        try:
            segment._enforce_max_dur([(0.0, 5.0)],
                                     np.zeros(16000 * 5, dtype="float32"), 16000, bad)
            check(f"_enforce_max_dur(max_dur={bad}) raises", False)
        except ValueError:
            check(f"_enforce_max_dur(max_dur={bad}) raises ValueError", True)

    old_path = git_show("video-dub/index_dub/segment.py", os.path.join(tmp, "old_segment.py"))
    probe = (
        "import importlib.util, numpy as np\n"
        "spec = importlib.util.spec_from_file_location('old_segment', " + repr(old_path) + ")\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "m._enforce_max_dur([(0.0, 5.0)], np.zeros(16000 * 5, dtype='float32'), 16000, 0.0)\n"
        "print('terminated')\n")
    try:
        r = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                           text=True, timeout=20)
        red = f"terminated rc={r.returncode}"
    except subprocess.TimeoutExpired:
        red = "still running after 20s -> effectively infinite split (red baseline)"
    print(f"        pre-fix module with max_dur=0: {red}")


def test_serve_s2st(tmp):
    print("[5] deploy/serve_s2st.py: --device override + Content-Length pre-check (413)")
    model_dir = os.path.join(tmp, "fake_model")
    os.makedirs(model_dir, exist_ok=True)
    with open(os.path.join(model_dir, "modeling_dubbing.py"), "w", encoding="utf-8") as f:
        f.write("class DubbingBridgeModel:\n"
                "    @classmethod\n"
                "    def from_pretrained(cls, path):\n"
                "        return cls()\n")

    spec = importlib.util.spec_from_file_location(
        "serve_s2st", os.path.join(ROOT, "deploy", "serve_s2st.py"))
    serve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(serve)

    old_env = os.environ.pop("CUDA_VISIBLE_DEVICES", None)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            app = serve.build_app(model_dir, device="3")
        check("--device sets CUDA_VISIBLE_DEVICES on a clean env",
              os.environ.get("CUDA_VISIBLE_DEVICES") == "3",
              os.environ.get("CUDA_VISIBLE_DEVICES"))
        os.environ.pop("CUDA_VISIBLE_DEVICES", None)

        os.environ["CUDA_VISIBLE_DEVICES"] = "1"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            serve.build_app(model_dir, device="3")
        check("--device overrides an inherited value",
              os.environ.get("CUDA_VISIBLE_DEVICES") == "3",
              os.environ.get("CUDA_VISIBLE_DEVICES"))
        check("--device override is announced (no silent setdefault)",
              "overrides" in buf.getvalue(), buf.getvalue().strip()[:120])

        try:
            from starlette.testclient import TestClient
        except ImportError as e:
            check("starlette TestClient available", False, str(e))
            return
        small = b"x" * 1024
        with TestClient(app) as client:
            ok = client.get("/healthz")
            check("/healthz still works", ok.status_code == 200 and ok.json()["ok"])
            r = client.post("/s2tt", files={"file": ("a.wav", small, "audio/wav")},
                            data={"lang": "en"})
            check("small upload passes the pre-check",
                  r.status_code != 413, f"status={r.status_code}")
            orig_limit = serve.MAX_UPLOAD_BYTES
            serve.MAX_UPLOAD_BYTES = 512
            try:
                r = client.post("/s2st", files={"file": ("a.wav", small, "audio/wav")},
                                data={"lang": "en"})
            finally:
                serve.MAX_UPLOAD_BYTES = orig_limit
            check("oversized Content-Length answered with 413",
                  r.status_code == 413 and r.json().get("ok") is False,
                  f"status={r.status_code} body={r.text[:80]}")
    finally:
        if old_env is None:
            os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        else:
            os.environ["CUDA_VISIBLE_DEVICES"] = old_env


def main():
    with tempfile.TemporaryDirectory(prefix="videodub-verify-") as tmp:
        test_registry_concurrency(tmp)
        test_app_pipeline(tmp)
        test_app_failure_cleanup(tmp)
        test_dub_video_tempdir_and_cli(tmp)
        test_segment_max_dur_guard(tmp)
        test_serve_s2st(tmp)
    print(f"\n{CHECKS[0] - len(FAILURES)}/{CHECKS[0]} checks passed")
    if FAILURES:
        print("FAILED: " + "; ".join(FAILURES))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
