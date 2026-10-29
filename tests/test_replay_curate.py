import bz2
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

    def test_hosted_archive_layout_is_curated_from_scenario_and_split_replay_blocks(self):
        # A replay dropped from the lobby has no [replay_start]: the starting
        # state is [scenario] plus [carryover_sides_start], and the history is
        # split over one [replay] holding only the upload log and one holding
        # the commands. Both blocks must be read, or the game looks empty.
        def archive(commands,seed='63d5121f',version='1.18.3'):
            uploaded='[replay]\n[upload_log]\n[/upload_log]\n[/replay]\n'
            scenario=('[scenario]\nid="multiplayer_The_Freelands"\nturns="30"\n'
                'map_data=" 1 Gg, 2 Gg, Gg, Gg, Gg, Gg"\n'
                '[side]\nside=1\nteam_name="one"\ncontroller="human"\ncurrent_player="a"\n'
                'faction="rebels"\ngold=100\n[/side]\n'
                '[side]\nside=2\nteam_name="two"\ncontroller="human"\ncurrent_player="b"\n'
                'faction="northerners"\ngold=100\n[/side]\n[/scenario]\n')
            carry='[carryover_sides_start]\nrandom_seed="'+seed+'"\nrandom_calls=0\n[/carryover_sides_start]\n'
            history='[replay]\n'+''.join('[command]\nfrom_side="1"\n[move]\nx='+str(c)+'\n[/move]\n[/command]\n'
                for c in commands)+'[/replay]\n'
            return ('version="'+version+'"\ncampaign_type="multiplayer"\nera_id="era_default"\n'
                +uploaded+scenario+carry+'[multiplayer]\nmp_scenario="multiplayer_The_Freelands"\n'
                'mp_era="era_default"\n[/multiplayer]\n'+history)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'raw';source.mkdir()
            for name,commands,seed in [('early.bz2',[1],'63d5121f'),('late.bz2',[1,2],'63d5121f'),
                                       ('other_seed.bz2',[1,2],'aa11')]:
                (source/name).write_bytes(bz2.compress(archive(commands,seed).encode()))
            before={p.name:p.read_bytes() for p in source.iterdir()}
            summary=curate(source,root/'curated')
            self.assertEqual(summary['selected_replays'],2)
            self.assertEqual(summary['selected_families'],2)
            self.assertEqual(summary['source_statuses']['earlier_save'],1)
            self.assertEqual(before,{p.name:p.read_bytes() for p in source.iterdir()})
            games=[json.loads(line) for line in (root/'curated/games.jsonl').read_text().splitlines()]
            latest=max(games,key=lambda g:g['actions'])
            self.assertEqual(latest['layout'],'archive')
            self.assertEqual(latest['actions'],2)
            self.assertEqual(latest['semantic_commands'],2)
            self.assertEqual(latest['scenario_id'],'multiplayer_The_Freelands')
            self.assertEqual(latest['initial_seed'],'63d5121f')
            self.assertEqual(latest['category'],'standard_multiplayer')
            self.assertEqual(latest['format'],'duel')
            self.assertEqual(latest['human_sides'],2)
            self.assertIn('server_archive_layout; no_replay_start_block',latest['notes'])
            self.assertEqual(latest['version'],'1.18.3')


if __name__=='__main__':unittest.main()
