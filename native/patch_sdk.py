from pathlib import Path

root = Path(".")


def edit(name, old, new, count=1):
    p = root / name
    s = p.read_text()
    assert s.count(old) == count, (name, old, s.count(old))
    p.write_text(s.replace(old, new))


for field, var in [
    ("plug_in_path", "PLUGINS"),
    ("module_path", "MODULES"),
    ("interpreter_path", "INTERPRETERS"),
    ("environ_path", "ENVIRON"),
]:
    edit(
        "app/config/gimpcoreconfig.c",
        f"g_set_str (&core_config->{field},\n                 g_value_get_string (value));",
        f'g_set_str (&core_config->{field},\n                 g_getenv ("GIMP_PURIFIER_{var}") ? g_getenv ("GIMP_PURIFIER_{var}") : g_value_get_string (value));',
    )
edit(
    "app/config/gimprc.c",
    "gimp_rc_query (GimpRc      *rc,\n               const gchar *key)\n{",
    'gimp_rc_query (GimpRc      *rc,\n               const gchar *key)\n{\n  if (g_getenv ("GIMP_PURIFIER_SCRIPTS") && g_strcmp0 (key, "script-fu-path") == 0)\n    return g_strdup (g_getenv ("GIMP_PURIFIER_SCRIPTS"));',
)
for kind in ["writable", "system"]:
    old = f'path_str = gimp_config_build_{kind}_path ("extensions");'
    edit(
        "app/core/gimpextensionmanager.c",
        old,
        f'path_str = g_getenv ("GIMP_PURIFIER_EXTENSIONS") ? g_strdup (g_getenv ("GIMP_PURIFIER_EXTENSIONS")) : gimp_config_build_{kind}_path ("extensions");',
    )
edit(
    "app/core/gimpextensionmanager.c",
    "  gboolean success = FALSE;",
    '  gboolean success = FALSE;\n\n  if (g_getenv ("GIMP_PURIFIER_EXTENSIONS"))\n    {\n      g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_PERMISSION_DENIED,\n                           "GIMP extensions are locked; run gimp-purifier lock --update");\n      return FALSE;\n    }',
)
