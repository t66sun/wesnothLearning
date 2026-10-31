"""Inventory and curate saved Wesnoth replays without running the game.

Both containers are read: a locally saved game, whose starting state lives in
[replay_start], and a hosted archive dropped from the multiplayer lobby, whose
starting state lives in [scenario] plus [carryover_sides_start]. Serialized WML
is parsed as data; embedded Lua is never executed. Originals are read only.
Replay branches are retained, not collapsed by map or filename.
"""
from __future__ import annotations

import argparse
import bz2
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass, field
import gzip
import hashlib
import json
from pathlib import Path
import re


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def first(self, tag):
        return next((n for n in self.children if n.tag == tag), None)

    def all(self, tag):
        return [n for n in self.children if n.tag == tag]


OPEN = re.compile(r'^\[([A-Za-z_][\w-]*)\]$')
CLOSE = re.compile(r'^\[/([A-Za-z_][\w-]*)\]$')
ATTR = re.compile(r'^([\w,]+)\s*=\s*(.*)$')
TRANSLATED = re.compile(r'^_\s*(?=")')
STRING = re.compile(r'(?:_\s*)?"((?:[^"]|"")*)"', re.S)
# These carry UI/network chatter, not decisions or randomness. Keep all other
# commands, including controller changes, choices and random seeds.
COSMETIC = {'speak', 'label', 'clear_labels', 'countdown_update', 'rename'}
DECISIONS = {'move', 'attack', 'recruit', 'recall', 'end_turn'}
CHECKUPS = {'checkup', 'mp_checkup'}  # single-player inline and multiplayer dependent sync records


def quote_state(value, quoted=False):
    i = 0
    while i < len(value):
        if value[i] == '"':
            if quoted and i+1 < len(value) and value[i+1] == '"':
                i += 2
                continue
            quoted = not quoted
        i += 1
    return quoted


def scalar(raw):
    raw = TRANSLATED.sub('', raw.strip())
    strings = list(STRING.finditer(raw))
    if strings and not raw[:strings[0].start()].strip() and not raw[strings[-1].end():].strip():
        gaps = [raw[a.end():b.start()] for a,b in zip(strings,strings[1:])]
        if all(re.fullmatch(r'\s*\+\s*', gap) for gap in gaps):
            return ''.join(match[1].replace('""','"') for match in strings)
    return raw


def parse_wml(text):
    """Parse the expanded, serialized WML shape used by saves, not source macros."""
    root = Node('root')
    stack = [root]
    lines = iter(enumerate(text.splitlines(), 1))
    for number, line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        opening, closing = OPEN.fullmatch(line), CLOSE.fullmatch(line)
        if opening:
            child = Node(opening[1])
            stack[-1].children.append(child)
            stack.append(child)
        elif closing:
            if len(stack) == 1 or stack[-1].tag != closing[1]:
                raise ValueError(f'mismatched closing tag at line {number}')
            stack.pop()
        else:
            match = ATTR.fullmatch(line)
            if not match:
                raise ValueError(f'unsupported serialized WML at line {number}')
            key, value = match.groups()
            if value.startswith('<<'):
                while '>>' not in value:
                    try:
                        value += '\n' + next(lines)[1]
                    except StopIteration:
                        raise ValueError('unterminated literal block') from None
            else:
                parts = [value]
                quoted = quote_state(value)
                continuation = value
                while quoted or continuation.rstrip().endswith('+'):
                    try:
                        continuation = next(lines)[1]
                        if not quoted and (not continuation.strip() or continuation.lstrip().startswith('#')):
                            continuation = '+'
                            continue
                        parts.append(continuation)
                        quoted = quote_state(continuation, quoted)
                    except StopIteration:
                        raise ValueError('unterminated quoted string') from None
                value = '\n'.join(parts)
            stack[-1].attrs[key] = scalar(value)
    if len(stack) != 1:
        raise ValueError('unclosed WML tag')
    return root


def canonical(node):
    return [node.tag, sorted(node.attrs.items()), [canonical(c) for c in node.children]]


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(value).hexdigest()


def unpack(path):
    content = path.read_bytes()
    if content.startswith(b'\x1f\x8b'):
        return content, gzip.decompress(content), 'gzip'
    if content.startswith(b'BZh'):
        return content, bz2.decompress(content), 'bzip2'
    return content, content, 'plain'


