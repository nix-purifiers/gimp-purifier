import os
import sys
from pathlib import Path

from gimp_purifier_prepare import prepare

state = os.environ["GIMP_PURIFIER_STATE"]
sdk = os.environ["GIMP_PURIFIER_LOCKED_SDK"]
env = os.environ.copy() | prepare(
    state,
    os.environ["GIMP_PURIFIER_ENVIRONMENT"],
    sdk,
    os.environ["GIMP_PURIFIER_CACHE"],
)
script = Path(sys.argv[1]).resolve()
exe = Path(sdk) / "bin/gimp-console"
os.execve(
    exe,
    [
        str(exe),
        "--new-instance",
        "--no-fonts",
        "--no-data",
        "--console-messages",
        "--batch-interpreter=python-fu-eval",
        "--batch",
        f"__import__('runpy').run_path({str(script)!r},run_name='__main__')",
        "--quit",
    ],
    env,
)
