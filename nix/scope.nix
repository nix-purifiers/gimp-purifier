{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.gimp;
  lockedSdk = pkgs.gimp.overrideAttrs (old: {
    postPatch = (old.postPatch or "") + ''
      ${pkgs.python3}/bin/python ${../native/patch_sdk.py}
    '';
  });
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  readLock = import ./read-lock.nix { inherit (pkgs) lib; };
  environment = scope.callPackage ./environment.nix { };
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  buildGimpProject = scope.callPackage ./build-project.nix { };
  emptyCache = pkgs.runCommand "gimp-immutable-empty" { } "mkdir -p $out";
  sdk = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      guard = builtins.hashFile "sha256" ../native/patch_sdk.py;
      runtime = builtins.hashFile "sha256" ../native/gimp_purifier_prepare.py;
      environment = builtins.hashFile "sha256" ./environment.nix;
    }
  );
})
