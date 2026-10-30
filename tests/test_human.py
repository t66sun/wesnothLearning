import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
import torch
from learning.human import intent, compatibility, prepare_capture, import_capture, PREFIX, OBSERVER_VERSION
from learning.replay_curate import parse_wml, canonical
from learning.data import bc_sample, split, validate_record
from learning.model import Policy
from learning.train import train
from tests.test_core import record


class HumanTests(unittest.TestCase):
    def fixture(self):
        root=parse_wml('''version="1.18.8"
[replay_start]
[side]
side=1
controller=human
[/side]
[side]
side=2
controller=human
[/side]
[/replay_start]
[replay]
[command]
[init_side]
side_number=1
[/init_side]
[/command]
[command]
from_side=1
[move]
x="1,2,3"
y="2,2,2"
[/move]
[/command]
[command]
dependent=yes
[random_seed]
new_seed=abcdef
[/random_seed]
[/command]
[/replay]''')
        row=dict(category='standard_multiplayer',era='era_default',format='duel',game_id='game_0001',family_id='g',curated_sha256='fixture',version='1.18.8')
        return root,row

    def test_prepare_keeps_original_random_inputs_and_actions(self):
        root,row=self.fixture();original=canonical(root)
        self.assertIsNone(compatibility(row,root))
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(prepare_capture(row,root,temp),1)
            prepared=parse_wml(Path(temp,'game_0001.cfg').read_text())
            original_commands=root.first('replay').children
            retained=[c for c in prepared.first('replay').children if c.first('custom_command') is None]
            self.assertEqual([canonical(c) for c in retained],[canonical(c) for c in original_commands])
            self.assertEqual(canonical(root),original)
            self.assertEqual(intent(original_commands[1]),dict(kind='move',x=1,y=2,tx=3,ty=2,full=False))

    def server_archive(self):
        root=parse_wml('''version="1.18.8"
[scenario]
id=mpscenario
[side]
side=1
controller=human
[/side]
[side]
side=2
controller=human
[/side]
[/scenario]
[replay]
[upload_log]
[/upload_log]
[/replay]
[replay]
[command]
[init_side]
side_number=1
[/init_side]
[/command]
[command]
from_side=1
[move]
x="1,2,3"
y="2,2,2"
[/move]
[/command]
[command]
dependent=yes
[random_seed]
new_seed=abcdef
[/random_seed]
[/command]
[/replay]
[carryover_sides_start]
random_seed=abcdef
random_calls=0
next_scenario=mpscenario
[/carryover_sides_start]''')
        row=dict(category='standard_multiplayer',era='era_default',format='duel',game_id='game_0002',family_id='g',curated_sha256='fixture',version='1.18.8')
        return root,row

    def test_server_archive_starts_from_its_scenario_block(self):
        root,row=self.server_archive();original=canonical(root)
        self.assertIsNone(compatibility(row,root))
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(prepare_capture(row,root,temp),1)
            prepared=parse_wml(Path(temp,'game_0002.cfg').read_text())
            self.assertIsNone(prepared.first('replay_start'))
            self.assertIn('replay_observer.lua',prepared.first('scenario').first('event').first('lua').attrs['code'])
            empty,replay=prepared.all('replay')
            self.assertEqual(canonical(empty),canonical(self.server_archive()[0].first('replay')))
            names=[c.first('custom_command').attrs['name'] if c.first('custom_command') else None for c in replay.children]
            self.assertEqual(names,[None,'learning_observe',None,'learning_result',None,'learning_complete'])
            retained=[c for c in replay.children if c.first('custom_command') is None]
            self.assertEqual([canonical(c) for c in retained],[canonical(c) for c in self.fixture()[0].first('replay').children])
            self.assertEqual(canonical(root),original)

    def test_server_archive_without_recorded_initial_rng_is_skipped(self):
        root,row=self.server_archive()
        root.children=[n for n in root.children if n.tag!='carryover_sides_start']
        self.assertEqual(compatibility(row,root),'missing_initial_rng')

    def test_ai_takeover_is_not_labeled_human(self):
        root,row=self.fixture()
        snapshot=copy.deepcopy(root.first('replay_start'));snapshot.tag='snapshot'
        snapshot.children[0].attrs['controller']='ai';root.children.append(snapshot)
        self.assertEqual(compatibility(row,root),'controller_provenance_changed')

    def test_labels_never_come_from_a_replay_recorded_under_older_rules(self):
        root,row=self.fixture()
        for version in ('1.18.7','1.18.2',None):
            stale=dict(row,version=version)
            self.assertEqual(compatibility(stale,root),'other_version')
        self.assertIsNone(compatibility(row,root))

    def test_capture_requires_complete_native_evidence_and_unknown_value_is_masked(self):
        root,row=self.fixture()
        sample=record();sample.update(source='human',teacher=False,format='duel',actual=dict(kind='end_turn'),action_index=0,human_control=True)
        sample['candidates'][sample['choice']]['kind']='end_turn'
        events=[dict(event='sample',record=sample),dict(event='complete',source_sha256='fixture',observer_version=OBSERVER_VERSION,expected_actions=1)]
        text='Battle for Wesnoth v1.18.8\n'+'\n'.join(PREFIX+json.dumps(e) for e in events)+'\n'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp,'capture.log');path.write_text(text)
            records,_=import_capture(path,row)
            self.assertIsNone(records[0]['reward']);self.assertFalse(records[0]['value_valid'])
            model=Policy('duel');optimizer=torch.optim.Adam(model.parameters())
            self.assertEqual(train(model,optimizer,records,'bc',epochs=1,minibatch=1)['updates'],1)
            path.write_text(text+'error replay: checkup mismatch\n')
            with self.assertRaises(ValueError): import_capture(path,row)
            path.write_text(text.split(PREFIX+'{"event": "complete"')[0])
            with self.assertRaises(ValueError): import_capture(path,row)

    def test_game_first_sampling_and_source_ratio(self):
        rows=[dict(record(game='long'),source='astra') for _ in range(100)]
        rows+=[dict(record(game='short'),source='astra')]
        rows+=[dict(record(game='human'),source='human',teacher=False)]
        for r in rows: r['split']='train'
        drawn=bc_sample(rows,10000,random.Random(19))
        human=sum(r['source']=='human' for r in drawn)
        short=sum(r['game_family']=='short' for r in drawn)
        self.assertTrue(2300<human<2700);self.assertTrue(3400<short<4100)
        bad=record();bad['split']='validation' if split('g')=='train' else 'train'
        with self.assertRaises(ValueError): validate_record(bad)
