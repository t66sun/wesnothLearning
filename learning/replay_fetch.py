"""Fetch whole-month replay archives from replays.wesnoth.org into data/replays.

One month of the public 1.18 archive is fetched day by day, into the existing
`data/replays/<YYYYMM>/<DD>/` layout, so a run can be resumed and re-verified at
any time. Each download is written to a `.part` file and renamed into place, so
an interrupted transfer never leaves a plausible-looking replay behind; a file
that is already present is kept only if it decompresses completely, which
re-fetches the truncated transfers earlier bulk runs produced.

    python -m learning.replay_fetch --month 2026-07
    python -m learning.replay_fetch --month 2026-07 --month 2026-08 --verify

This provisions captured inputs only: nothing here parses replay content, and
an unreachable day or a failed transfer is reported as a failure, never as a
pass.
"""
from __future__ import annotations

import argparse
import bz2
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import sys
import time
from urllib.parse import unquote
from urllib.request import Request, urlopen

BASE = "https://replays.wesnoth.org/1.18"
USER_AGENT = "WesnothLearning-replay-fetch/1.0"
DAYS = re.compile(r'href="(\d{2})/"')
FILES = re.compile(r'href="([^"?]+\.bz2)"')
UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def get_text(url, tries=6, timeout=90, delay=3):
    """Read one listing, retrying the resets the archive host sends under load."""
    for attempt in range(tries):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as reply:
                return reply.read().decode("utf-8", "replace")
        except Exception:
            if attempt == tries - 1:
                return None
            time.sleep(delay * (attempt + 1))
    return None


def month_days(base, year, month, delay=3):
    """Days the archive lists for a month; empty when the month is unreachable."""
    text = get_text(f"{base}/{year}/{month:02d}/", delay=delay)
    return sorted({int(d) for d in DAYS.findall(text or "")})


def day_files(base, year, month, day, delay=3):
    """Replay hrefs the archive lists for one day; None when the day fails."""
    text = get_text(f"{base}/{year}/{month:02d}/{day:02d}/", delay=delay)
    if text is None:
        return None
    return sorted(set(FILES.findall(text)))


def local_name(href):
    """Archive href to a local filename: percent-decoded, Windows-legal."""
    return UNSAFE.sub("_", unquote(href))


def valid(path):
    """True when the file is a complete bz2 stream with content.

    Truncated transfers keep the bz2 header and lose the end-of-stream marker,
    so the magic alone would accept them.
    """
    try:
        reader = bz2.BZ2Decompressor()
        written = 0
        with Path(path).open("rb") as handle:
            while True:
                chunk = handle.read(1 << 20)
                if not chunk:
                    break
                written += len(reader.decompress(chunk))
        return reader.eof and written > 0
    except Exception:
        return False


def fetch_one(base, year, month, day, href, target, tries=6, delay=2):
    """Download one replay to `target`; returns (status, bytes)."""
    url = f"{base}/{year}/{month:02d}/{day:02d}/{href}"
    for attempt in range(tries):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as reply:
                data = reply.read()
            if not data.startswith(b"BZh"):
                raise ValueError("response is not bz2")
            partial = target.with_name(target.name + ".part")
            partial.write_bytes(data)
            os.replace(partial, target)
            return ("ok", len(data))
        except Exception as error:
            if attempt == tries - 1:
                return (f"error: {error}", 0)
            time.sleep(delay * (attempt + 1))
    return ("error: retries exhausted", 0)


