"""Create a portable source archive plus a patch against the retrieved GitHub snapshot."""
from pathlib import Path
import difflib
import zipfile
root=Path(__file__).resolve().parents[1]
base=Path('/private/tmp/pulsepath-base')
files=[*root.glob('pi/*.py'),root/'pi/requirements.txt',root/'pi/requirements-world.txt',root/'pi/data/obstacles.json',*root.glob('web/static/*'),*root.glob('web/templates/*'),*root.glob('tools/*.py'),*root.glob('tests/*.py'),*root.glob('docs/*'),root/'arduino/haptic_controller/haptic_controller.ino']
files=[p for p in files if p.is_file() and p.name!='package_changes.py']
out=root/'deliverables';out.mkdir(exist_ok=True)
with zipfile.ZipFile(out/'pulsepath-checkpoints.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(root))
patch=[]
for p in files:
    if p.suffix=='.png':continue
    rel=p.relative_to(root).as_posix();old=base/rel
    # The original world requirements were retrieved unchanged later.
    if rel=='pi/requirements-world.txt':continue
    before=old.read_text().splitlines(keepends=True) if old.exists() else []
    after=p.read_text().splitlines(keepends=True)
    for line in difflib.unified_diff(before,after,fromfile='a/'+rel if old.exists() else '/dev/null',tofile='b/'+rel):
        patch.append(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n')
(out/'vision-checkpoints.patch').write_text(''.join(patch))
print(f'Packaged {len(files)} files; model weights, environment and camera frames excluded.')
