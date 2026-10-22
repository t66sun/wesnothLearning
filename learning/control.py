"""Per-format reward controls; all changes become effective at batch boundaries.

Metrics supplied to boundary are incremental, fault-free training/validation
evidence. Final holdout measurements are rejected for automatic tuning.
"""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
import uuid

from .rewards import RewardConfig, RANGES

FORMATS = ('duel', 'ffa4', 'team2v2')
MUTABLE = {'economy', 'control', 'explore', 'mode', 'entropy', 'bc_aux'}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _read(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def _atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            name = stream.name
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(6):
            try:
                os.replace(name, path)
                break
            except PermissionError:
                # Windows scanners can briefly hold a newly replaced file.
                if os.name != 'nt' or attempt == 5:
                    raise
                time.sleep(.02 * (attempt + 1))
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


@contextmanager
def _locked(directory):
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / '.write-lock'
    deadline = time.monotonic() + 5
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f'control writer lock is busy: {lock}')
            time.sleep(.025)
    try:
        yield
    finally:
        lock.rmdir()


def _events(directory):
    path = directory / 'events.jsonl'
    rows, previous = [], None
    if path.exists():
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            try:
                row = json.loads(line)
                body = {k: v for k, v in row.items() if k != 'checksum'}
                if row['seq'] != number or row['previous'] != previous or row['checksum'] != _digest(body):
                    raise ValueError('event sequence/checksum mismatch')
                if row['format'] not in FORMATS:
                    raise ValueError('invalid event format')
                old, new = RewardConfig(**row['old']), RewardConfig(**row['new'])
                if new.reward_version != old.reward_version + 1:
                    raise ValueError('nonsequential reward version')
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f'invalid control event line {number}: {exc}') from exc
            previous = row['checksum']
            rows.append(row)
    return rows


def _changed(config, changes):
    unknown = set(changes) - MUTABLE
    if unknown:
        raise ValueError(f'unsupported control fields: {sorted(unknown)}')
    if not changes:
        raise ValueError('empty control change')
    return replace(config, **changes)


def _validate_command(config, command):
    if command['source'] not in ('manual', 'adaptive', 'scheduled') or not command['reason'] or not command.get('id'):
        raise ValueError('invalid control provenance')
    candidate = _changed(config, command['changes'])
    if command['source'] == 'adaptive':
        for name in RANGES:
            before, after = getattr(config, name), getattr(candidate, name)
            if not before * .9 - 1e-12 <= after <= before * 1.1 + 1e-12:
                raise ValueError('adaptive change exceeds 10 percent')
    return candidate


def queue_control(run_dir, format_name, changes, *, source='manual', reason='manual control', command_id=None):
    """Validate and atomically queue one complete command, never alter a live game."""
    if format_name not in FORMATS:
        raise ValueError('unknown format')
    if source not in ('manual', 'adaptive', 'scheduled') or not reason:
        raise ValueError('control source/reason required')
    directory = Path(run_dir) / 'control'
    with _locked(directory):
        events = _events(directory)
        if command_id is not None:
            existing = next((event for event in events if event.get('command_id') == command_id), None)
            if existing is not None:
                return existing
        state = _read(directory / f'{format_name}.json', {})
        config = RewardConfig(**state.get('config', {}))
        for event in events:
            if event['format'] == format_name:
                config = RewardConfig(**event['new'])
        path = directory / f'{format_name}.pending.json'
        pending = _read(path, [])
        if command_id is not None:
            existing = next((command for command in pending if command.get('id') == command_id), None)
            if existing is not None:
                return existing
        for command in pending:
            config = _changed(config, command['changes'])
        command = dict(id=command_id or uuid.uuid4().hex, changes=dict(changes), source=source, reason=reason, queued_at=time.time())
        _validate_command(config, command)
        pending.append(command)
        _atomic(path, pending)
        return command


def show_control(run_dir, format_name=None):
    directory = Path(run_dir) / 'control'
    if format_name is not None and format_name not in FORMATS:
        raise ValueError('unknown format')
    with _locked(directory):
        events = _events(directory)
        result = {}
        for fmt in (FORMATS if format_name is None else [format_name]):
            state = _read(directory / f'{fmt}.json', {})
            config = state.get('config', RewardConfig().to_dict())
            for event in events:
                if event['format'] == fmt:
                    config = event['new']
            result[fmt] = dict(config=config, pending=_read(directory / f'{fmt}.pending.json', []),
                               applied_event_seq=state.get('cursor', 0), last_error=state.get('last_error'))
        return result