def integer(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def replay_identity(root, start):
    # Deliberately exclude snapshot state and filenames: they change at each
    # autosave. The initial RNG, map, rules and starting roster identify a run.
    mp = root.first('multiplayer') or Node('multiplayer')
    sides = []
    for side in start.all('side'):
        # Saves can re-randomize initial visual facing. It is not a new game;
        # retain all other initial unit state, including traits and objects.
        units = [canonical(Node(u.tag,{k:v for k,v in u.attrs.items() if k != 'facing'},u.children))
                 for u in side.all('unit')]
        sides.append(dict(attrs={k:side.attrs.get(k, '') for k in
            ['side','team_name','controller','current_player','player_id','faction','type',
             'recruit','gold','income','village_gold','village_support']}, units=units))
    return dict(campaign=root.attrs.get('campaign', ''), era=root.attrs.get('era_id', ''),
        scenario=start.attrs.get('id', mp.attrs.get('mp_scenario', '')),
        random_seed=start.attrs.get('random_seed', ''),
        map_hash=digest(start.attrs.get('map_data', '')),
        rules={k:start.attrs.get(k, '') for k in ['turns','experience_modifier','random_start_time']},
        sides=sides)


def archive_identity(root, scenario, carry):
    # Server archives dropped from the multiplayer lobby carry the starting
    # state as [scenario] plus the carried RNG state; there is no
    # [replay_start] and no per-unit roster, because the game rebuilds the
    # sides from the scenario. Identity therefore rests on the board, the
    # rules, the side setup and the initial RNG position.
    mp = root.first('multiplayer') or Node('multiplayer')
    sides = [dict(attrs={k:side.attrs.get(k, '') for k in
        ['side','team_name','controller','current_player','player_id','faction',
         'recruit','gold','income','village_gold','village_support']}, units=[])
        for side in scenario.all('side')]
    return dict(campaign=root.attrs.get('campaign', ''), era=root.attrs.get('era_id', ''),
        scenario=scenario.attrs.get('id', mp.attrs.get('mp_scenario', '')),
        random_seed=(carry.attrs.get('random_seed', '') if carry is not None else ''),
        map_hash=digest(scenario.attrs.get('map_data', '')),
        rules={'random_calls': carry.attrs.get('random_calls', '') if carry is not None else '',
               **{k:scenario.attrs.get(k, '') for k in
                  ['turns','experience_modifier','random_start_time']}},
        sides=sides)


TAKEOVER = re.compile(r'^(.+) takes control of side (\d+)\.$')


def controller_changes(commands, initial_players):
    """Sides whose human changed hands once the game was under way.

    The server announces "X takes control of side N." both when a lobby slot
    is filled before play, when a player takes a seat mid-game, and when the
    lobby reopens after the game. Only an announcement bracketed by decisions
    on that side, naming someone other than its initial player, replaces the
    human who produced them.
    """
    first_decision, last_decision = {}, {}
    for index, command in enumerate(commands):
        if any(node.tag in DECISIONS for node in command.children):
            side = str(command.attrs.get('from_side',''))
            first_decision.setdefault(side, index)
            last_decision[side] = index
    named = {str(player['side']): player['player'] for player in initial_players}
    changed = {}
    for index, command in enumerate(commands):
        for node in command.children:
            match = TAKEOVER.match(node.attrs.get('message','')) if node.tag == 'speak' else None
            if match is None:
                continue
            name, side = match.group(1), match.group(2)
            # Only a hand-over bracketed by decisions on that side mixes two
            # humans in one history; lobby chatter and post-game rejoins do not.
            if not first_decision.get(side, len(commands)) <= index < last_decision.get(side, -1):
                continue
            if name == named.get(side, ''):
                continue
            changed.setdefault(side, []).append(name)
    return changed


def command_sequence(blocks):
    # Every command from every [replay] block, in document order: a hosted
    # archive puts the upload log in one block and the history in another.
    result, intents, partial_last = [], [], False
    for command in [c for block in blocks for c in block.all('command')]:
        children = [n for n in command.children if n.tag not in COSMETIC]
        if not children:
            continue
        # sent/undo are recorder bookkeeping, not changed game decisions.
        stable = Node('command', {k:v for k,v in command.attrs.items() if k not in {'sent','undo'}}, children)
        result.append(digest(canonical(stable)))
        intents.append(digest(canonical(Node('command',stable.attrs,
            [n for n in children if n.tag not in CHECKUPS]))))
        checkups = [n for n in children if n.tag in CHECKUPS]
        partial_last = bool(checkups) and all(not n.attrs and not n.children for n in checkups)
    return result, intents, partial_last


def inspect_file(path, source):
    packed, raw, compression = unpack(path)
    row = dict(source=path.relative_to(source).as_posix(), source_sha256=digest(packed),
               payload_sha256=digest(raw), bytes=len(packed), compression=compression,
               layout='', status='', selected='', family_id='', game_id='', curated_path='', notes=[])
    # Steam metadata is not a saved game. Do not classify it as malformed WML.
    if path.suffix.lower() == '.vdf':
        row['status'] = 'not_replay'
        return row
    root = parse_wml(raw.decode('utf-8-sig'))
    row.update(version=root.attrs.get('version', ''), campaign_type=root.attrs.get('campaign_type', ''),
               campaign=root.attrs.get('campaign', ''), era=root.attrs.get('era_id', ''),
               label=root.attrs.get('label', ''))
    start, snapshot = root.first('replay_start'), root.first('snapshot')
    scenario, carry = root.first('scenario'), root.first('carryover_sides_start')
    replays = root.all('replay')
    row['snapshot_turn'] = integer(snapshot.attrs.get('turn_at')) if snapshot else None
    if not replays or (start is None and scenario is None):
        row['status'] = 'no_replay_history'
        return row
    row['layout'] = 'save' if start is not None else 'archive'
    if start is None:
        row['notes'].append('server_archive_layout; no_replay_start_block')
    initial = start if start is not None else scenario
    identity = replay_identity(root, start) if start is not None else archive_identity(root, scenario, carry)
    row['family_id'] = digest(identity)
    row['initial_seed'] = identity['random_seed']
    row['scenario_id'] = identity['scenario']
    row['_commands'], row['_intents'], row['_partial_last'] = command_sequence(replays)
    row['history_sha256'] = digest(row['_commands'])
    commands = [c for block in replays for c in block.all('command')]
    tags = Counter(n.tag for c in commands for n in c.children)
    row['commands'] = len(commands)
    row['semantic_commands'] = len(row['_commands'])
    row['actions'] = sum(tags[t] for t in DECISIONS)
    row['command_tags'] = dict(tags)
    row['has_snapshot'] = snapshot is not None
    row['replay_only_file'] = snapshot is None
    row['end_marker'] = any(tags[t] for t in ['surrender','endlevel','game_end'])
    row['observed_end_turns'] = tags['end_turn']
    row['initial_turn'] = integer(initial.attrs.get('turn_at'), 1)
    row['initial_players'] = [dict(side=s.attrs.get('side'), controller=s.attrs.get('controller'),
        player=s.attrs.get('current_player', s.attrs.get('player_id', '')),
        faction=s.attrs.get('faction'), team=s.attrs.get('team_name'),
        allow_player=s.attrs.get('allow_player', 'yes')) for s in initial.all('side')]
    playable = [s for s in row['initial_players'] if s['allow_player'] not in {'no','false','0'}]
    row['players'] = len(playable)
    row['human_sides'] = sum(s['controller'] in {'human','network'} for s in playable)
    row['ai_sides'] = sum(s['controller'] == 'ai' for s in playable)
    row['controller_changes'] = controller_changes(commands, row['initial_players'])
    if row['controller_changes']:
        row['notes'].append('controller_changed_midgame; human_side_provenance_mixed')
    row['factions'] = [s['faction'] or '' for s in playable]
    teams = Counter(s['team'] for s in playable)
    if len(playable) == 2 and len(teams) == 2:
        row['format'] = 'duel'
    elif len(playable) == 4 and len(teams) == 2 and sorted(teams.values()) == [2,2]:
        row['format'] = 'team2v2'
    elif len(teams) == len(playable) and len(playable) > 2:
        row['format'] = f'ffa{len(playable)}'
    else:
        row['format'] = 'other'
    mp = root.first('multiplayer') or Node('multiplayer')
    row['required_addons'] = [a.attrs.get('id','') for a in mp.all('addon')
                              if a.attrs.get('required') in {'yes','true','1'} and a.attrs.get('id') != 'mainline']
    if row['campaign'] or row['campaign_type'] == 'scenario':
        row['category'] = 'campaigns'
    elif row['campaign_type'] == 'test' or not row['actions']:
        row['category'] = 'test_or_empty'
    elif row['campaign_type'] == 'multiplayer' and row['era'] == 'era_default' and not row['required_addons']:
        row['category'] = 'standard_multiplayer'
    else:
        row['category'] = 'other_multiplayer'
    if row['human_sides'] == 0:
        row['notes'].append('no_human_side_identified')
    if row['ai_sides']:
        row['notes'].append('contains_ai_opponents; human_actions_must_be_filtered')
    names = [s['player'] for s in playable if s['controller'] in {'human','network'} and s['player']]
    if len(names) != len(set(names)):
        row['notes'].append('same_player_on_multiple_sides')
    if not row['end_marker']:
        row['notes'].append('outcome_not_verified')
    if not row['initial_seed']:
        row['notes'].append('missing_initial_seed; identity_requires_review')
    row['status'] = 'candidate'
    return row


def choose_survivors(rows):
    """Collapse identical histories and strict prefixes; retain divergent leaves."""
    families = defaultdict(list)
    for row in rows:
        if row['status'] == 'candidate':
            families[row['family_id']].append(row)
    selected = []
    for family in families.values():
        # More recorded decisions first. Prefer replay-only files on exact ties,
        # then a filename without a copy suffix; filenames never establish identity.
        order = sorted(family, key=lambda r:(-len(r['_commands']), -r['actions'],
            r['_partial_last'], not r['replay_only_file'],
            bool(re.search(r'副本|copy|\(\d+\)',r['source'],re.I)),r['source']))
        leaves = []
        for row in order:
            seq = row['_commands']
            def covered_by(leaf):
                if leaf['_commands'][:len(seq)] == seq:
                    return True
                # An autosave can end inside an attack, before the recorded
                # checkup/mp_checkup results. Only the last, explicitly empty
                # checkup is a wildcard; earlier RNG/results must still match
                # exactly.
                return (row['_partial_last'] and bool(seq) and len(leaf['_commands']) >= len(seq)
                    and seq[:-1] == leaf['_commands'][:len(seq)-1]
                    and row['_intents'][-1] == leaf['_intents'][len(seq)-1])
            matches = [leaf for leaf in leaves if covered_by(leaf)]
            if matches:
                parent = matches[0]
                row['selected'] = parent['source']
                if row['source_sha256'] == parent['source_sha256']:
                    row['status'] = 'byte_duplicate'
                elif row['payload_sha256'] == parent['payload_sha256']:
                    row['status'] = 'payload_duplicate'
                elif seq == parent['_commands']:
                    row['status'] = 'same_history'
                else:
                    row['status'] = 'earlier_save'
                if row['_partial_last'] and seq != parent['_commands']:
                    row['notes'].append('last_command_checkup_incomplete')
                if len(matches) > 1:
                    row['notes'].append('prefix_shared_by_multiple_branches')
            else:
                leaves.append(row)
                row['status'] = 'selected'
                row['selected'] = row['source']
        if len(leaves) > 1:
            for row in family:
                row['notes'].append('divergent_history_branches_retained')
        selected.extend(leaves)
    return selected


def public(row):
    return {k:v for k,v in row.items() if not k.startswith('_')}


def curate(source, output, origin=''):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir():
        raise ValueError('source directory does not exist')
    if output == source or output.is_relative_to(source):
        raise ValueError('output must be separate from source')
    if output.exists():
        raise FileExistsError('choose a new output directory; existing results are never overwritten')
    rows = []
    source_files = sorted(p for p in source.rglob('*') if p.is_file())
    for path in source_files:
        try:
            row = inspect_file(path, source)
        except (ValueError, UnicodeError, OSError, EOFError) as exc:
            row = dict(source=str(path.relative_to(source)), source_sha256=digest(path.read_bytes()),
                status='parse_error', error=str(exc), selected='', notes=[])
        rows.append(row)
    byte_seen, payload_seen = {}, {}
    for row in rows:
        byte_hash = row['source_sha256']
        row['byte_duplicate_of'] = byte_seen.get(byte_hash, '')
        byte_seen.setdefault(byte_hash, row['source'])
        payload_hash = row.get('payload_sha256')
        row['payload_duplicate_of'] = payload_seen.get(payload_hash, '') if payload_hash else ''
        if payload_hash:
            payload_seen.setdefault(payload_hash, row['source'])
    survivors = sorted(choose_survivors(rows), key=lambda r:(r['category'],r['scenario_id'],r['family_id'],r['history_sha256']))
    output.mkdir(parents=True)
    for i,row in enumerate(survivors,1):
        row['game_id'] = f'game_{i:04d}'
        destination = output/'replays'/row['category']/(row['game_id']+'.gz')
        destination.parent.mkdir(parents=True,exist_ok=True)
        _,payload,_ = unpack(source/row['source'])
        destination.write_bytes(gzip.compress(payload,mtime=0))
        assert digest(gzip.decompress(destination.read_bytes())) == row['payload_sha256']
        row['curated_path'] = destination.relative_to(output).as_posix()
        row['curated_sha256'] = digest(destination.read_bytes())
    lookup = {r['source']:r for r in survivors}
    for row in rows:
        if row.get('selected') in lookup:
            selected = lookup[row['selected']]
            row['game_id'] = selected['game_id']
            row['curated_path'] = selected['curated_path']
    # Prove that neither the bytes nor the set of original files changed.
    assert source_files == sorted(p for p in source.rglob('*') if p.is_file())
    assert all(digest((source/r['source']).read_bytes()) == r['source_sha256'] for r in rows)
    summary = dict(source=str(source),output=str(output),source_files=len(rows),selected_replays=len(survivors),
        byte_duplicate_files=sum(bool(r['byte_duplicate_of']) for r in rows),
        duplicate_payload_files=sum(bool(r['payload_duplicate_of']) for r in rows),
        source_statuses=dict(Counter(r['status'] for r in rows)),
        selected_categories=dict(Counter(r['category'] for r in survivors)),
        selected_formats=dict(Counter(r['format'] for r in survivors)),
        selected_versions=dict(Counter(r['version'] for r in survivors)),
        selected_families=len({r['family_id'] for r in survivors}),
        branched_families=len({r['family_id'] for r in survivors if 'divergent_history_branches_retained' in r['notes']}),
        originals_unchanged=True, normalization='gzip container only; decompressed payload unchanged',
        origin=origin,
        outcome_labels='not inferred from filenames or assumed from latest turn',
        train_validation_split='not assigned; all histories in one family must share a split')
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    for name, data in [('inventory.jsonl',rows),('games.jsonl',survivors)]:
        (output/name).write_text(''.join(json.dumps(public(r),ensure_ascii=False)+'\n' for r in data),encoding='utf-8',newline='\n')
    columns=['game_id','source','status','selected','curated_path','byte_duplicate_of','payload_duplicate_of','layout','version','campaign_type','campaign',
             'scenario_id','era','category','format','players','human_sides','ai_sides','actions',
             'commands','snapshot_turn','replay_only_file','end_marker','family_id','notes']
    with (output/'inventory.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore',lineterminator='\n');writer.writeheader()
        for row in rows:
            entry=public(row);entry['notes']='; '.join(entry.get('notes',[]));writer.writerow(entry)
    lines=['# 人类回放整理结果','',f'原始文件：{len(rows)}；选定回放：{len(survivors)}。',
        '所有原始文件已逐一复核 SHA256，内容未修改。输出仅重封装为 gzip（mtime 固定）；容器字节随 zlib 版本而异，解压内容逐字节相同。',
        '', '## 来源','', f'- {origin}；inventory 的 source 即归档内成员路径。' if origin else '- 本地存档目录；inventory 的 source 即原文件名。',
        '', '## 筛选规则','',
        '- 依据初始地图、随机种子、规则、时代、阵营和单位建立同局族，再比较实际 command 历史；忽略保存时会随机变化的初始单位朝向。',
        '- 同历史只留一份；严格前缀视为更早存档；聊天/标签/单位改名不构成新对局。',
        '- 若最后动作的 checkup 尚为空且其余历史吻合，视为动作中途保存；其他随机结果差异保留为分支。',
        '- 实际历史分歧全部保留并标记，不按最高回合或同名地图直接合并。',
        '- 中途换人（判决前后同一方的操作者不同）记入 controller_changes，语料保留但需按此字段过滤。',
        '- 全部回放使用 ASCII 目录与统一 game_0001.gz 编号；原名对应见 inventory.csv。',
        '- standard_multiplayer 只是默认时代候选；仍需检查重建、规则、玩家控制和结果，尚非训练标签。',
        '- campaigns 与 other_multiplayer 单独归档；战役/自定义时代不直接混入当前标准时代训练。',
        '- 无 replay_start/replay 的开局/关卡切换存档及 Steam 元数据仅在清单中记录。',
        '- 多个分支或更早存档来自同一 family_id，后续训练/验证必须按 family_id 分组，防止泄漏。',
        '- 完整录像文件不等于已证明有胜负；本次不推测胜者，不启动游戏，不执行文件内 Lua。',
        '', '## 分类数量','']
    lines += [f'- {key}: {value}' for key,value in sorted(summary['selected_categories'].items())]
    lines += ['', '## 原文件处置数量','']
    lines += [f'- {key}: {value}' for key,value in sorted(summary['source_statuses'].items())]
    lines += ['', '## 编号对照','', '|编号|类别|版本|动作数|原文件|','|---|---|---|---:|---|']
    lines += [f"|{r['game_id']}|{r['category']}|{r['version']}|{r['actions']}|{r['source']}|" for r in survivors]
    (output/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--origin',default='',help='where the source files came from, recorded in the summary and README')
    args=parser.parse_args()
    print(json.dumps(curate(args.source,args.output,args.origin),ensure_ascii=True,indent=2))
