"""Frozen engine workload manifests and measured-only performance acceptance.

Runners own actual process-tree instrumentation. This module never infers CPU
from wall time, substitutes RSS for PSS, or treats missing measurements as passes.
"""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random

from .formats import FORMATS, PLAYERS
from .features import VERSION


COMPONENTS = ('rules', 'visibility_pathfinding', 'candidates', 'teacher', 'inference', 'serialization', 'logging')
MAPS = dict(duel=('The Freelands', 'Weldyn Channel', 'Sablestone Delta'),
    ffa4=('Clash', "Isar's Cross"), team2v2=('Clash', "Isar's Cross"))
MEASUREMENTS = ('wall_seconds', 'cpu_core_seconds', 'peak_rss_bytes', 'peak_pss_bytes',
    'disk_bytes', 'startup_seconds')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def build_manifest(artifacts=None):
    """A fixed 30-block, full-seat rotation per format/cache/workload/scenario.

    Artifacts must bind native executable, lite rules, Astra and all three V4
    models by SHA256 before acceptance. Missing artifacts keep status pending.
    Equivalent scripts supply a common snapshot/script/injected-hit hash.
    """
    workloads = []
    for fmt in FORMATS:
        for cache in ('cold', 'hot'):
            for mode in ('equal_work', 'end_to_end'):
                for density in ('regular', 'dense'):
                    for block in range(30):
                        for seat in range(1, PLAYERS[fmt] + 1):
                            work = dict(format=fmt, cache=cache, mode=mode, density=density,
                                block=block, seat=seat, seed=190000 + block,
                                map=MAPS[fmt][block % len(MAPS[fmt])],
                                workers=1, inference='cpu', threads=1, turn_limit=30,
                                factions_rotation=block % 6, teammate_context='astra_partner' if fmt == 'team2v2' else 'none')
                            work['id'] = _digest(work)
                            workloads.append(work)
    manifest = dict(version=1, native_version='1.18.8', observation_schema=VERSION,
        minimum_complete_rotation_blocks=30, required_speedup=5, required_cpu_ratio=5,
        resource_memory_ratio_target=1.3, artifacts=artifacts or {}, workloads=workloads,
        cpu_scope='all game/host/inference processes plus coordination',
        cache_contract='cold: fresh process and declared cold caches; hot: warmed resident process, aligned engine caches',
        equal_work_contract='identical map/state/script/injected outcomes, action count and turns',
        acceptance='single-worker CPU cold and hot, each format and density separately; wall and CPU each >=5x; peak PSS native/lite >=1.3 (lite memory at least 30% lower); 4/8 workers are secondary')
    manifest['manifest_id'] = _digest(manifest)
    return manifest


