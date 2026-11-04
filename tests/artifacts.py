"""Consume exported native image output, external locks and exact release assets."""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

cli = Path(sys.argv[1]).resolve() / "bin/gimp-purifier"
original = Path(sys.argv[2]).resolve()
source = Path(__file__).resolve().parents[1]


def call(arguments, *, env, cwd):
    result = subprocess.run(
        arguments, check=False, env=env, cwd=cwd, text=True, capture_output=True
    )
    assert result.returncode==0,result.stdout+result.stderr
    return result.stdout.strip()


with tempfile.TemporaryDirectory(prefix="gimp-artifacts-") as temporary:
    root = Path(temporary)
    project = root / "project"
    shutil.copytree(
        source / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".gimp-purifier"),
    )
    env = os.environ.copy() | {
        "HOME": str(root / "home"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "QT_QPA_PLATFORM": "offscreen",
    }
    for name in ["home", "data", "config", "cache"]:
        (root / name).mkdir()
    args = [str(cli), "--project", str(project)]
    build = Path(call([*args, "build"], env=env, cwd=root))
    image = build / "image.ppm"
    assert image.read_bytes() == b"P6\n8 8\n255\n" + bytes([255, 0, 0]) * 64
    consumer = root / "consumer.py"
    consumer.write_text(
        "from gi.repository import Gimp,Gio,Gegl\n"
        f"image=Gimp.file_load(Gimp.RunMode.NONINTERACTIVE,Gio.File.new_for_path({str(image)!r}))\n"
        "assert image.get_width()==8 and image.get_height()==8\n"
        "pixels=image.get_layers()[0].get_buffer().get(Gegl.Rectangle.new(0,0,8,8),1.0,\"R'G'B' u8\",Gegl.AbyssPolicy.NONE)\n"
        "assert bytes(pixels)==bytes([255,0,0])*64\n"
        "image.delete()\n"
    )
    call(
        [
            str(original / "bin/gimp-console"),
            "--new-instance",
            "--no-fonts",
            "--no-data",
            "--console-messages",
            "--batch-interpreter=python-fu-eval",
            "--batch",
            f"__import__('runpy').run_path({str(consumer)!r})",
            "--quit",
        ],
        env=env,
        cwd=root,
    )
    release = Path(call([*args, "bundle"], env=env, cwd=root))
    archive = release / "gimp-project.tar.gz"
    with tarfile.open(archive) as tar:
        assert (
            tar.extractfile("./image.ppm").read() == (build / "image.ppm").read_bytes()
        )
    external = root / "external-lock.json"
    shutil.copyfile(project / "gimp-purifier.lock.json", external)
    replay = Path(call([*args, "--lock", str(external), "bundle"], env=env, cwd=root))
    assert (replay / archive.name).read_bytes() == archive.read_bytes()
    fake = root / "gh"
    fake.write_text(
        f"#!{sys.executable}\nimport json,os,sys\nfrom pathlib import Path\n"
        "Path(os.environ['UPLOAD_RECORD']).write_text(json.dumps(sys.argv[1:]))\n"
        "Path(os.environ['UPLOAD_BYTES']).write_bytes(Path(sys.argv[4]).read_bytes())\n"
    )
    fake.chmod(0o755)
    publish_env = env | {
        "GIMP_PURIFIER_GH": str(fake),
        "UPLOAD_RECORD": str(root / "upload.json"),
        "UPLOAD_BYTES": str(root / "upload.tar.gz"),
    }
    call([*args, "publish", "--tag", "proof"], env=publish_env, cwd=root)
    record = json.loads((root / "upload.json").read_text())
    assert record[:3] == ["release", "upload", "proof"] and record[3] == str(archive)
    assert (root / "upload.tar.gz").read_bytes() == archive.read_bytes()
print("native GIMP artifact consumers passed")
