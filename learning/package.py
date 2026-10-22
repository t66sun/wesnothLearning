from pathlib import Path
import zipfile
from .common import ROOT, write_json, sha256


def package_project(output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): raise FileExistsError(output)
    exclude={'.venv','.cache','.runtime','.ssh','runs','verification','tmp','__pycache__','delivery','.git',
             'references','humanData','datasets','.codegraph','.pi','target','.pytest_cache'}
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(ROOT.rglob('*')):
            relative=file.relative_to(ROOT)
            if any(part in exclude for part in relative.parts) or not file.is_file() or file.suffix=='.pyc': continue
            info=zipfile.ZipInfo('WesnothLearning/'+relative.as_posix())
            info.create_system=3
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o100755 if file.suffix=='.sh' else 0o100644)<<16
            archive.writestr(info,file.read_bytes())
    write_json(output.with_suffix('.json'),dict(file=output.name,sha256=sha256(output),
        note='训练工程；不包含运行数据、虚拟环境或已训练权重。'))
    return output
