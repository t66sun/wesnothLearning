from pathlib import Path
import json
import tempfile
import unittest
import zipfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import addons
import native
import params as P
from match import rank_points


class SDKTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_templates(self):
        self.assertEqual(addons.validate(native.ROOT/'sdk/template_bot'),'template_bot')
        self.assertEqual(addons.validate(native.ROOT/'sdk/sample_bot'),'sample_bot')
    def test_create_pack_install(self):
        bot=addons.create('TeamA',self.root)
        package=addons.pack(bot,self.root/'TeamA.zip')
        with addons.open_addon(package) as unpacked:
            self.assertEqual(addons.validate(unpacked),'TeamA')
            self.assertEqual((bot/'lua/bot.lua').read_bytes(),(unpacked/'lua/bot.lua').read_bytes())
        dest=addons.install(package,self.root/'user')
        self.assertTrue((dest/'_main.cfg').is_file())
        with self.assertRaises(ValueError): addons.install(package,self.root/'user')
    def test_no_overwrite(self):
        bot=addons.create('TeamA',self.root)
        with self.assertRaises(ValueError): addons.create('TeamA',self.root)
        package=addons.pack(bot,self.root/'TeamA.zip')
        with self.assertRaises(FileExistsError): addons.pack(bot,package)
    def test_registration_tamper(self):
        bot=addons.create('TeamA',self.root)
        (bot/'_main.cfg').write_text('[event]\n[/event]\n',encoding='utf-8')
        with self.assertRaises(ValueError): addons.validate(bot)
    def test_native_only(self):
        bot=addons.create('TeamA',self.root)
        (bot/'old_bot.exe').write_bytes(b'MZ')
        with self.assertRaises(ValueError): addons.validate(bot)
    def test_manifest(self):
        bot=addons.create('TeamA',self.root)
        (bot/'arena.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError): addons.validate(bot)
    def test_names(self):
        for name in ('../bad','baseline','human','Bad-name','中文','1Team','CON','COM1',''):
            with self.subTest(name=name),self.assertRaises(ValueError): addons.valid_name(name)
    def test_zip_traversal(self):
        for name in ('../bad','/bad','C:/bad','team/../../bad','team\\bad','team/./file.lua','team//file.lua','team/CON.lua','team/file.lua '):
            path=self.root/'bad.zip'
            with zipfile.ZipFile(path,'w') as z: z.writestr(name,'bad')
            with self.subTest(name=name),self.assertRaises(ValueError):
                with addons.open_addon(path): pass
    def test_duplicate_zip(self):
        path=self.root/'bad.zip'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('team/FILE.lua','a');z.writestr('team/file.lua','b')
        with self.assertRaises(ValueError):
            with addons.open_addon(path): pass
    def test_zip_limit(self):
        path=self.root/'large.zip'
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('team/file.lua',b' '*(addons.MAX_PACKAGE_BYTES+1))
        with self.assertRaises(ValueError):
            with addons.open_addon(path): pass
    def test_pack_inside_source(self):
        bot=addons.create('TeamA',self.root)
        with self.assertRaises(ValueError): addons.pack(bot,bot/'output.zip')
    def test_maps(self):
        for count in P.PLAYERS:
            board=native.load_map(count)
            self.assertEqual(len(board['starts']),count)
            rows=native.map_wml(board).splitlines()
            self.assertEqual(len(rows),len(board['terrain'])+2)
            self.assertEqual(len(rows[0].split(',')),len(board['terrain'][0])+2)
            for s in range(1,count+1): self.assertIn(f'{s} Kh',native.map_wml(board))
    def test_native_scenario(self):
        cfg=native.scenario(dict(max_turns=30,fog=True,token='test'),list(P.FACTIONS[:4]))
        self.assertIn('experience_modifier=70',cfg)
        self.assertEqual(cfg.count('[side]'),4)
        self.assertEqual(cfg.count('fog=yes'),4)
    def test_ranking(self):
        points=rank_points(4,[3,4],{1:3,2:6},{})
        self.assertEqual(points,{1:0,2:1,3:2.5,4:2.5})
        self.assertEqual(sum(points.values()),6)
    def test_same_round_tie(self):
        self.assertEqual(rank_points(4,[4],{1:3,2:3,3:5},{}),{1:.5,2:.5,3:2,4:3})
    def test_dq_last(self):
        self.assertEqual(rank_points(4,[4],{1:10,2:3,3:4},{1:'timeout'}),{1:0,2:1,3:2,4:3})
    def test_all_dq(self):
        self.assertEqual(rank_points(2,[],{1:1,2:2},{1:'a',2:'b'}),{1:.5,2:.5})


if __name__=='__main__': unittest.main()
