"""Native source edits, preferences, ambient code rejection, networking and fallback."""

import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

cli = Path(sys.argv[1]).resolve()
sdk = Path(sys.argv[2]).resolve()
source = Path(__file__).resolve().parents[1]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"network works")

    def log_message(self, *args):
        pass


with tempfile.TemporaryDirectory(prefix="gimp-native-") as temporary:
    root = Path(temporary)
    project = root / "project"
    shutil.copytree(
        source / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".gimp-purifier", "output"),
    )
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GIMP") or key in {
            "DISPLAY",
            "WAYLAND_DISPLAY",
            "WAYLAND_SOCKET",
            "DBUS_SESSION_BUS_ADDRESS",
            "GTK_MODULES",
            "GTK3_MODULES",
            "GTK_PATH",
            "PYTHONPATH",
            "PYTHONHOME",
        }:
            env.pop(key, None)
    for key, name in [
        ("HOME", "home"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_RUNTIME_DIR", "runtime"),
    ]:
        (root / name).mkdir(mode=0o700)
        env[key] = str(root / name)
    env |= {
        "GIMP_PURIFIER_PROJECT": str(project),
        "NO_AT_BRIDGE": "1",
        "GTK_USE_PORTAL": "0",
        "DBUS_SYSTEM_BUS_ADDRESS": "unix:path=" + str(root / "no-system-bus"),
    }
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    script = project / "build.py"
    script.write_text(
        script.read_text()
        + f"""
import urllib.request,sys
assert Path(sys.pycache_prefix).is_relative_to('/nix/store')
assert Gimp.gimprc_query('plug-in-path')==os.environ['GIMP_PURIFIER_PLUGINS']
assert Gimp.gimprc_query('script-fu-path')==os.environ['GIMP_PURIFIER_SCRIPTS']
counter=int(Gimp.gimprc_query('purifier-counter') or '0')+1
assert Gimp.gimprc_set('purifier-counter',str(counter))
(p.parent/'counter.txt').write_text(str(counter))
with urllib.request.urlopen('http://127.0.0.1:{server.server_port}/') as response:assert response.read()==b'network works'
"""
    )
    args = [
        "--new-instance",
        "--no-fonts",
        "--no-data",
        "--console-messages",
        "--batch-interpreter=python-fu-eval",
        "--batch",
        f"__import__('runpy').run_path({str(script)!r},run_name='__main__')",
        "--quit",
    ]
    lock = project / "gimp-purifier.lock.json"
    before = lock.read_bytes()
    hashes = []
    try:
        for counter, size in enumerate([8, 9, 8], 1):
            (project / "size.json").write_text(json.dumps({"size": size}))
            result = subprocess.run(
                [cli / "bin/gimp-console", *args],
                env=env,
                cwd=project,
                capture_output=True,
                text=True,
                check=False,
                timeout=90,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            assert (project / "output/counter.txt").read_text() == str(counter)
            hashes.append(
                hashlib.sha256((project / "output/image.ppm").read_bytes()).hexdigest()
            )
            assert lock.read_bytes() == before
            if counter == 1:
                ambient = root / "ambient"
                (ambient / "ambient").mkdir(parents=True)
                marker = root / "ambient-ran"
                executable = ambient / "ambient/ambient"
                executable.write_text("#!/bin/sh\n" + f"touch {marker}\n")
                executable.chmod(0o755)
                profile = project / ".gimp-purifier/profile"
                with (profile / "gimprc").open("a") as f:
                    f.write(
                        "\n(plug-in-path "
                        + json.dumps(
                            str(ambient) + ":" + str(sdk / "lib/gimp/3.0/plug-ins")
                        )
                        + ")\n"
                    )
                control_env = env | {"GIMP3_DIRECTORY": str(profile)}
                result = subprocess.run(
                    [
                        sdk / "bin/gimp-console",
                        *args[:-3],
                        "--batch",
                        "print('native control')",
                        "--quit",
                    ],
                    env=control_env,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=90,
                )
                assert result.returncode == 0, result.stdout + result.stderr
                assert marker.exists(), (
                    "original native loader did not execute ambient code"
                )
                marker.unlink()
            else:
                assert not marker.exists(), "locked native loader executed ambient code"
    finally:
        server.shutdown()
        server.server_close()
    assert hashes[0] != hashes[1] and hashes[0] == hashes[2]
    (project / "gimp-purifier.json").write_text('{"plugins": []}')
    failed = subprocess.run(
        [cli / "bin/gimp", "--version"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode and "selection changed" in failed.stderr
    lock.unlink()
    for name in ["gimp", "gimp-console"]:
        for arguments in [["--version"], ["--purifier-invalid"]]:
            expected = subprocess.run(
                [sdk / "bin" / name, *arguments],
                env=env,
                capture_output=True,
                check=False,
            )
            actual = subprocess.run(
                [cli / "bin" / name, *arguments],
                env=env,
                capture_output=True,
                check=False,
            )
            warning = b"warning: no GIMP purifier lock; using ordinary, impure plug-in resolution\n"
            assert actual.returncode == expected.returncode
            assert (
                actual.stdout == expected.stdout
                and actual.stderr == warning + expected.stderr
            )
print("GIMP native source/preferences/code boundaries/network/fallback passed")
