{
  lib,
  runCommand,
  writeText,
  makeWrapper,
  python3,
  original,
  lockedSdk,
  sdk,
  emptyCache,
  nix,
  gh,
  cacert,
  nixpkgsSrc,
  purifierSrc,
}:
let
  integration = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      (lib.fileset.fileFilter (file: file.hasExt "py") ../gimp_purifier)
      (lib.fileset.fileFilter (file: file.hasExt "py") ../native)
      (lib.fileset.fileFilter (file: file.hasExt "nix") ./.)
    ];
  };
  bootstrap = writeText "gimp-purifier-main.py" "import os,runpy,sys; sys.path.insert(0, ${builtins.toJSON integration}); sys.argv[0]=os.environ['GIMP_PURIFIER_COMMAND']; runpy.run_module('gimp_purifier.main',run_name='__main__')";
  realize = writeText "gimp-purifier-realize.nix" ''
    { lockPath, projectPath, target ? "environment" }:
    let
      pkgs = import (builtins.storePath "${nixpkgsSrc}") {};
      scope = import ${integration}/nix/scope.nix {
        inherit pkgs;
        nixpkgsSrc = builtins.storePath "${nixpkgsSrc}";
        purifierSrc = builtins.storePath "${purifierSrc}";
      };
      lockFile = builtins.toPath lockPath;
      src = if target == "environment" then builtins.toPath projectPath else builtins.path {
        path = builtins.toPath projectPath;
        name = "gimp-project";
        filter = path: type: !(builtins.elem (baseNameOf path) [ ".git" ".gimp-purifier" "__pycache__" "result" "output" ]);
      };
      build = scope.buildGimpProject { inherit src lockFile; };
    in if target == "environment" then scope.environment { lock = scope.readLock { inherit src lockFile; }; }
       else if target == "project" then build.packages.project
       else if target == "release" then build.release
       else throw "Unknown GIMP purifier target"
  '';
in
runCommand "gimp-purifier" { nativeBuildInputs = [ makeWrapper ]; } ''
  mkdir -p "$out/bin"
  for name in gimp-purifier gimp gimp-console; do
    makeWrapper ${python3}/bin/python "$out/bin/$name" \
      --add-flags ${bootstrap} \
      --set GIMP_PURIFIER_COMMAND "$name" \
      --set GIMP_PURIFIER_NATIVE ${integration}/native \
      --set GIMP_PURIFIER_ORIGINAL ${original} \
      --set GIMP_PURIFIER_LOCKED_SDK ${lockedSdk} \
      --set GIMP_PURIFIER_SDK ${sdk} \
      --set GIMP_PURIFIER_CACHE ${emptyCache} \
      --set GIMP_PURIFIER_REALIZE ${realize} \
      --set-default GIMP_PURIFIER_GH ${gh}/bin/gh \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default NIX_SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --prefix PATH : ${
        lib.makeBinPath [
          nix
          gh
        ]
      }
  done
''
