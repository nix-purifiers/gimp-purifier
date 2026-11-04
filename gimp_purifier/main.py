"""GIMP's normal application workflow with a frozen native extension profile."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def public_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("GIMP addon repositories must use public HTTPS URLs")
    return url


def selection(project):
    import re

    value = json.loads((project / "gimp-purifier.json").read_text())
    if set(value) != {"plugins"} or not isinstance(value["plugins"], list):
        raise ValueError("gimp-purifier.json needs a plugins list")
    names = []
    for plugin in value["plugins"]:
        if not isinstance(plugin, dict) or set(plugin) != {"name", "url", "build"}:
            raise ValueError("plugins need name, url and build")
        if not isinstance(plugin["name"], str) or not re.fullmatch(
            "[a-zA-Z0-9][a-zA-Z0-9._-]*", plugin["name"]
        ):
            raise ValueError("invalid plug-in name")
        if plugin["build"] != "meson":
            raise ValueError("only native Meson builds are supported")
        public_url(plugin["url"])
        names.append(plugin["name"])
    if len(names) != len(set(names)):
        raise ValueError("duplicate plug-in names")
    return value


def project_path(explicit):
    if explicit:
        return Path(explicit).resolve()
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "gimp-purifier.json").exists() or (
            parent / "gimp-purifier.lock.json"
        ).exists():
            return parent
    return current


def validate(project, lock):
    data = json.loads(lock.read_text())
    if data.get("version") != 1 or data.get("purifier") != "gimp":
        raise ValueError("unsupported GIMP lock")
    if data.get("sdk") != os.environ["GIMP_PURIFIER_SDK"]:
        raise ValueError("GIMP SDK changed; run gimp-purifier lock --update")
    if data.get("selection") != selection(project):
        raise ValueError("extension selection changed; run gimp-purifier lock --update")
    return data


def realize(project, lock, target="environment", out_link=None):
    args = [
        "nix",
        "build",
        "--impure",
        "--file",
        os.environ["GIMP_PURIFIER_REALIZE"],
        "--argstr",
        "projectPath",
        str(project),
        "--argstr",
        "lockPath",
        str(lock),
        "--argstr",
        "target",
        target,
        "--json",
    ]
    args += ["--out-link", str(out_link)] if out_link else ["--no-link"]
    result = run(args, stdout=subprocess.PIPE, text=True)
    return Path(json.loads(result.stdout)[0]["outputs"]["out"])


def prefetch(url):
    return json.loads(
        run(
            ["nix", "store", "prefetch-file", "--json", public_url(url)],
            stdout=subprocess.PIPE,
            text=True,
        ).stdout
    )


def capture(project, lock):
    requested = selection(project)
    entries = []
    for plugin in requested["plugins"]:
        fetched = prefetch(plugin["url"])
        entries.append(
            {
                "path": plugin["name"] + ".tar",
                "url": plugin["url"],
                "hash": fetched["hash"],
                "mirrors": [],
                "build": plugin["build"],
                "name": plugin["name"],
            }
        )
    data = {
        "version": 1,
        "purifier": "gimp",
        "sdk": os.environ["GIMP_PURIFIER_SDK"],
        "selection": requested,
        "entries": entries,
    }
    with tempfile.TemporaryDirectory(prefix="gimp-capture-") as temporary:
        candidate = Path(temporary) / "gimp-purifier.lock.json"
        candidate.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        realize(project, candidate)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=lock.parent, delete=False
        ) as output:
            output.write(candidate.read_text())
            pending = Path(output.name)
        try:
            os.replace(pending, lock)
        finally:
            pending.unlink(missing_ok=True)


def prepared_environment(project, lock):
    data = validate(project, lock)
    state = project / ".gimp-purifier"
    identity = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    roots = state / "environments"
    roots.mkdir(parents=True, exist_ok=True)
    environment = realize(project, lock, out_link=roots / identity)
    alias = state / "environment"
    if alias.exists() and not alias.is_symlink():
        raise ValueError("unexpected file at the managed GIMP environment link")
    with tempfile.TemporaryDirectory(dir=state) as temporary:
        link = Path(temporary) / "environment"
        link.symlink_to(environment)
        os.replace(link, alias)
    return state, environment


def native_exec(project, lock, arguments, command="gimp"):
    executable = Path(os.environ["GIMP_PURIFIER_ORIGINAL"]) / "bin" / command
    if not lock.exists():
        print(
            "warning: no GIMP purifier lock; using ordinary, impure plug-in resolution",
            file=sys.stderr,
        )
        os.execve(executable, [str(executable), *arguments], os.environ.copy())
    state, environment = prepared_environment(project, lock)
    sys.path.insert(0, os.environ["GIMP_PURIFIER_NATIVE"])
    from gimp_purifier_prepare import prepare

    env = os.environ.copy() | prepare(
        state,
        environment,
        os.environ["GIMP_PURIFIER_LOCKED_SDK"],
        os.environ["GIMP_PURIFIER_CACHE"],
    )
    executable = Path(os.environ["GIMP_PURIFIER_LOCKED_SDK"]) / "bin" / command
    os.execve(executable, [str(executable), "--new-instance", *arguments], env)


def main():
    if os.environ.get("GIMP_PURIFIER_COMMAND") not in {None, "gimp-purifier"}:
        project = project_path(os.environ.get("GIMP_PURIFIER_PROJECT"))
        lock = Path(
            os.environ.get("GIMP_PURIFIER_LOCK", project / "gimp-purifier.lock.json")
        ).resolve()
        native_exec(project, lock, sys.argv[1:], os.environ["GIMP_PURIFIER_COMMAND"])
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--lock")
    sub = parser.add_subparsers(dest="action", required=True)
    lock_parser = sub.add_parser("lock")
    lock_parser.add_argument("--update", action="store_true")
    sub.add_parser("prefetch")
    for name in ["build", "bundle"]:
        sub.add_parser(name)
    publish = sub.add_parser("publish")
    publish.add_argument("--tag", required=True)
    execute = sub.add_parser("exec")
    execute.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    project = project_path(args.project or os.environ.get("GIMP_PURIFIER_PROJECT"))
    lock = Path(
        args.lock
        or os.environ.get("GIMP_PURIFIER_LOCK", project / "gimp-purifier.lock.json")
    ).resolve()
    if args.action == "lock" and args.update:
        capture(project, lock)
        return
    if args.action == "exec":
        arguments = (
            args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        )
        native_exec(project, lock, arguments)
        return
    validate(project, lock)
    if args.action == "lock":
        realize(project, lock)
    elif args.action == "prefetch":
        print(realize(project, lock))
    elif args.action in {"build", "bundle"}:
        print(
            realize(project, lock, "project" if args.action == "build" else "release")
        )
    elif args.action == "publish":
        release = realize(project, lock, "release")
        run(
            [
                os.environ.get("GIMP_PURIFIER_GH", "gh"),
                "release",
                "upload",
                args.tag,
                str(release / "gimp-project.tar.gz"),
                "--clobber",
            ]
        )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"gimp-purifier: {error}", file=sys.stderr)
        sys.exit(1)
