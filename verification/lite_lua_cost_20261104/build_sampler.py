"""Prepare a diagnostic copy of the exact shipped Lite crate with an instruction sampler."""
from pathlib import Path
from shutil import copy2, copytree, ignore_patterns
import sys


crate = Path(sys.argv[1])
copytree('engine_lite', crate, ignore=ignore_patterns('target', '__pycache__'))
copy2(Path(__file__).with_name('sample_lua.rs'), crate/'src/sample_lua.rs')
host = crate/'src/host.rs'
source = host.read_text()
old = 'let lua=Lua::new();'
assert source.count(old) == 1
host.write_text(source.replace(old, old+'crate::sample_lua::install(&lua);'))
lib = crate/'src/lib.rs'
lib.write_text(lib.read_text()+'\nmod sample_lua;\n')
