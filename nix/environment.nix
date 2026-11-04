{
  lib,
  runCommand,
  writeText,
  fetchurl,
  fetchgit,
  python3,
  stdenv,
  meson,
  ninja,
  pkg-config,
  intltool,
  glib,
  fftw,
  lockedSdk,
  purifier,
  sdk,
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  archives = purifier.tree (
    {
      name = "gimp-plugin-sources";
      entries = checked.entries;
      inherit
        runCommand
        writeText
        fetchurl
        fetchgit
        python3
        ;
    }
    // fetchers
  );
  plugins = map (
    entry:
    stdenv.mkDerivation {
      pname = "gimp-plugin-${entry.name}";
      version = "locked";
      src = "${archives}/${entry.path}";
      nativeBuildInputs = [
        meson
        ninja
        pkg-config
        intltool
      ];
      buildInputs = [
        lockedSdk
        lockedSdk.gtk
        glib
        fftw
      ];
      env.PKG_CONFIG_GIMP_3_0_GIMPLIBDIR = "${placeholder "out"}/lib/gimp/3.0";
      env.PKG_CONFIG_GIMP_3_0_GIMPDATADIR = "${placeholder "out"}/share/gimp/3.0";
    }
  ) checked.entries;
  manifest = writeText "gimp-locked-plugins.json" (builtins.toJSON checked.data);
in
assert lib.assertMsg (checked.data.sdk == sdk) "GIMP SDK changed; run gimp-purifier lock --update";
runCommand "gimp-locked-plugins" { } ''
  mkdir -p "$out/plug-ins"
  ${lib.concatMapStringsSep "\n" (plugin: ''
    for item in ${plugin}/lib/gimp/3.0/plug-ins/*; do
      name=$(basename "$item")
      test ! -e "$out/plug-ins/$name"
      ln -s "$item" "$out/plug-ins/$name"
    done
  '') plugins}
  ln -s ${manifest} "$out/lock.json"
''
