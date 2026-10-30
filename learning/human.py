"""Prepare native 1.18.8 replay capture and import only verified capture logs.

No Python simulation of moves, damage, recruitment, fog or random numbers.
The original replay command order, dependent inputs and checkups are preserved.
Preparation does not launch Wesnoth. The replay viewer must be played on the
test machine before its full stdout/stderr log can be imported.
"""
from collections import Counter
import copy
import gzip
import json
import os
from pathlib import Path
import re
from .common import ROOT, write_json, sha256
from .features import schema, VERSION
from .formats import FORMATS
from .data import split, validate_record
from .replay_curate import Node, parse_wml, unpack
import native

OBSERVER_VERSION='native-observer-v5.0'
PREFIX='LEARNING_HUMAN '


def dump(node):
    def quoted(value): return '"'+str(value).replace('"','""')+'"'
    lines=[f'{key}='+ (str(value) if str(value).startswith('<<') and str(value).endswith('>>') else quoted(value)) for key,value in node.attrs.items()]
    for child in node.children: lines.extend(['['+child.tag+']',dump(child),'[/'+child.tag+']'])
    return '\n'.join(lines)


def intent(command):
    for tag in ('recruit','move','attack','end_turn'):
        n=command.first(tag)
        if n is None: continue
        a=dict(kind=tag)
        if tag=='move':
            xs=list(map(int,n.attrs['x'].split(',')));ys=list(map(int,n.attrs['y'].split(',')))
            if len(xs)!=len(ys) or len(xs)<2: return None
            a.update(x=xs[0],y=ys[0],tx=xs[-1],ty=ys[-1],full=False)
        elif tag=='recruit': a.update(type=n.attrs['type'],x=int(n.attrs['x']),y=int(n.attrs['y']))
        elif tag=='attack':
            if 'weapon' not in n.attrs or int(n.attrs['weapon'])<0: return None
            src=n.first('source');dst=n.first('destination')
            if src is None or dst is None: return None
            a.update(x=int(src.attrs['x']),y=int(src.attrs['y']),tx=int(dst.attrs['x']),ty=int(dst.attrs['y']),weapon=int(n.attrs['weapon'])+1)
        return a
    return None


def start_block(root):
    """The block that seeds the replay.

    A save replay carries [replay_start]; a server archive carries [scenario] and lets
    Wesnoth merge [carryover_sides_start] into it (saved_game::get_replay_starting_point).
    """
    return root.first('replay_start') or root.first('scenario')


def replay_block(root):
    """The [replay] that holds commands; server archives also write an empty [upload_log] one."""
    blocks=[n for n in root.all('replay') if n.first('command')]
    return blocks[-1] if blocks else None


def compatibility(row,root):
    if row['category']!='standard_multiplayer' or row.get('era')!='era_default': return 'non_standard_rules'
    if row['format'] not in FORMATS: return 'unsupported_training_format'
    if row.get('required_addons') or root.attrs.get('active_mods') or root.attrs.get('mod_defines'): return 'custom_modifications'
    # Labels must describe the frozen 1.18.8 rules; an older replay reproduces
    # under different combat and recruit numbers even when it replays cleanly.
    if row.get('version')!='1.18.8': return 'other_version'
    start=start_block(root);replay=replay_block(root)
    if start is None or replay is None: return 'missing_native_initial_state'
    # A server archive has no state snapshot: [scenario] is the start block and the
    # recorded initial RNG is the only source for dependent random_seed commands.
    if root.first('replay_start') is None:
        rng=root.first('carryover_sides_start')
        if rng is None or not rng.attrs.get('random_seed'): return 'missing_initial_rng'
    # Controller transitions are not reliably timestamped in all save variants.
    # Skip the whole file rather than labeling a possible AI takeover as human.
    initial={s.attrs.get('side'):s.attrs.get('controller') for s in start.all('side')}
    snapshot=root.first('snapshot')
    if snapshot is not None and any(initial.get(s.attrs.get('side'))!=s.attrs.get('controller') for s in snapshot.all('side')): return 'controller_provenance_changed'
    for c in replay.all('command'):
        if any('controller' in n.tag or n.tag in ('side_drop','change_side','change_side_controller') for n in c.children): return 'controller_provenance_changed'
    return None


