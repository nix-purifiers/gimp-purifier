import json
import os
from pathlib import Path

from gi.repository import Gegl, Gimp

pdb = Gimp.get_pdb()
proc = pdb.lookup_procedure("plug-in-resynthesizer")
assert proc is not None
size = json.loads((Path(__file__).parent / "size.json").read_text())["size"]
image = Gimp.Image.new(size, size, Gimp.ImageBaseType.RGB)
layer = Gimp.Layer.new(
    image, "Target", size, size, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL
)
image.insert_layer(layer, None, 0)
corpus = Gimp.Image.new(size, size, Gimp.ImageBaseType.RGB)
source = Gimp.Layer.new(
    corpus, "Corpus", size, size, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL
)
corpus.insert_layer(source, None, 0)
Gimp.context_set_foreground(Gegl.Color.new("rgb(255,0,0)"))
source.fill(Gimp.FillType.FOREGROUND)
config = proc.create_config()
for key, value in {
    "drawable": layer,
    "corpus-drawable": source,
    "h-tile": False,
    "v-tile": False,
    "use-border": 0,
    "neighbours": 4,
    "trys": 16,
}.items():
    config.set_property(key, value)
result = proc.run(config)
assert result.index(0) == Gimp.PDBStatusType.SUCCESS, result.index(0)
buffer = layer.get_buffer()
pixels = buffer.get(
    Gegl.Rectangle.new(0, 0, size, size), 1.0, "R'G'B' u8", Gegl.AbyssPolicy.NONE
)
assert bytes(pixels) == bytes([255, 0, 0]) * (size * size), bytes(pixels)[:48]
p = Path(os.environ.get("GIMP_PURIFIER_OUTPUT", "output")) / "image.ppm"
p.parent.mkdir(exist_ok=True)
p.write_bytes(f'P6\n{size} {size}\n255\n'.encode() + bytes(pixels))
print(
    json.dumps({"procedure": proc.get_name(), "pixels": len(pixels), "output": str(p)})
)