def sync_month(base, out, year, month, workers=16, log=print, delay=3):
    """Provision one month into `out`; returns a report dict."""
    out = Path(out)
    days = month_days(base, year, month, delay=delay)
    report = {"year": year, "month": month, "directory": str(out), "days": days,
              "listed": 0, "kept": 0, "downloaded": 0, "failed": [], "bytes": 0,
              "failed_days": []}
    if not days:
        report["failed_days"].append(f"{year}-{month:02d}")
        log(f"{year}-{month:02d}: archive listing unreachable")
        return report
    jobs = []
    for day in days:
        hrefs = day_files(base, year, month, day, delay=delay)
        if hrefs is None:
            report["failed_days"].append(f"{year}-{month:02d}-{day:02d}")
            log(f"  day {day:02d}: listing failed")
            continue
        target_dir = out / f"{day:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)
        present = {path.name: path for path in target_dir.iterdir() if path.is_file()}
        for href in hrefs:
            name = local_name(href)
            report["listed"] += 1
            existing = present.get(name)
            if existing is not None and valid(existing):
                report["kept"] += 1
                report["bytes"] += existing.stat().st_size
            else:
                if existing is not None:
                    existing.unlink()
                jobs.append((day, href, target_dir / name))
        log(f"  day {day:02d}: {len(hrefs)} listed")
    log(f"{year}-{month:02d}: {report['listed']} listed, {report['kept']} already valid, "
        f"{len(jobs)} to download")
    if not jobs:
        return report
    started = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_one, base, year, month, day, href, target, delay=delay)
                   for day, href, target in jobs]
        for index, future in enumerate(futures, 1):
            status, size = future.result()
            day, href, target = jobs[index - 1]
            if status == "ok":
                report["downloaded"] += 1
                report["bytes"] += size
            else:
                report["failed"].append(f"{day:02d}/{target.name}: {status}")
            if index % 500 == 0 or index == len(jobs):
                log(f"  [{index}/{len(jobs)}] ok={report['downloaded']} "
                    f"failed={len(report['failed'])} {report['bytes']/1e6:.1f}MB "
                    f"{time.time()-started:.0f}s")
    return report


def verify_month(base, out, year, month, workers=8, log=print, delay=3):
    """Compare a provisioned month against the archive and decompress it all."""
    out = Path(out)
    problems = []
    days = month_days(base, year, month, delay=delay)
    if not days:
        return [f"{year}-{month:02d}: archive listing unreachable"]
    checked = 0
    for day in days:
        hrefs = day_files(base, year, month, day, delay=delay)
        if hrefs is None:
            problems.append(f"day {day:02d}: listing failed")
            continue
        expected = {local_name(href) for href in hrefs}
        directory = out / f"{day:02d}"
        actual = ({path.name for path in directory.iterdir() if path.is_file()}
                  if directory.is_dir() else set())
        for name in sorted(expected - actual):
            problems.append(f"day {day:02d}/{name}: missing")
        for name in sorted(actual - expected):
            problems.append(f"day {day:02d}/{name}: unexpected")
        files = sorted(path for path in directory.iterdir() if path.is_file()) \
            if directory.is_dir() else []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for path, ok in zip(files, pool.map(valid, files)):
                checked += 1
                if not ok:
                    problems.append(f"day {day:02d}/{path.name}: not a complete bz2")
        log(f"  day {day:02d}: listed={len(expected)} local={len(files)} problems={len(problems)}")
    log(f"{year}-{month:02d}: {checked} files decompressed, {len(problems)} problems")
    return problems


def parse_month(text):
    """'YYYY-MM' to (year, month)."""
    match = re.fullmatch(r"(\d{4})-(\d{1,2})", text.strip())
    if match is None:
        raise argparse.ArgumentTypeError(f"month must look like 2026-07, got {text!r}")
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        raise argparse.ArgumentTypeError(f"month out of range in {text!r}")
    return year, month


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--month", action="append", type=parse_month, required=True,
                        metavar="YYYY-MM", help="archive month to provision; repeatable")
    parser.add_argument("--out", type=Path, default=None,
                        help="output directory; default data/replays/<YYYYMM>")
    parser.add_argument("--base", default=BASE, help="archive root, default %(default)s")
    parser.add_argument("--workers", type=int, default=16, help="parallel transfers, default %(default)s")
    parser.add_argument("--verify", action="store_true",
                        help="check an already provisioned month instead of downloading")
    args = parser.parse_args(argv)
    failed = False
    for year, month in args.month:
        out = args.out or Path("data") / "replays" / f"{year}{month:02d}"
        if args.verify:
            problems = verify_month(args.base, out, year, month)
            for problem in problems[:20]:
                print(f"  ! {problem}")
            failed = failed or bool(problems)
            continue
        report = sync_month(args.base, out, year, month, workers=args.workers)
        print(f"{year}-{month:02d}: listed={report['listed']} kept={report['kept']} "
              f"downloaded={report['downloaded']} failed={len(report['failed'])} "
              f"{report['bytes']/1e6:.1f}MB -> {report['directory']}")
        for line in report["failed"][:20]:
            print(f"  ! {line}")
        failed = failed or bool(report["failed"] or report["failed_days"] or not report["listed"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
