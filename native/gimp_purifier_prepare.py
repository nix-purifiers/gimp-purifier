"""Keep writable GIMP preferences while pinning executable search paths."""

from pathlib import Path


def prepare(state, environment, sdk, cache):
    state = Path(state).resolve()
    environment = Path(environment).resolve()
    sdk = Path(sdk).resolve()
    profile = state / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    # Native code search remains guarded even when the GUI saves different preferences.
    return {
        "GIMP3_DIRECTORY": str(profile),
        "GIMP3_PLUGINDIR": str(sdk / "lib/gimp/3.0"),
        "GIMP3_DATADIR": str(sdk / "share/gimp/3.0"),
        "GIMP_PURIFIER_PLUGINS": str(environment / "plug-ins")
        + ":"
        + str(sdk / "lib/gimp/3.0/plug-ins"),
        "GIMP_PURIFIER_MODULES": str(sdk / "lib/gimp/3.0/modules"),
        "GIMP_PURIFIER_INTERPRETERS": str(sdk / "lib/gimp/3.0/interpreters"),
        "GIMP_PURIFIER_ENVIRON": str(sdk / "lib/gimp/3.0/environ"),
        "GIMP_PURIFIER_SCRIPTS": str(sdk / "share/gimp/3.0/scripts"),
        "GIMP_PURIFIER_EXTENSIONS": str(cache),
        "GIMP_TESTING_PLUGINDIRS": str(environment / "plug-ins")
        + ":"
        + str(sdk / "lib/gimp/3.0/plug-ins"),
        "GIMP_TESTING_INTERPRETER_DIRS": str(sdk / "lib/gimp/3.0/interpreters"),
        "GIMP_TESTING_ENVIRON_DIRS": str(sdk / "lib/gimp/3.0/environ"),
        "PYTHONPATH": "",
        "PYTHONHOME": "",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPYCACHEPREFIX": str(cache),
    }
