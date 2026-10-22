import gzip
import json
from pathlib import Path
import tempfile
import unittest

from learning.replay_curate import curate, inspect_file, parse_wml


def save(commands, seed='abc', snapshot=True):
    return ('version="1.18.8"\ncampaign_type="multiplayer"\nera_id="era_default"\n'
        '[replay_start]\nid="same_map"\nmap_data="1 Gg, 2 Gg"\nrandom_seed="'+seed+'"\n'
        '[side]\nside=1\nteam_name="one"\ncontroller="human"\ncurrent_player="a"\n[/side]\n'
        '[side]\nside=2\nteam_name="two"\ncontroller="human"\ncurrent_player="b"\n[/side]\n'
        '[/replay_start]\n[replay]\n'+''.join(
            '[command]\n[move]\nx='+str(c)+'\n[/move]\n[/command]\n' for c in commands)
        +'[/replay]\n'+('[snapshot]\nturn_at=99\n[/snapshot]\n' if snapshot else ''))


class ReplayCurateTests(unittest.TestCase):
    def test_same_run_prefixes_collapse_but_divergent_branches_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'raw';source.mkdir()
            examples={'early.gz':save([1]),'branch_a.gz':save([1,2]),
                      'branch_b.gz':save([1,3]),'different_seed.gz':save([1,2],seed='other')}
            for name,text in examples.items():(source/name).write_bytes(gzip.compress(text.encode()))
            before={p.name:p.read_bytes() for p in source.iterdir()}
            summary=curate(source,root/'curated')
            self.assertEqual(summary['selected_replays'],3)
            self.assertEqual(summary['selected_families'],2)
            self.assertEqual(summary['branched_families'],1)
            self.assertEqual(summary['source_statuses']['earlier_save'],1)
            self.assertEqual(before,{p.name:p.read_bytes() for p in source.iterdir()})

    def test_container_duplicates_and_unicode_names_become_numbered_gzip(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'raw';source.mkdir()
            payload=save([1,2],snapshot=False).encode()
            (source/'中文录像').write_bytes(payload)
            (source/'duplicate.gz').write_bytes(gzip.compress(payload,mtime=5))
            (source/'same_payload.gz').write_bytes(gzip.compress(payload,mtime=10))
            summary=curate(source,root/'curated')
            self.assertEqual(summary['selected_replays'],1)
            self.assertEqual(summary['source_statuses']['payload_duplicate'],2)
            files=list((root/'curated/replays').rglob('*.gz'))
            self.assertEqual(files[0].name,'game_0001.gz')
            self.assertTrue(files[0].relative_to(root/'curated').as_posix().isascii())
            self.assertEqual(gzip.decompress(files[0].read_bytes()),payload)
            game=json.loads((root/'curated/games.jsonl').read_text())
            self.assertEqual(game['format'],'duel')
            self.assertFalse(game['end_marker'])

    def test_random_initial_unit_facing_does_not_split_one_game(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'raw';source.mkdir()
            for name,commands,facing in [('early.gz',[1],'ne'),('late.gz',[1,2],'sw')]:
                text=save(commands).replace('side=1\n','side=1\n[unit]\ntype="Elvish Captain"\nx=1\ny=1\nfacing="'+facing+'"\n[/unit]\n',1)
                (source/name).write_bytes(gzip.compress(text.encode()))
            summary=curate(source,root/'curated')
            self.assertEqual(summary['selected_replays'],1)

    def test_async_unit_renaming_is_not_a_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'raw';source.mkdir()
            (source/'early.gz').write_bytes(gzip.compress(save([1]).encode()))
            text=save([1,2]).replace('[replay]\n','[replay]\n[command]\nasync=yes\n[rename]\nname="new name"\nx=1\ny=1\n[/rename]\n[/command]\n',1)
            (source/'late.gz').write_bytes(gzip.compress(text.encode()))
            summary=curate(source,root/'curated')
            self.assertEqual(summary['selected_replays'],1)

    def test_incomplete_last_checkup_is_a_prefix_but_different_rolls_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'raw';source.mkdir()
            texts={
                'partial.gz':save([1]).replace('[/move]','[/move]\n[checkup]\n[/checkup]'),
                'complete.gz':save([1,2]).replace('[/move]','[/move]\n[checkup]\n[result]\nhits=yes\n[/result]\n[/checkup]'),
                'other_roll.gz':save([1,3]).replace('[/move]','[/move]\n[checkup]\n[result]\nhits=no\n[/result]\n[/checkup]')}
            for name,text in texts.items():(source/name).write_bytes(gzip.compress(text.encode()))
            summary=curate(source,root/'curated')
            self.assertEqual(summary['selected_replays'],2)
            self.assertEqual(summary['branched_families'],1)

    def test_tag_looking_text_inside_multiline_strings_is_not_a_tag(self):
        node=parse_wml('[side]\ndescription="line\n[command]\nquoted ""text""\n"\n[/side]')
        self.assertEqual(node.children[0].tag,'side')
        self.assertFalse(node.children[0].children)
        self.assertIn('[command]',node.children[0].attrs['description'])

    def test_saved_translatable_strings_can_continue_after_plus(self):
        node=parse_wml('name=_"Unit Test " +\n#textdomain test\n "runtime"\n[unit]\nhelp=_"One" +\n _"\nTwo"\n[/unit]')
        self.assertEqual(node.attrs['name'],'Unit Test runtime')
        self.assertEqual(node.children[0].attrs['help'],'One\nTwo')

    def test_parse_error_does_not_become_an_empty_valid_replay(self):
        with self.assertRaises(ValueError):parse_wml('[snapshot]\n[/replay]')
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'metadata.vdf';p.write_text('"steam"\n{\n}')
            self.assertEqual(inspect_file(p,p.parent)['status'],'not_replay')


if __name__=='__main__':unittest.main()
