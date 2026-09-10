"""Milestones B, C, D: client disconnects, atomic persistence, hostile archives.

    python -m unittest -v test_resilience.py
"""

import contextlib
import email.message
import io
import json
import os
import stat
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import archive_guard as ag
import terminus_checklist_site as site

ROOT = Path(__file__).resolve().parent
GITHUB = ROOT.parent


# ----------------------------------------------------------------- helpers

class FakeWriter:
    """Socket writer that can hang up on the Nth write (0 = headers, 1 = body)."""

    def __init__(self, fail_at=None, exc=BrokenPipeError):
        self.writes, self.fail_at, self.exc = [], fail_at, exc

    def write(self, data):
        if self.fail_at is not None and len(self.writes) >= self.fail_at:
            raise self.exc(32, "Broken pipe")
        self.writes.append(bytes(data))
        return len(data)

    def flush(self):
        pass


def make_handler(method, path, fail_at=None, body=b"", headers=None, exc=BrokenPipeError):
    h = site.Handler.__new__(site.Handler)
    h.wfile = FakeWriter(fail_at, exc)
    h.rfile = io.BytesIO(body)
    h.command, h.path = method, path
    h.request_version = "HTTP/1.1"
    h.requestline = f"{method} {path} HTTP/1.1"
    h.client_address = ("127.0.0.1", 0)
    h.close_connection = False
    msg = email.message.Message()
    for k, v in (headers or {}).items():
        msg[k] = v
    h.headers = msg
    return h


def response_of(handler):
    raw = b"".join(handler.wfile.writes)
    if not raw:
        return None, None
    head, _, body = raw.partition(b"\r\n\r\n")
    status = int(head.split(b" ", 2)[1])
    return status, (json.loads(body) if body.strip().startswith((b"{", b"[")) else body)


@contextlib.contextmanager
def captured_stderr():
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        yield buf


@contextlib.contextmanager
def temp_store(content=None):
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / ".terminus_checklist.json"
        if content is not None:
            store.write_text(content, encoding="utf-8")
        with patch.object(site, "CHECKLIST_STORE", store):
            yield store


def good_checklist(marker="new"):
    return {"title": marker, "items": [{"id": f"{marker}-a", "criterion": "A"},
                                       {"id": f"{marker}-b", "criterion": "B"}]}


def seed_json():
    return json.dumps({"checklist": good_checklist("old")}, indent=2)


def zip_of(entries, method=zipfile.ZIP_DEFLATED):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", method) as z:
        for name, data in entries:
            z.writestr(name, data)
    return b.getvalue()


def patch_flag(raw: bytes, bit: int) -> bytes:
    """Set a general-purpose flag bit in every local and central header."""
    out = bytearray(raw)
    for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        i = out.find(sig)
        while i != -1:
            flags = struct.unpack_from("<H", out, i + off)[0] | bit
            struct.pack_into("<H", out, i + off, flags)
            i = out.find(sig, i + 4)
    return bytes(out)


def patch_method(raw: bytes, method: int) -> bytes:
    out = bytearray(raw)
    for sig, off in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
        i = out.find(sig)
        while i != -1:
            struct.pack_into("<H", out, i + off, method)
            i = out.find(sig, i + 4)
    return bytes(out)


# ----------------------------------------------------------------- Milestone B

