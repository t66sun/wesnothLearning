"""Per-format profile report: summary.json, training.csv and REPORT.md."""
import csv
from pathlib import Path

from .common import write_json


def write_profile_report(directory,summary,history):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    write_json(directory/'summary.json',summary)
    fields=['batch','method','elapsed_hours','updates','loss','interrupted']
    with (directory/'training.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(history)
    lines=['# '+summary['format'],'Conclusion: '+summary['status'],'Blockers: '+
        ('; '.join(f"{control}: {row['status']}" for control,row in summary['controls'].items()
                   if row['status']!='passed') or 'none'),'',
        '| Control | Complete blocks | Planned blocks | Distinct scenarios | Required scenarios | Fault games | Difference | 95% interval | Status |',
        '|---|---:|---:|---:|---:|---:|---:|---|---|']
    for control,row in summary['controls'].items():
        difference='pending' if row['difference'] is None else f"{row['difference']:.4f}"
        lines.append(f"| {control} | {row['blocks']} | {row['planned_blocks']} | {row.get('distinct_scenarios','unknown')} | {row.get('min_distinct','unknown')} | {row.get('fault_games',0)} | {difference} | {row['interval95']} | {row['status']} |")
        for context,value in row['contexts'].items():
            lines.append(f"| ↳ {context} | {value['blocks']} | | {value.get('distinct_scenarios','unknown')} | | | {value['difference']:.4f} | {value['interval95']} | |")
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
