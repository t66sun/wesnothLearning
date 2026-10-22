import unittest
from learning.experiment import default_config,validate_config
from learning.__main__ import parser,run_config
from learning.sample import collect
from learning.coordinator import broker


class WorkerLimitTests(unittest.TestCase):
    def test_global_limit_and_cli_defaults(self):
        config=default_config()
        self.assertEqual(config['workers'],8)
        for n in (1,4,16):validate_config(config|dict(workers=n))
        self.assertEqual(run_config(parser().parse_args(['run']))['workers'],8)
        cpu=run_config(parser().parse_args(['run','--device','cpu']))
        self.assertEqual((cpu['device'],cpu['workers'],cpu['trainer_threads']),('cpu',8,1))
        self.assertEqual(parser().parse_args(['collect','--jobs','jobs','--output','out']).workers,8)
        self.assertEqual(parser().parse_args(['evaluate','--jobs','jobs','--output','out','--format','duel']).workers,8)
        for n in (0,17):
            with self.assertRaises(ValueError):validate_config(config|dict(workers=n))
            with self.assertRaises(ValueError):collect([],n,'unused')
            with self.assertRaises(ValueError):broker({},None,{},n,'unused')