class RewardController:
    def __init__(self, run_dir, format_name, state=None, config=None, schedule=None):
        if format_name not in FORMATS:
            raise ValueError('unknown format')
        self.run_dir, self.format = Path(run_dir), format_name
        self.directory = self.run_dir / 'control'
        self.schedule = schedule or []
        saved = state if state is not None else _read(self.directory / f'{format_name}.json', {})
        initial = dict(saved.get('config') or config or {})
        if schedule and config is None and not saved.get('config'):
            initial.setdefault('mode', 'scheduled')
        self.config = RewardConfig(**initial)
        self.cursor = saved.get('cursor', 0)
        self.last_check = saved.get('last_check', 0)
        self.games = saved.get('games', 0)
        self.blocks = saved.get('blocks', [])
        self.seen_blocks = set(saved.get('seen_blocks', []))
        self.windows = saved.get('windows', [])
        self.control_previous = saved.get('control_previous')
        self.last_error = saved.get('last_error')
        self.applied_schedule = set(saved.get('applied_schedule', []))
        with _locked(self.directory):
            self._replay(_events(self.directory))
            self._save()

    def _replay(self, events):
        if self.cursor > len(events):
            raise ValueError('checkpoint control cursor is ahead of event log')
        for event in events:
            if event['seq'] <= self.cursor or event['format'] != self.format:
                continue
            if event['old'] != self.config.to_dict():
                raise ValueError('control checkpoint does not match event chain')
            if event['source'] == 'adaptive' and event['new']['control'] > event['old']['control']:
                if self.control_previous is None:
                    self.control_previous = event['old']['control']
            elif event['source'] == 'adaptive' and event['new']['control'] < event['old']['control']:
                self.control_previous = None
            self.config = RewardConfig(**event['new'])
        self.cursor = len(events)

    def freeze(self):
        """Copy this into every game/job and keep it for its entire trajectory."""
        return self.config.to_dict()

    def state_dict(self):
        return dict(config=self.freeze(), cursor=self.cursor, last_check=self.last_check,
                    games=self.games, blocks=self.blocks, seen_blocks=sorted(self.seen_blocks),
                    windows=self.windows, control_previous=self.control_previous,
                    last_error=self.last_error, applied_schedule=sorted(self.applied_schedule))

    def _save(self):
        _atomic(self.directory / f'{self.format}.json', self.state_dict())

    def _apply_pending(self, batch):
        path = self.directory / f'{self.format}.pending.json'
        with _locked(self.directory):
            events = _events(self.directory)
            self._replay(events)
            applied_ids = {event.get('command_id') for event in events}
            pending = [command for command in _read(path, []) if command.get('id') not in applied_ids]
            # Validate every queued command before appending any application.
            try:
                candidate = self.config
                for command in pending:
                    candidate = _validate_command(candidate, command)
            except (ValueError, TypeError, KeyError) as exc:
                self.last_error = str(exc)
                _atomic(path, [])
                self._save()
                return
            for command in pending:
                next_config = replace(_changed(self.config, command['changes']), reward_version=self.config.reward_version + 1)
                body = dict(seq=len(events) + 1, previous=events[-1]['checksum'] if events else None,
                            format=self.format, old=self.freeze(), new=next_config.to_dict(),
                            source=command['source'], reason=command['reason'], batch=batch,
                            command_id=command['id'],
                            queued_at=command['queued_at'], applied_at=time.time())
                event = dict(body, checksum=_digest(body))
                with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(event, sort_keys=True, allow_nan=False) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                events.append(event)
                self._replay(events)
                self.last_error = None
            if path.exists():
                _atomic(path, [])
            self._save()

    def _ingest(self, metrics):
        if metrics.get('partition') in ('holdout', 'test', 'final'):
            raise ValueError('final holdout cannot tune rewards')
        self.games += max(0, int(metrics.get('new_games', 0)) - int(metrics.get('faulted_games', 0)))
        for block in metrics.get('validation_blocks', []):
            key = str(block['id'])
            if key in self.seen_blocks or not block.get('complete') or block.get('faults'):
                continue
            if block.get('partition') in ('holdout', 'test', 'final'):
                raise ValueError('final holdout cannot tune rewards')
            self.seen_blocks.add(key)
            self.blocks.append(block)

    @staticmethod
    def _window(blocks):
        # Match each map/faction to its own Astra reference, then give strata
        # equal weight. Sampling a large easy map cannot dominate this panel.
        strata = {}
        for block in blocks:
            for row in block.get('strata', []):
                key = (row['map'], row['faction'])
                strata.setdefault(key, []).append(row)
        if not strata:
            return None
        low_explore, met_explore, low_control, safe = [], [], [], []
        for rows in strata.values():
            def average(name):
                values = [float(row[name]) for row in rows]
                if not all(math.isfinite(v) for v in values):
                    raise ValueError('nonfinite controller metric')
                return sum(values) / len(values)
            ratios = [average(f'coverage{turn}') / max(1e-9, average(f'astra_coverage{turn}')) for turn in (5, 10)]
            low_explore.append(all(ratio < .9 for ratio in ratios))
            met_explore.append(all(ratio >= .9 for ratio in ratios))
            low_control.append(average('control') < .8 * average('astra_control'))
            safe.append(average('leader_survival') >= average('astra_leader_survival') and average('loss') <= average('astra_loss'))
        def score(name):
            values = [float(block[name]) for block in blocks if block.get(name) is not None]
            if not all(math.isfinite(v) for v in values):
                raise ValueError('nonfinite score')
            return sum(values) / len(values) if values else None
        return dict(low_explore=all(low_explore), met_explore=all(met_explore),
                    low_control=all(low_control), safe=all(safe),
                    fixed_score=score('fixed_score'), native_score=score('native_score'),
                    control=sum(float(row['control']) for rows in strata.values() for row in rows) / sum(map(len, strata.values())),
                    strata=sorted('|'.join(key) for key in strata))

    def _decision(self, metrics):
        while len(self.blocks) >= 12 and len(self.windows) < 3:
            blocks, self.blocks = self.blocks[:12], self.blocks[12:]
            window = self._window(blocks)
            if window is None:
                return {}, 'missing Astra calibration'
            self.windows.append(window)
            self.windows = self.windows[-3:]
        if len(self.windows) < 2:
            return {}, 'insufficient rotation blocks'
        window = self.windows[-1]
        if self.windows[-2]['strata'] != window['strata']:
            return {}, 'need two comparable windows'
        previous = self.windows[-2]
        changes, reasons = {}, []
        if all(w['low_explore'] and w['safe'] for w in (previous, window)):
            changes['explore'] = self.config.explore * 1.1
            reasons.append('coverage below 90% Astra without survival/loss regression')
        elif len(self.windows) >= 3 and all(w['met_explore'] for w in self.windows):
            changes['explore'] = self.config.explore * .9
            reasons.append('coverage maintained across three windows')
        if all(w['low_control'] for w in (previous, window)):
            changes['control'] = self.config.control * 1.1
            reasons.append('control below 80% Astra in two windows')
        # Two successive score declines need three windows (each >=12 blocks).
        if self.control_previous is not None and len(self.windows) == 3:
            for name in ('fixed_score', 'native_score'):
                values = [w[name] for w in self.windows]
                controls = [w['control'] for w in self.windows]
                if all(v is not None for v in values) and values[2] < values[1] < values[0] and controls[2] > controls[1] > controls[0]:
                    changes['control'] = max(self.config.control * .9, self.control_previous)
                    reasons.append(f'rollback control after two {name} declines')
                    break
        shaping, terminal = metrics.get('shaping_rms'), metrics.get('terminal_rms')
        if shaping is not None and terminal is not None and math.isfinite(shaping) and math.isfinite(terminal) and shaping > 2 * max(terminal, 1e-9):
            changes['economy'] = self.config.economy * .9
            reasons.append('shaping RMS exceeds twice terminal RMS')
        for name in list(changes):
            lo, hi = RANGES[name]
            current = getattr(self.config, name)
            changes[name] = min(hi, current * 1.1, max(lo, current * .9, changes[name]))
            if abs(changes[name] - getattr(self.config, name)) < 1e-12:
                del changes[name]
        return changes, '; '.join(reasons)

    def boundary(self, batch, metrics=None):
        """Call after the previous collection/update finishes, before next jobs.

        `new_games` is an incremental count. validation_blocks have globally
        unique IDs, complete rotation flags and per-map/faction `strata` rows.
        See REWARD_TEST_SCOPE.md for the evidence contract and future checks.
        """
        if type(batch) is not int or batch < 0:
            raise ValueError('invalid batch')
        self._apply_pending(batch)
        metrics = metrics or {}
        self._ingest(metrics)
        if self.config.mode == 'scheduled':
            for index, item in enumerate(self.schedule):
                if index not in self.applied_schedule and batch >= item['batch']:
                    command_id = _digest(dict(format=self.format, schedule_index=index, item=item))
                    queue_control(self.run_dir, self.format, item['changes'], source='scheduled', reason=f'schedule {index}', command_id=command_id)
                    self.applied_schedule.add(index)
        elif self.config.mode == 'adaptive' and batch - self.last_check >= 50 and self.games >= 64:
            self.last_check = batch
            changes, reason = self._decision(metrics)
            if changes:
                command_id = _digest(dict(format=self.format, batch=batch, changes=changes, source='adaptive'))
                queue_control(self.run_dir, self.format, changes, source='adaptive', reason=reason, command_id=command_id)
            self.games = 0
        self._apply_pending(batch)
        return self.freeze()
