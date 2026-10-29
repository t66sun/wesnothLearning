"""Tests for the archive replay fetcher: listing, resume, failure reporting.

A local HTTP server stands in for replays.wesnoth.org, serving an Apache-like
month/day tree of bz2 replays. No network access and no real Wesnoth data.
"""
from __future__ import annotations

import bz2
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import unquote

from learning.replay_fetch import (day_files, local_name, main, month_days,
                                   sync_month, valid, verify_month)

BODY = ('version="1.18.8"\ncampaign_type="multiplayer"\n'
        '[replay]\n[command]\n[end_turn]\n[/end_turn]\n[/command]\n[/replay]\n')
ROOT = "1.18"


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(directory, drop=""):
    """Serve `directory`; requests whose path ends with `drop` answer 404.

    The dropped file stays in the listing, which is the archive behavior that
    must be reported instead of skipped.
    """
    class Handler(Quiet):
        def send_head(self):
            if drop and unquote(self.path).endswith(drop):
                self.send_error(404, "gone")
                return None
            return super().send_head()

    server = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: Handler(
        *a, directory=str(directory), **k))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/1.18"


def archive(root, days):
    """Write a month tree: {day: [href, ...]} with bz2 payloads."""
    month = Path(root) / ROOT / "2026" / "07"
    for day, hrefs in days.items():
        (month / f"{day:02d}").mkdir(parents=True, exist_ok=True)
        for href in hrefs:
            (month / f"{day:02d}" / local_name(href)).write_bytes(bz2.compress(BODY.encode()))


DAYS = {1: ["Afterlife_Turn_1_(24694).bz2",
            "WC_II_2_-__+%23textdomain_wesnoth-wc_Start_Turn_6_(24672).bz2"],
        2: ["2p_-_Micro_Isar_Turn_10_(24197).bz2"]}


class ReplayFetchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.www = self.root / "www"
        archive(self.www, DAYS)
        self.servers = []
        self.start()
        self.out = self.root / "replays" / "202607"

    def start(self, drop=""):
        server, base = serve(self.www, drop)
        self.servers.append(server)
        self.base = base

    def tearDown(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()
        self.tmp.cleanup()

    def test_month_provisions_every_listed_replay(self):
        report = sync_month(self.base, self.out, 2026, 7, workers=4, log=lambda _m: None, delay=0)
        self.assertEqual(report["days"], [1, 2])
        self.assertEqual(report["listed"], 3)
        self.assertEqual(report["downloaded"], 3)
        self.assertEqual(report["failed"], [])
        self.assertEqual(report["failed_days"], [])
        names = sorted(p.name for p in self.out.rglob("*.bz2"))
        self.assertEqual(names, ["2p_-_Micro_Isar_Turn_10_(24197).bz2",
                                 "Afterlife_Turn_1_(24694).bz2",
                                 "WC_II_2_-__+#textdomain_wesnoth-wc_Start_Turn_6_(24672).bz2"])
        self.assertTrue(all(valid(p) for p in self.out.rglob("*.bz2")))
        self.assertEqual(list(self.out.rglob("*.part")), [])

    def test_resume_keeps_complete_files_and_refetches_truncated_ones(self):
        day = self.out / "01"
        day.mkdir(parents=True)
        keep = day / "Afterlife_Turn_1_(24694).bz2"
        keep.write_bytes(bz2.compress(BODY.encode()))
        truncated = day / "WC_II_2_-__+#textdomain_wesnoth-wc_Start_Turn_6_(24672).bz2"
        truncated.write_bytes(bz2.compress(BODY.encode())[:-6])

        report = sync_month(self.base, self.out, 2026, 7, workers=4, log=lambda _m: None, delay=0)

        self.assertEqual(report["kept"], 1)
        self.assertEqual(report["downloaded"], 2)
        self.assertTrue(valid(truncated))
        self.assertEqual(truncated.read_bytes(), bz2.compress(BODY.encode()))
        self.assertTrue(valid(self.out / "02" / "2p_-_Micro_Isar_Turn_10_(24197).bz2"))

    def test_unreachable_file_is_reported_not_skipped(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()
        self.servers = []
        self.start(drop="2p_-_Micro_Isar_Turn_10_(24197).bz2")

        report = sync_month(self.base, self.out, 2026, 7, workers=2, log=lambda _m: None, delay=0)

        self.assertEqual(report["downloaded"], 2)
        self.assertEqual(len(report["failed"]), 1)
        self.assertIn("2p_-_Micro_Isar_Turn_10_(24197).bz2", report["failed"][0])
        self.assertFalse((self.out / "02" / "2p_-_Micro_Isar_Turn_10_(24197).bz2").exists())

    def test_unreachable_month_reports_the_day_listing_failure(self):
        report = sync_month(f"{self.base}/missing", self.out, 2026, 7, workers=2, log=lambda _m: None, delay=0)
        self.assertEqual(report["days"], [])
        self.assertEqual(report["failed_days"], ["2026-07"])
        self.assertEqual(report["listed"], 0)

    def test_verify_reports_missing_truncated_and_unexpected_files(self):
        sync_month(self.base, self.out, 2026, 7, workers=2, log=lambda _m: None, delay=0)
        (self.out / "02" / "2p_-_Micro_Isar_Turn_10_(24197).bz2").unlink()
        (self.out / "01" / "Afterlife_Turn_1_(24694).bz2").write_bytes(
            bz2.compress(BODY.encode())[:-6])
        (self.out / "01" / "stray.bz2").write_bytes(bz2.compress(b"x"))
        problems = verify_month(self.base, self.out, 2026, 7, workers=2, log=lambda _m: None, delay=0)
        self.assertIn("day 02/2p_-_Micro_Isar_Turn_10_(24197).bz2: missing", problems)
        self.assertIn("day 01/Afterlife_Turn_1_(24694).bz2: not a complete bz2", problems)
        self.assertIn("day 01/stray.bz2: unexpected", problems)

    def test_listings_decode_days_and_percent_encoded_names(self):
        self.assertEqual(month_days(self.base, 2026, 7), [1, 2])
        self.assertEqual(sorted(local_name(href) for href in day_files(self.base, 2026, 7, 1)),
                         sorted(local_name(href) for href in DAYS[1]))
        self.assertEqual(local_name("WC_II_2_-__+%23textdomain_wesnoth-wc_Start_Turn_6_(24672).bz2"),
                         "WC_II_2_-__+#textdomain_wesnoth-wc_Start_Turn_6_(24672).bz2")
        self.assertEqual(local_name("a:b*b.bz2"), "a_b_b.bz2")

    def test_cli_provisions_then_verifies_the_requested_directory(self):
        out = self.root / "cli" / "202607"
        code = main(["--month", "2026-07", "--out", str(out), "--base", self.base,
                     "--workers", "2"])
        self.assertEqual(code, 0)
        self.assertEqual(len(list(out.rglob("*.bz2"))), 3)
        self.assertEqual(main(["--month", "2026-07", "--out", str(out), "--base",
                               self.base, "--verify"]), 0)
        (out / "02" / "2p_-_Micro_Isar_Turn_10_(24197).bz2").unlink()
        self.assertEqual(main(["--month", "2026-07", "--out", str(out), "--base",
                               self.base, "--verify"]), 1)


if __name__ == "__main__":
    unittest.main()
