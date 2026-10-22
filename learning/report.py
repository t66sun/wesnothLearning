"""Stage report (TEST.md section 10) and per-format profile reports."""
import csv
from pathlib import Path
from .common import write_json

STATUSES=('passed','failed','inconclusive','not_run','blocked')
REPORT_KEYS=('report_version','stage','status','revision','source_sha256','command',
    'started_at','finished_at','host','versions','format','context','counts','checks',
    'metrics','known_differences','implementation_gaps','artifacts','next_required_action','stage_exit')


def _derived_status(checks):
    states=[check.get('status','not_run') for check in checks]
    if not states: return 'not_run'
    if all(state == 'not_run' for state in states): return 'not_run'
    if 'failed' in states: return 'failed'
    if any(state in ('inconclusive','blocked','not_run') for state in states): return 'inconclusive'
    return 'passed'


def build_report(*,stage='P1',status=None,revision=None,source_sha256=None,command=None,
                 started_at=None,finished_at=None,host=None,versions=None,format=None,
                 format_name=None,context=None,counts=None,checks=None,metrics=None,
                 known_differences=None,implementation_gaps=None,artifacts=None,
                 next_required_action=None,stage_exit=None):
    """Build the machine-readable report required by TEST.md section 10.

    Missing measurements stay null. They are never replaced by zero or by a
    historical best result; the corresponding metric name is listed in
    ``missing`` so a reader can distinguish "not measured" from "measured as 0".
    """
    checks=[dict(check) for check in (checks or [])]
    for check in checks:
        check.setdefault('id','check-%d' % (len(checks)+1))
        check.setdefault('expected',None);check.setdefault('actual',None)
        check.setdefault('status','not_run');check.setdefault('reason',None)
        check.setdefault('evidence',[])
    metrics=dict(metrics or {})
    missing={name:'not measured' for name,value in metrics.items() if value is None}
    derived=_derived_status(checks)
    # A caller cannot claim `passed` when any check is blocked, missing, or failed.
    result_status=derived if status=='passed' else (status or derived)
    gaps=list(implementation_gaps or [])
    if not metrics and not gaps: gaps=['metrics are empty; measurement is not complete']
    report={
        'report_version':1,'stage':stage,'status':result_status,'revision':revision,
        'source_sha256':source_sha256,'command':command,'started_at':started_at,
        'finished_at':finished_at,
        'host':dict({'os':None,'cpu':None,'ram_bytes':None,'threads':None,'workers':None},**(host or {})),
        'versions':dict({'native':'1.18.8','engine':None,'rules':None,'rng':None,
            'schema':4,'candidates':None,'architecture':'relational_v5','policy':None,
            'reward_formula':None,'reward_config':None},**(versions or {})),
        'format':format if format is not None else format_name,
        'context':dict({'map':None,'map_sha256':None,'faction':None,'teammate':None,
            'partition':None,'families':[],'seeds':[]},**(context or {})),
        'counts':dict({'planned':None,'complete':None,'faulted':None,'missing':None,
            'excluded':None},**(counts or {})),
        'checks':checks,'metrics':metrics,'missing':missing,
        'known_differences':list(known_differences or []),
        'implementation_gaps':gaps,'artifacts':dict(artifacts or {}),
        'next_required_action':next_required_action,
        'stage_exit':dict({'met':result_status=='passed','condition':None,
            'reason':None},**(stage_exit or {})),
    }
    if result_status not in STATUSES: raise ValueError('unknown report status: '+str(result_status))
    return report


def _blockers(report):
    reasons=[]
    for check in report.get('checks',[]):
        if check.get('status') in ('failed','blocked','inconclusive','not_run'):
            reasons.append('%s: %s' % (check.get('id'),check.get('reason') or check.get('status')))
    if report.get('implementation_gaps'):
        reasons.extend(report['implementation_gaps'])
    return reasons


def report_markdown(report):
    """Short Markdown report; conclusion and blockers precede all detail."""
    blockers=_blockers(report)
    lines=['# '+str(report.get('stage','report')),'',
        'Conclusion: '+str(report.get('status')),'Blockers: '+('; '.join(blockers) if blockers else 'none'),'',
        '| Field | Value |','|---|---|']
    for field in ('revision','source_sha256','command','started_at','finished_at','format'):
        lines.append('| %s | %s |' % (field,report.get(field)))
    lines+=['','## Checks','','| ID | Expected | Actual | Status | Reason |','|---|---|---|---|---|']
    for check in report.get('checks',[]):
        lines.append('| %s | %s | %s | %s | %s |' % (check.get('id'),check.get('expected'),
            check.get('actual'),check.get('status'),check.get('reason')))
    lines+=['','## Metrics','','```json','%s' % _json(report.get('metrics',{})),'```','',
        '## Next required action','',str(report.get('next_required_action')),'']
    return '\n'.join(lines)


def _json(value):
    import json
    return json.dumps(value,sort_keys=True,indent=2)


def write_stage_report(directory,report):
    """Write the paired machine JSON and short Markdown for one stage."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    write_json(directory/'report.json',report)
    (directory/'REPORT.md').write_text(report_markdown(report),encoding='utf-8')
    return directory/'report.json',directory/'REPORT.md'


def write_profile_report(directory,summary,history):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    write_json(directory/'summary.json',summary)
    fields=['batch','method','elapsed_hours','updates','loss','interrupted']
    with (directory/'training.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(history)
    lines=['# '+summary['format'],'Conclusion: '+summary['status'],'Blockers: '+
        ('; '.join(f"{control}: {row['status']}" for control,row in summary['controls'].items()
                   if row['status']!='passed') or 'none'),'',
        '| Control | Complete blocks | Planned blocks | Fault games | Difference | 95% interval | Status |',
        '|---|---:|---:|---:|---:|---|---|']
    for control,row in summary['controls'].items():
        difference='pending' if row['difference'] is None else f"{row['difference']:.4f}"
        lines.append(f"| {control} | {row['blocks']} | {row['planned_blocks']} | {row.get('fault_games',0)} | {difference} | {row['interval95']} | {row['status']} |")
        for context,value in row['contexts'].items():
            lines.append(f"| ↳ {context} | {value['blocks']} | | | {value['difference']:.4f} | {value['interval95']} | |")
    lines+=['',f"Selected: {summary['selected_kind']}, v{summary['version']}; parameters: {summary['parameters']}",
        f"BC gate complete: {summary.get('pretraining_complete',False)}; clean teacher games: {summary.get('bc_games_collected',0)}/{summary.get('bc_games_required','unknown')}",
        'Checkpoint SHA-256: '+summary['checkpoint_sha256']]
    if summary.get('evaluation_engine'):
        lines+=['','Evaluation engine: '+summary['evaluation_engine'],
                'Evaluation scope: '+summary.get('evaluation_scope','unspecified')]
    if history:
        lines+=['','## Trend','', 'Panel sampled every 10 updates.','',
                '| Batch | Method | Updates | Elapsed hours | Loss |','|---|---|---:|---:|---:|']
        for row in history:
            if int(row.get('updates', 0)) % 10 == 0:
                lines.append(f"| {row.get('batch')} | {row.get('method')} | {row.get('updates')} | "
                             f"{row.get('elapsed_hours')} | {row.get('loss')} |")
    lines+=['',
        'A missing rotation block is inconclusive. These results select only this format.',
        'Full gates, errors and the original budget are recorded in summary.json.']
    (directory/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
