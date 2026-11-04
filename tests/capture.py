"""Fresh native capture, cold replay and atomic failure against the public catalog."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

cli = Path(sys.argv[1]).resolve() / "bin/gimp-purifier"
source = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="gimp-capture-") as temporary:
    project = Path(temporary)
    shutil.copyfile(
        source / "examples/minimal/gimp-purifier.json",
        project / "gimp-purifier.json",
    )
    env = os.environ.copy() | {"GIMP_PURIFIER_PROJECT": str(project)}
    subprocess.run([str(cli), "lock", "--update"], check=True, env=env, cwd=project)
    lock = project / "gimp-purifier.lock.json"
    before = lock.read_bytes()
    subprocess.run([str(cli), "lock"], check=True, env=env, cwd=project)
    subprocess.run([str(cli), "prefetch"], check=True, env=env, cwd=project)
    assert lock.read_bytes() == before
    selection_file = project / "gimp-purifier.json"
    selection = json.loads(selection_file.read_text())
    selection["plugins"].append(
        {
            "name": "missing",
            "build": "meson",
            "url": "https://github.com/nix-purifiers/missing-gimp-plugin-probe/archive/nonexistent.tar.gz",
        }
    )
    selection_file.write_text(json.dumps(selection))
    failed = subprocess.run(
        [str(cli), "lock", "--update"], check=False, env=env, cwd=project
    )
    assert failed.returncode != 0 and lock.read_bytes() == before
    empty = project / "empty"
    empty.mkdir()
    (empty / "gimp-purifier.json").write_text('{"plugins": []}\n')
    empty_env = env | {"GIMP_PURIFIER_PROJECT": str(empty)}
    subprocess.run([str(cli), "lock", "--update"], check=True, env=empty_env, cwd=empty)
    subprocess.run(
        [str(cli), "exec", "--", "--version"], check=True, env=empty_env, cwd=empty
    )

print("native gimp capture and atomic failure passed")
