{
  lib,
  runCommand,
  python3,
  lockedSdk,
  environment,
  readLock,
  emptyCache,
  gnutar,
  gzip,
}:
{
  src,
  lockFile ? src + "/gimp-purifier.lock.json",
  script ? "build.py",
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = readLock { inherit src lockFile; };
  profile = environment { inherit lock fetchers; };
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = lib.fileset.unions [
      ../native/gimp_purifier_prepare.py
      ../native/run_project.py
    ];
  };
  projectSource = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".gimp-purifier"
        "__pycache__"
        "result"
        "output"
      ]);
  };
  project = runCommand "gimp-project" { } ''
    export GIMP_PURIFIER_ENVIRONMENT=${profile} GIMP_PURIFIER_LOCKED_SDK=${lockedSdk}
    export GIMP_PURIFIER_CACHE=${emptyCache}
    export HOME="$TMPDIR/home" XDG_CONFIG_HOME="$TMPDIR/config" XDG_DATA_HOME="$TMPDIR/data" XDG_CACHE_HOME="$TMPDIR/cache"
    mkdir -p "$HOME" "$out"
    cp -r ${projectSource} project
    chmod -R u+w project
    cd project
    export GIMP_PURIFIER_OUTPUT="$out" GIMP_PURIFIER_STATE="$TMPDIR/gimp-state"
    ${python3}/bin/python ${driver}/run_project.py ${lib.escapeShellArg script}
    ${lib.optionalString doCheck checkCommand}
  '';
  release =
    runCommand "gimp-project-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -cf - -C ${project} . | gzip -n > "$out/gimp-project.tar.gz"
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = profile;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
