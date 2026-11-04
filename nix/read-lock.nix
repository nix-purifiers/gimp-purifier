{ lib }:
{
  src,
  lockFile ? src + "/gimp-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  selection =
    if builtins.pathExists (src + "/gimp-purifier.json") then
      builtins.fromJSON (builtins.readFile (src + "/gimp-purifier.json"))
    else
      null;
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "gimp"
    && builtins.isString (data.sdk or null)
    && builtins.isAttrs (data.selection or null)
    && data.selection == selection
    && builtins.isList (data.selection.plugins or null)
    && builtins.all (
      plugin:
      builtins.isAttrs plugin
      && builtins.isString (plugin.name or null)
      && builtins.isString (plugin.url or null)
      && (plugin.build or null) == "meson"
    ) data.selection.plugins
    && builtins.isList entries
    && builtins.all (
      entry:
      builtins.isAttrs entry
      && builtins.isString (entry.name or null)
      && builtins.match "[a-zA-Z0-9][a-zA-Z0-9._-]*" entry.name != null
      && (entry.path or null) == "${entry.name}.tar"
      && (entry.build or null) == "meson"
      && builtins.isString (entry.url or null)
      && lib.hasPrefix "https://" entry.url
      && builtins.isString (entry.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" entry.hash != null
      && builtins.isList (entry.mirrors or null)
      && builtins.all builtins.isString entry.mirrors
    ) entries
    && builtins.length (lib.unique (map (entry: entry.path) entries)) == builtins.length entries
    && (map (entry: { inherit (entry) name url build; }) entries) == data.selection.plugins;
in
{
  purifier = "gimp";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "GIMP lock is missing, malformed, or stale; run gimp-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