def freeze_artifacts(paths):
    """Bind actual files, without rewriting or executing historical artifacts."""
    return {name: dict(path=str(Path(path).resolve()), sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
            for name, path in paths.items()}


def _percentile(values, percentile):
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * percentile
    lo = int(index)
    return values[lo] + (values[min(lo + 1, len(values)-1)] - values[lo]) * (index - lo)


def _summary(values):
    return dict(samples=len(values), p50=_percentile(values, .50), p95=_percentile(values, .95),
                total=sum(values) if values else None)


def _interval(block_ratios, seed=19):
    if len(block_ratios) < 2:
        return None
    rng = random.Random(seed)
    samples = []
    for _ in range(2000):
        chosen = rng.choices(block_ratios, k=len(block_ratios))
        samples.append(sum(a for a, _ in chosen) / sum(b for _, b in chosen))
    return [_percentile(samples, .025), _percentile(samples, .975)]


def benchmark_report(raw_samples, manifest=None):
    manifest = manifest or build_manifest()
    expected = {work['id']: work for work in manifest['workloads']}
    grouped = defaultdict(dict)
    failures = []
    timing_gaps = []
    seen = set()
    for sample in raw_samples:
        row = dict(sample)
        work = expected.get(row.get('workload_id'))
        if work is None:
            failures.append(dict(reason='unknown_workload', workload_id=row.get('workload_id')))
            continue
        engine = row.get('engine')
        if engine not in ('native', 'lite'):
            failures.append(dict(reason='unknown_engine', workload_id=work['id']))
            continue
        identity = work['id'], engine
        if identity in seen:
            failures.append(dict(reason='duplicate_sample', workload_id=work['id'], engine=engine))
            continue
        seen.add(identity)
        reasons = []
        if row.get('manifest_id') != manifest['manifest_id']:
            reasons.append('manifest_mismatch')
        if row.get('faults'):
            reasons.append('faulted_game')
        if any(not isinstance(row.get(k), (float, int)) or not math.isfinite(row[k]) or row[k] < 0 for k in MEASUREMENTS):
            reasons.append('missing_or_invalid_resources')
        elif any(row[k] <= 0 for k in ('wall_seconds', 'cpu_core_seconds', 'peak_rss_bytes', 'peak_pss_bytes')):
            reasons.append('nonpositive_required_resources')
        if row.get('cpu_scope') != 'process_tree_including_coordinator':
            reasons.append('incomplete_cpu_scope')
        if not row.get('host_id') or row.get('cpu_quota') is None:
            reasons.append('missing_host_or_quota')
        if row.get('workers') != work['workers'] or row.get('inference') != 'cpu' or row.get('threads') != work['threads']:
            reasons.append('execution_configuration_mismatch')
        components = row.get('components_seconds') or {}
        absent = [k for k in COMPONENTS if not isinstance(components.get(k), (int, float))
                  or not math.isfinite(components[k]) or components[k] < 0]
        if absent:
            timing_gaps.append(dict(workload_id=work['id'], engine=engine, missing=absent))
        row['components_seconds'] = {k: components.get(k) if k not in absent else None for k in COMPONENTS}
        if any(not isinstance(row.get(k), int) or row[k] <= 0 for k in ('actions', 'turns')):
            reasons.append('missing_actual_work_counts')
        if not row.get('terminal_reason'):
            reasons.append('missing_terminal_reason')
        elif work.get('mode') == 'end_to_end' and row['terminal_reason'] == 'decision_limit':
            reasons.append('incomplete_end_to_end_game')
        if not row.get('cache_aligned'):
            reasons.append('unverified_cache_state')
        if reasons:
            failures.append(dict(reason=reasons, workload_id=work['id'], engine=engine))
            continue
        key = tuple(work[k] for k in ('format', 'cache', 'mode', 'density', 'workers'))
        grouped[key][(work['block'], work['seat'], engine)] = row
    reports = []
    required = sorted({tuple(w[k] for k in ('format', 'cache', 'mode', 'density', 'workers')) for w in expected.values()})
    for key in required:
        fmt, cache, mode, density, workers = key
        rows = grouped[key]
        complete, missing, mismatched = [], [], []
        wall_blocks, cpu_blocks = [], []
        memory_blocks = []
        for block in range(30):
            pairs = [(rows.get((block, seat, 'native')), rows.get((block, seat, 'lite')))
                     for seat in range(1, PLAYERS[fmt] + 1)]
            if any(a is None or b is None for a, b in pairs):
                missing.append(block)
                continue
            mismatch = any(a['host_id'] != b['host_id'] or a['cpu_quota'] != b['cpu_quota'] for a, b in pairs)
            if mode == 'equal_work':
                mismatch = mismatch or any(not a.get('work_signature') or a.get('work_signature') != b.get('work_signature')
                    or a.get('actions') != b.get('actions') or a.get('turns') != b.get('turns') for a, b in pairs)
            else:
                # A different finish or action count means the engines did not
                # perform the same end-to-end work; their resource ratio is not
                # comparable acceptance evidence.
                mismatch = mismatch or any(a.get('terminal_reason') != b.get('terminal_reason')
                    or a.get('actions') != b.get('actions') or a.get('turns') != b.get('turns')
                    for a, b in pairs)
            if mismatch:
                mismatched.append(block)
                continue
            complete.append(block)
            def ratio(metric):
                numerator = sum(a[metric] for a, _ in pairs)
                denominator = sum(b[metric] for _, b in pairs)
                return numerator, denominator
            wall_blocks.append(ratio('wall_seconds'))
            cpu_blocks.append(ratio('cpu_core_seconds'))
            memory_blocks.append(ratio('peak_pss_bytes'))
        measured = len(complete) >= 30
        def combined_ratio(blocks):
            return sum(a for a, _ in blocks) / sum(b for _, b in blocks) if blocks else None
        wall_ratio = combined_ratio(wall_blocks) if measured else None
        cpu_ratio = combined_ratio(cpu_blocks) if measured else None
        memory_ratio = combined_ratio(memory_blocks) if measured else None
        engine_metrics = {}
        for engine in ('native', 'lite'):
            selected = [r for (block, seat, e), r in rows.items() if e == engine and block in complete]
            engine_metrics[engine] = {metric: _summary([r[metric] for r in selected]) for metric in MEASUREMENTS}
            engine_metrics[engine]['components_seconds'] = {component: _summary([r['components_seconds'][component]
                for r in selected if r['components_seconds'][component] is not None]) for component in COMPONENTS}
            engine_metrics[engine]['actions'] = sum(r.get('actions', 0) for r in selected)
            engine_metrics[engine]['turns'] = sum(r.get('turns', 0) for r in selected)
            reasons = defaultdict(int)
            for row in selected:
                reasons[row.get('terminal_reason', 'unknown')] += 1
            engine_metrics[engine]['terminal_reasons'] = dict(reasons)
        reports.append(dict(format=fmt, cache=cache, mode=mode, density=density, workers=workers,
            complete_rotation_blocks=len(complete), missing_blocks=missing, unequal_work_blocks=mismatched,
            wall_speedup=wall_ratio, cpu_ratio=cpu_ratio,
            memory_pss_ratio=memory_ratio,
            wall_speedup_ci95=_interval(wall_blocks) if measured else None,
            cpu_ratio_ci95=_interval(cpu_blocks) if measured else None,
            status=('passed' if wall_ratio >= manifest['required_speedup']
                    and cpu_ratio >= manifest['required_cpu_ratio']
                    and memory_ratio >= manifest['resource_memory_ratio_target'] else 'failed')
                   if measured else 'inconclusive',
            engines=engine_metrics))
    required_artifacts = manifest.get('required_artifacts',
        ('native_executable', 'lite_rules', 'astra', 'v4_duel', 'v4_ffa4', 'v4_team2v2'))
    artifacts_frozen = all(manifest['artifacts'].get(k, {}).get('sha256') for k in required_artifacts)
    status = 'inconclusive' if not artifacts_frozen or failures or any(r['status'] == 'inconclusive' for r in reports) else 'failed' if any(r['status'] == 'failed' for r in reports) else 'passed'
    return dict(manifest_id=manifest['manifest_id'], status=status, artifacts_frozen=artifacts_frozen,
        groups=reports, excluded_samples=failures,
        component_diagnostics=dict(status='inconclusive' if timing_gaps else 'passed', missing=timing_gaps,
            explanation='Missing component timings limit profiling attribution, not measured wall/CPU/PSS ratios.'),
        audit_pipeline=dict(status='inconclusive', explanation='Measure audit plus lite pipeline separately; pure-lite ratios do not prove pipeline speedup.'),
        secondary_workers=dict(status='inconclusive', required=[4, 8]))


def pipeline_report(native_equivalent, measured_pipeline):
    """Measured total wall/core-seconds, including native audit and coordination."""
    metrics = ('wall_seconds', 'cpu_core_seconds')
    if any(not isinstance(row.get(k), (int, float)) or row[k] <= 0
           for row in (native_equivalent, measured_pipeline) for k in metrics):
        return dict(status='inconclusive', reason='missing measured pipeline totals')
    if native_equivalent.get('work_signature') != measured_pipeline.get('work_signature') or not native_equivalent.get('work_signature'):
        return dict(status='inconclusive', reason='pipeline workloads differ')
    wall = native_equivalent['wall_seconds'] / measured_pipeline['wall_seconds']
    cpu = native_equivalent['cpu_core_seconds'] / measured_pipeline['cpu_core_seconds']
    return dict(status='passed' if min(wall, cpu) >= 5 else 'failed', wall_speedup=wall, cpu_ratio=cpu)


def run_benchmarks(runners, manifest, output_dir):
    """Explicit execution only: runner(workload) returns actual raw measurements.

    Run engines alternately per paired workload. No runner or result is invented;
    a backend lacking process-tree CPU or PSS reports null and stays inconclusive.
    """
    from .common import write_json
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'manifest.json', manifest)
    raw = []
    with (output / 'raw.jsonl').open('x', encoding='utf-8') as stream:
        for index, work in enumerate(manifest['workloads']):
            for engine in (('native', 'lite') if index % 2 == 0 else ('lite', 'native')):
                measured = runners[engine](dict(work))
                sample = dict(measured, workload_id=work['id'], manifest_id=manifest['manifest_id'], engine=engine)
                stream.write(json.dumps(sample, allow_nan=False) + '\n')
                stream.flush()
                raw.append(sample)
    report = benchmark_report(raw, manifest)
    write_json(output / 'report.json', report)
    return report
