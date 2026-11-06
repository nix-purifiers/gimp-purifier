# SPDX-License-Identifier: MIT
{ pkgs, build }:
let
  plain = build { src = ../examples/minimal; };
  args = {
    src = ../examples/minimal;
    resourceRoots."image.ppm" = "image.ppm";
    doCheck = true;
    checkCommand = ''
      test -s "$out/image.ppm"
      printf 'private sibling\n' > "$out/private.txt"
    '';
  };
  selected = build args;
  rejects =
    name: roots: expected:
    let
      actual = (build (args // { resourceRoots = roots; })).projections.resources;
    in
    actual.overrideAttrs (old: {
      name = "gimp-resource-reject-${name}";
      buildCommand = ''
        if ( ${old.buildCommand} ) > "$TMPDIR/rejection.log" 2>&1; then
          echo "unexpectedly accepted ${name}" >&2
          exit 1
        fi
        ${pkgs.lib.concatMapStringsSep "\n" (
          message: "grep -F -- ${pkgs.lib.escapeShellArg message} \"$TMPDIR/rejection.log\""
        ) expected}
        mkdir -p "$out"
        cp "$TMPDIR/rejection.log" "$out/rejection.log"
      '';
    });
  missing = rejects "missing-output" { "missing.ppm" = "missing.ppm"; } [
    "FileNotFoundError:"
    "missing.ppm"
  ];
  unsafeSource = rejects "source-traversal" { "image.ppm" = "../private.txt"; } [
    "canonical relative resource path: ../private.txt"
  ];
  unsafeDestination = rejects "destination-traversal" { "../escape.ppm" = "image.ppm"; } [
    "canonical relative resource path: ../escape.ppm"
  ];
  projection = selected.packages.project.projections.resources;
  consumers = import ./resource-consumer.nix {
    inherit pkgs projection;
    excluded = [
      "private.txt"
      "size.json"
      "gimp-purifier.lock.json"
    ];
  };
in
assert plain.projections == { };
assert selected.projections.resources == projection;
pkgs.runCommand "gimp-resource-projections" { nativeBuildInputs = [ pkgs.python3 ]; } ''
  test -e ${consumers}
  test -e ${missing}
  test -e ${unsafeSource}
  test -e ${unsafeDestination}
  test -e ${selected.packages.project}/private.txt
  python - <<'PY'
  import hashlib, json, pathlib, zipfile
  root = pathlib.Path('${projection.directory}')
  catalog = json.load(open('${projection.catalog}'))
  assert sorted(catalog['files']) == ['image.ppm']
  exported = (root / 'image.ppm').read_bytes()
  native = pathlib.Path('${selected.packages.project}/image.ppm').read_bytes()
  assert hashlib.sha256(exported).digest() == hashlib.sha256(native).digest()
  with zipfile.ZipFile('${projection.classPath}') as jar:
      assert jar.namelist() == ['image.ppm']
      assert jar.read('image.ppm') == native
  magic, dimensions, maximum, pixels = exported.split(b'\n', 3)
  assert magic == b'P6' and maximum == b'255'
  size = json.load(open('${../examples/minimal/size.json}'))['size']
  assert dimensions == f'{size} {size}'.encode()
  assert len(pixels) == size * size * 3
  PY
  touch $out
''