class ClientDisconnectTests(unittest.TestCase):

    def test_disconnect_before_headers_is_logged_once_without_traceback(self):
        h = make_handler("GET", "/api/checklist?profile=t3", fail_at=0)
        with captured_stderr() as err:
            h.do_GET()
        self.assertTrue(h.client_gone)
        self.assertEqual(h.wfile.writes, [])  # no second response attempted
        log = err.getvalue()
        self.assertEqual(log.count("[client-disconnect]"), 1)
        self.assertIn("GET /api/checklist", log)
        self.assertNotIn("Traceback", log)

    def test_disconnect_while_writing_body(self):
        h = make_handler("GET", "/api/checklist?profile=t3", fail_at=1)
        with captured_stderr() as err:
            h.do_GET()
        self.assertTrue(h.client_gone)
        self.assertEqual(len(h.wfile.writes), 1)  # headers only
        self.assertIn("response delivery", err.getvalue())

    def test_connection_reset_is_treated_as_a_disconnect(self):
        h = make_handler("GET", "/api/checklist?profile=t3", fail_at=0, exc=ConnectionResetError)
        with captured_stderr() as err:
            h.do_GET()
        self.assertTrue(h.client_gone)
        self.assertNotIn("Traceback", err.getvalue())

    def test_disconnect_after_generation_keeps_the_atomic_save(self):
        with temp_store(seed_json()) as store, \
             patch.object(site, "generate_checklist", return_value={"checklist": good_checklist()}):
            h = make_handler("POST", "/api/checklist?profile=t3", fail_at=0)
            with captured_stderr() as err:
                h.do_POST()
            saved = json.loads(store.read_text(encoding="utf-8"))["checklist"]
        self.assertEqual(saved["title"], "new")  # the update was saved
        self.assertEqual(h.wfile.writes, [])  # and nothing was re-sent
        self.assertIn("generation and save succeeded; response not delivered", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_successful_save_is_not_reported_as_failed_when_client_leaves(self):
        with temp_store(seed_json()), \
             patch.object(site, "generate_checklist", return_value={"checklist": good_checklist()}):
            h = make_handler("POST", "/api/checklist?profile=t3", fail_at=1)
            with captured_stderr() as err:
                h.do_POST()
        self.assertNotIn("failed", err.getvalue().split(";")[0])
        self.assertIn("succeeded", err.getvalue())

    def test_genuine_generation_exception_returns_500_and_saves_nothing(self):
        with temp_store(seed_json()) as store, \
             patch.object(site, "generate_checklist", side_effect=RuntimeError("portal down")):
            h = make_handler("POST", "/api/checklist?profile=t3")
            h.do_POST()
            saved = json.loads(store.read_text(encoding="utf-8"))["checklist"]
        status, body = response_of(h)
        self.assertEqual(status, 500)
        self.assertIn("generation failed", body["error"].lower())
        self.assertEqual(saved["title"], "old")

    def test_genuine_filesystem_exception_is_a_save_failure_with_old_file_intact(self):
        with temp_store(seed_json()) as store, \
             patch.object(site, "generate_checklist", return_value={"checklist": good_checklist()}), \
             patch.object(site.os, "replace", side_effect=PermissionError("read-only")):
            h = make_handler("POST", "/api/checklist?profile=t3")
            h.do_POST()
            saved = json.loads(store.read_text(encoding="utf-8"))["checklist"]
            leftovers = [p.name for p in store.parent.iterdir() if p.suffix == ".tmp"]
        status, body = response_of(h)
        self.assertEqual(status, 500)
        self.assertIn("could not be saved", body["error"])
        self.assertIn("unchanged", body["error"])
        self.assertEqual(saved["title"], "old")
        self.assertEqual(leftovers, [])

    def test_successful_ordinary_response(self):
        h = make_handler("GET", "/api/checklist?profile=t3")
        h.do_GET()
        status, body = response_of(h)
        self.assertEqual(status, 200)
        self.assertEqual(body["profile"], "t3")
        self.assertFalse(h.client_gone)

    def test_static_file_disconnect_is_quiet(self):
        h = make_handler("GET", "/app.js", fail_at=1)
        with captured_stderr() as err:
            h.do_GET()
        self.assertIn("static file delivery", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_static_paths_cannot_leave_the_web_root(self):
        # "/." is the web root itself (a directory); the others resolve outside it.
        for path in ("/../terminus_checklist_site.py", "/..%2F..%2Fetc/passwd", "/.", "/../web"):
            h = make_handler("GET", path)
            h.do_GET()
            self.assertEqual(response_of(h)[0], 404, path)
        h = make_handler("GET", "/review-guard.js")
        h.do_GET()
        self.assertEqual(response_of(h)[0], 200)

    def test_disconnect_while_reading_request_body(self):
        class Boom(io.BytesIO):
            def read(self, *a):
                raise ConnectionResetError(104, "reset")
        h = make_handler("POST", "/api/review", headers={"Content-Length": "10",
                                                         "Content-Type": "multipart/form-data"})
        h.rfile = Boom()
        with captured_stderr() as err:
            h.do_POST()
        self.assertTrue(h.client_gone)
        self.assertEqual(h.wfile.writes, [])
        self.assertIn("request read", err.getvalue())

    def test_server_swallows_only_disconnects(self):
        server = site.ReviewServer.__new__(site.ReviewServer)
        with captured_stderr() as err:
            try:
                raise BrokenPipeError(32, "Broken pipe")
            except BrokenPipeError:
                server.handle_error(None, ("127.0.0.1", 1))
        self.assertIn("closed the connection", err.getvalue())
        with patch.object(site.ThreadingHTTPServer, "handle_error") as parent:
            try:
                raise ValueError("a real bug")
            except ValueError:
                server.handle_error(None, ("127.0.0.1", 1))
        parent.assert_called_once()


# ----------------------------------------------------------------- Milestone C

class AtomicWriteTests(unittest.TestCase):

    def test_successful_replacement(self):
        with temp_store(seed_json()) as store:
            site.save_checklist(good_checklist())
            saved = json.loads(store.read_text(encoding="utf-8"))["checklist"]
            leftovers = [p for p in store.parent.iterdir() if p.suffix == ".tmp"]
        self.assertEqual(saved["title"], "new")
        self.assertEqual(leftovers, [])

    def test_interruption_before_replacement_leaves_old_file_and_no_temp(self):
        with temp_store(seed_json()) as store, \
             patch.object(site.os, "fsync", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                site.save_checklist(good_checklist())
            saved = json.loads(store.read_text(encoding="utf-8"))["checklist"]
            leftovers = [p for p in store.parent.iterdir() if p.suffix == ".tmp"]
        self.assertEqual(saved["title"], "old")
        self.assertEqual(leftovers, [])

    def test_failed_replacement_leaves_old_file_and_no_temp(self):
        with temp_store(seed_json()) as store, \
             patch.object(site.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                site.save_checklist(good_checklist())
            saved = json.loads(store.read_text(encoding="utf-8"))["checklist"]
            leftovers = [p for p in store.parent.iterdir() if p.suffix == ".tmp"]
        self.assertEqual(saved["title"], "old")
        self.assertEqual(leftovers, [])

    def test_invalid_generated_checklist_is_refused_before_any_write(self):
        bad = [{"items": []},
               {"items": [{"criterion": "no id"}]},
               {"items": [{"id": "dup"}, {"id": "dup"}]},
               "not a dict"]
        with temp_store(seed_json()) as store:
            for checklist in bad:
                with self.assertRaises(ValueError):
                    site.save_checklist(checklist)
            with self.assertRaises(TypeError):  # not JSON-serialisable
                site.save_checklist({"items": [{"id": "a", "x": {1, 2}}]})
            saved = json.loads(store.read_text(encoding="utf-8"))["checklist"]
            leftovers = [p for p in store.parent.iterdir() if p.suffix == ".tmp"]
        self.assertEqual(saved["title"], "old")
        self.assertEqual(leftovers, [])

    def test_temp_file_is_created_beside_the_destination(self):
        seen = []
        real = site.tempfile.mkstemp

        def spy(*a, **k):
            seen.append(k.get("dir"))
            return real(*a, **k)
        with temp_store(seed_json()) as store, patch.object(site.tempfile, "mkstemp", spy):
            site.save_checklist(good_checklist())
        self.assertEqual(seen, [str(store.parent)])

    def test_corrupt_saved_checklist_is_quarantined_and_reported(self):
        with temp_store('{"checklist": {"items": [ truncated') as store:
            checklist, recovery = site.load_checklist_state()
            quarantined = [p for p in store.parent.iterdir() if ".corrupt-" in p.name]
            self.assertTrue(recovery)
            self.assertEqual(len(quarantined), 1)
            self.assertIn("truncated", quarantined[0].read_text(encoding="utf-8"))
            self.assertEqual(len(checklist["items"]), 49)  # built-in T3 seed restored
            payload = site.checklist_response(profile="t3")
        self.assertIn("recovery", payload)

    def test_valid_saved_checklist_is_never_rewritten_on_load(self):
        with temp_store(seed_json()) as store:
            before = store.stat().st_mtime_ns
            site.load_checklist_state()
            self.assertEqual(store.stat().st_mtime_ns, before)


# ----------------------------------------------------------------- Milestone D

class ArchiveGuardTests(unittest.TestCase):

    def assertRejected(self, raw, fragment):
        with self.assertRaises(ag.ArchiveRejected) as ctx:
            ag.validate_archive(raw)
        self.assertIn(fragment.lower(), str(ctx.exception).lower())

    def test_benign_highly_compressible_text_is_accepted(self):
        raw = zip_of([("task/README.md", "a" * (1024 * 1024)), ("task/task.toml", "x = 1\n")])
        members = ag.validate_archive(raw)  # ratio > 1000:1 but only 1 MiB
        self.assertEqual({m.name for m in members}, {"task/README.md", "task/task.toml"})
        site.zip_inventory(raw)  # and it stays reviewable

    def test_single_entry_zip_bomb_is_rejected(self):
        raw = zip_of([("task/bomb.bin", b"\0" * (4 * 1024 * 1024))])
        with patch.object(ag, "RATIO_ENTRY_FLOOR", 1024 * 1024):
            self.assertRejected(raw, "decompression bomb")

    def test_bomb_split_across_many_small_entries_is_rejected(self):
        raw = zip_of([(f"task/part{i}.bin", b"\0" * (1024 * 1024)) for i in range(6)])
        with patch.object(ag, "RATIO_ENTRY_FLOOR", 64 * 1024 * 1024), \
             patch.object(ag, "RATIO_TOTAL_FLOOR", 2 * 1024 * 1024):
            self.assertRejected(raw, "overall")

    def test_encrypted_entry_is_rejected(self):
        self.assertRejected(patch_flag(zip_of([("task/secret.txt", "x")]), 0x1), "encrypted")

    def test_unsupported_compression_method_is_rejected(self):
        raw = patch_method(zip_of([("task/a.txt", "hello")], zipfile.ZIP_STORED), 99)
        self.assertRejected(raw, "unsupported compression")

    def test_malformed_archive_is_rejected(self):
        self.assertRejected(b"this is not a zip file", "not a readable zip")
        truncated = zip_of([("task/a.txt", "hello" * 100)])[:-30]
        self.assertRejected(truncated, "not a readable zip")

    def test_duplicate_paths_are_rejected(self):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z, contextlib.suppress(UserWarning):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                z.writestr("task/a.txt", "one")
                z.writestr("task/a.txt", "two")
        self.assertRejected(b.getvalue(), "same path twice")

    def test_normalised_duplicates_are_rejected(self):
        self.assertRejected(zip_of([("task/a.txt", "1"), ("task/./a.txt", "2")]), "same path twice")

    def test_case_colliding_paths_are_rejected(self):
        self.assertRejected(zip_of([("task/Task.toml", "1"), ("task/task.toml", "2")]), "case")

    def test_unsafe_names_are_rejected(self):
        for name, fragment in (("../escape.txt", "escapes"),
                               ("task/../../escape.txt", "escapes"),
                               ("/etc/passwd", "absolute"),
                               ("C:/Windows/x.txt", "drive-letter"),
                               ("C:\\Windows\\x.txt", "drive-letter"),
                               ("task\\..\\..\\x.txt", "escapes"),
                               ("task/a\x01b.txt", "control"),
                               ("task/a\nb.txt", "control")):
            with self.subTest(name=name):
                self.assertRejected(zip_of([(name, "x")]), fragment)

    def test_nul_in_raw_archive_name_is_rejected_not_truncated(self):
        # zipfile truncates names at NUL when writing, so patch one into the raw headers.
        raw = zip_of([("task/aXb.txt", "x")]).replace(b"task/aXb.txt", b"task/a\x00b.txt")
        self.assertRejected(raw, "control")

    def test_backslash_separators_are_normalised_not_trusted(self):
        members = ag.validate_archive(zip_of([("task\\sub\\a.txt", "x")]))
        self.assertEqual(members[0].name, "task/sub/a.txt")

    def test_symlink_entry_is_rejected(self):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            info = zipfile.ZipInfo("task/link")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, "/etc/passwd")
        self.assertRejected(b.getvalue(), "symbolic link")

    def test_oversized_entry_is_rejected(self):
        raw = zip_of([("task/big.bin", os.urandom(2 * 1024 * 1024))])
        with patch.object(ag, "MAX_ENTRY_UNCOMPRESSED", 1024 * 1024):
            self.assertRejected(raw, "per-file limit")

    def test_excessive_entry_count_is_rejected(self):
        raw = zip_of([(f"task/f{i}.txt", "x") for i in range(11)])
        with patch.object(ag, "MAX_ARCHIVE_ENTRIES", 10):
            self.assertRejected(raw, "entries")

    def test_total_uncompressed_limit(self):
        raw = zip_of([(f"task/f{i}.bin", os.urandom(512 * 1024)) for i in range(4)])
        with patch.object(ag, "MAX_TOTAL_UNCOMPRESSED", 1024 * 1024):
            self.assertRejected(raw, "uncompressed")

    def test_upload_size_limit(self):
        raw = zip_of([("task/a.txt", "x")])
        with patch.object(ag, "MAX_UPLOAD_BYTES", 10):
            self.assertRejected(raw, "limit is")

    def test_work_budget(self):
        raw = zip_of([("task/a.txt", "x")])
        with self.assertRaises(ag.ArchiveRejected):
            ag.validate_archive(raw, deadline=0.0)

    def test_ratio_is_defined_for_zero_compressed_size(self):
        info = zipfile.ZipInfo("x")
        info.file_size, info.compress_size = 10, 0
        self.assertEqual(ag._ratio(info), 10.0)
        info.file_size = 0
        self.assertEqual(ag._ratio(info), 0.0)

    def test_oversized_text_is_listed_not_read(self):
        raw = zip_of([("task/log.txt", "y" * (3 * 1024 * 1024))])
        inv = site.zip_inventory(raw)
        entry = inv["files"][0]
        self.assertIn("read_error", entry)
        self.assertNotIn("content", entry)

    def test_hostile_archive_gets_a_400_not_a_traceback(self):
        boundary = "XyZ"
        form = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"checklist\"\r\n\r\n{{}}\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"profile\"\r\n\r\nt3\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"zip\"; filename=\"x.zip\"\r\n"
                f"Content-Type: application/zip\r\n\r\n").encode() + zip_of([("../evil", "x")]) + \
               f"\r\n--{boundary}--\r\n".encode()
        h = make_handler("POST", "/api/review", body=form,
                         headers={"Content-Length": str(len(form)),
                                  "Content-Type": f"multipart/form-data; boundary={boundary}"})
        with captured_stderr() as err:
            h.do_POST()
        status, body = response_of(h)
        self.assertEqual(status, 400)
        self.assertIn("escapes", body["error"])
        self.assertNotIn("Traceback", err.getvalue())

    def test_oversized_upload_is_refused_before_reading_the_body(self):
        h = make_handler("POST", "/api/review",
                         headers={"Content-Length": str(ag.MAX_UPLOAD_BYTES * 2),
                                  "Content-Type": "multipart/form-data; boundary=x"})
        h.rfile = io.BytesIO(b"")  # would be the huge body; never read
        h.do_POST()
        status, _ = response_of(h)
        self.assertEqual(status, 413)

    def test_real_task_packages_remain_reviewable(self):
        candidates = [GITHUB / "terminal-bench" / "tasks" / "foodstuff-beta-activity.zip",
                      GITHUB / "Snorkel Passed TB 2.0 - 340" / "Snorkel Passed TB 2.0 - 340" / "battleship.zip"]
        present = [p for p in candidates if p.is_file()]
        merged = GITHUB / "terminal-bench" / "tasks"
        if merged.is_dir():
            for task in ("uefi-bootkit", "atrx-vep-crispr"):  # worst ratio, largest total
                d = merged / task
                if d.is_dir():
                    b = io.BytesIO()
                    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
                        for f in sorted(d.rglob("*")):
                            if f.is_file():
                                z.write(f, f"{task}/{f.relative_to(d).as_posix()}")
                    present.append(b.getvalue())
        if not present:
            self.skipTest("no real task packages available")
        for item in present:
            raw = item.read_bytes() if isinstance(item, Path) else item
            with self.subTest(item=str(item)[:60] if isinstance(item, Path) else "merged task"):
                ag.validate_archive(raw)

    def test_inspection_never_writes_into_the_project(self):
        before = sorted(p.name for p in ROOT.iterdir())
        raw = zip_of([("task/task.toml", "x = 1\n"), ("task/terminus_checklist_site.py", "print(1)")])
        with patch.object(site, "run_ollama", side_effect=RuntimeError("stub")):
            site.review_zip(raw, site.source_supported_checklist(), "m", "t.zip", profile="t3")
        self.assertEqual(sorted(p.name for p in ROOT.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