def prepare_capture(row,root,directory,wesnoth=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    root=copy.deepcopy(root);start=start_block(root);replay=replay_block(root)
    root.children=[n for n in root.children if n.tag!='snapshot']
    humans={int(s.attrs['side']) for s in start.all('side') if s.attrs.get('controller')=='human'}
    actions=[];commands=[];current=0
    for c in replay.children:
        init=c.first('init_side')
        if init: current=int(init.attrs.get('side_number',current))
        a=intent(c) if c.tag=='command' and c.attrs.get('dependent') not in ('yes','true') else None
        if a and current in humans:
            sender=c.attrs.get('from_side')
            if sender is not None and sender!=str(current): raise ValueError('action sender/side mismatch')
            actions.append(dict(a,index=len(actions),side=current))
            commands.append(Node('command',{'from_side':str(current)},[Node('custom_command',{'name':'learning_observe'},[Node('data',{'index':str(len(actions)-1)})])]))
        commands.append(c)
    if not actions: raise ValueError('no reconstructable human action intents')
    commands.append(Node('command',{'from_side':str(current)},[Node('custom_command',{'name':'learning_complete'},[])]))
    replay.children=commands
    options=dict(game_id=row['game_id'],game_family=row['family_id'],format=row['format'],actions=actions,
        source_sha256=row['curated_sha256'],observer_version=OBSERVER_VERSION,expected_actions=len(actions))
    code="wesnoth.dofile('~add-ons/LearningSupport/lua/replay_observer.lua').setup("+native.lua(options)+")"
    start.children.append(Node('event',{'name':'preload','first_time_only':'no'},[Node('lua',{'code':code})]))
    path=directory/(row['game_id']+'.cfg');path.write_text(dump(root)+'\n',encoding='utf-8')
    support=directory/'userdata/data/add-ons/LearningSupport/lua';support.mkdir(parents=True,exist_ok=True)
    for source in (ROOT/'lua').glob('*.lua'):
        (support/source.name).write_text(source.read_text(encoding='utf-8').replace('@ADDON@','LearningSupport'),encoding='utf-8')
    (support/'features.lua').write_text('return '+native.lua(schema()),encoding='utf-8')
    (support/'config.lua').write_text('return {candidate_budget_ms=200}',encoding='utf-8')
    (support/'replay_observer.lua').write_bytes((ROOT/'learning/replay_observer.lua').read_bytes())
    write_json(directory/'capture.json',dict(options=options,replay_sha256=sha256(path),
        command=[wesnoth or os.environ.get('WESNOTH_EXE','wesnoth'),'--debug','--debug-lua','--noaddons','--with-replay','--load',str(path.resolve()),
                 '--userdata-dir',str((directory/'userdata').resolve()),'--userconfig-dir',str((directory/'config').resolve()),
                 '--usercache-dir',str((directory/'cache').resolve()),'--nosound','--exit-at-end','--log-info=replay']))
    return len(actions)


def import_capture(path,row):
    text=Path(path).read_text(encoding='utf-8',errors='replace')
    if not re.search(r'(?:Battle for Wesnoth|Wesnoth)\s*v?1\.18\.8\b',text,re.I): raise ValueError('missing official 1.18.8 startup evidence')
    if re.search(r'out.of.sync|\bOOS\b|error (?:engine|replay|scripting/lua)|replay error|checkup.*(?:fail|mismatch)',text,re.I): raise ValueError('native replay mismatch/error')
    events=[json.loads(line.split(PREFIX,1)[1]) for line in text.splitlines() if PREFIX in line]
    complete=[e for e in events if e['event']=='complete']
    if len(complete)!=1: raise ValueError('replay did not reach exactly one completion marker')
    proof=complete[0]
    if proof.get('source_sha256')!=row['curated_sha256'] or proof.get('observer_version')!=OBSERVER_VERSION: raise ValueError('capture provenance mismatch')
    samples=[e['record'] for e in events if e['event']=='sample']
    if [r['action_index'] for r in samples]!=list(range(proof['expected_actions'])): raise ValueError('missing/reordered native observations')
    rows=[];counts=Counter();matched=Counter()
    for r in samples:
        kind=r['actual']['kind'];counts[kind]+=1
        if r.get('format')!=row['format'] or r.get('source')!='human' or r.get('human_control') is not True: raise ValueError('human/format provenance mismatch')
        r.update(game_id=row['game_id'],game_family=row['family_id'],split=split(row['family_id']),
                 reward=None,value_valid=False,version=OBSERVER_VERSION,teacher=False,source='human',
                 native_version='1.18.8',
                 source_sha256=row['curated_sha256'],capture_sha256=sha256(path))
        from dataclasses import asdict
        from .rewards import RewardConfig
        config=asdict(RewardConfig())
        r.update(engine='native',engine_id='native',rules_version=schema().get('rules_sha256') or 'native-1.18.8',rng_version='native-1.18.8',
            combat_version='native-1.18.8',
            architecture_id='relational_v5',candidate_version=r.get('candidate_version',f"schema{r.get('schema')}-"+r.get('timing',{}).get('budget','fixed-20000-v1')),data_pool='original',
            reward_config=config,reward_version=config['reward_version'],reward_formula_id=config['reward_formula_id'])
        if r['choice']>=0: validate_record(r,row['format']);matched[kind]+=1
        rows.append(r)
    return rows,{k:dict(total=n,matched=matched[k],ratio=matched[k]/n) for k,n in counts.items()}


def import_curated(curated,output,wesnoth=None,inventory_only=False,captures=None):
    curated=Path(curated);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    results=[]
    for line in (curated/'games.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line);item=dict(game_id=row['game_id'],format=row['format'],game_family=row['family_id'],split=split(row['family_id']),samples=0)
        try:
            path=curated/row['curated_path']
            if sha256(path)!=row['curated_sha256']: raise ValueError('curated source hash changed')
            root=parse_wml(unpack(path)[1].decode('utf-8-sig'))
            reason=compatibility(row,root)
            if reason: item.update(status='skipped',reason=reason)
            elif inventory_only: item.update(status='compatible_pending_native_replay')
            elif captures:
                rows,coverage=import_capture(Path(captures)/(row['game_id']+'.log'),row)
                dest=output/row['format']/(row['game_id']+'.jsonl.gz');dest.parent.mkdir(parents=True,exist_ok=True)
                with gzip.open(dest,'wt',encoding='utf-8') as stream:
                    from .rowpack import pack_line
                    for r in rows: stream.write(pack_line(r)+'\n')
                from .sequences import IndexedSequenceStore
                with IndexedSequenceStore(dest.parent/'sequences') as store: store.write(rows)
                item.update(status='imported',samples=sum(r['choice']>=0 for r in rows),coverage=coverage)
            else:
                count=prepare_capture(row,root,output/'capture'/row['game_id'],wesnoth)
                item.update(status='prepared_pending_native_replay',intents=count)
        except (ValueError,OSError,KeyError) as exc: item.update(status='skipped',reason=str(exc))
        results.append(item)
    summary=dict(schema=VERSION,observer_version=OBSERVER_VERSION,source_games=len(results),
        statuses=dict(Counter(r['status'] for r in results)),samples=sum(r['samples'] for r in results),games=results,
        native_replay_executed=False if not captures else 'capture logs supplied',
        note='Preparation never launches Wesnoth. Play prepared replays in official 1.18.8, retain full logs, then use --captures. Unknown outcomes never supervise value.')
    write_json(output/'import.json',summary);return summary
