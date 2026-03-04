import os, sys, tempfile

def _log(msg: str):
    try:
        p = os.path.join(tempfile.gettempdir(), "tmp_browser_hook.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
lib_dir = os.path.join(base, "lib")
plugins_dir = os.path.join(base, "plugins")

_log(f"base={base}")
_log(f"lib_dir exists={os.path.isdir(lib_dir)} path={lib_dir}")
_log(f"plugins_dir exists={os.path.isdir(plugins_dir)} path={plugins_dir}")

# Wichtig: erst env setzen, bevor irgendwo vlc importiert wird.
if os.path.isdir(lib_dir):
    os.environ["LD_LIBRARY_PATH"] = lib_dir + ":" + os.environ.get("LD_LIBRARY_PATH", "")
    _log(f"LD_LIBRARY_PATH={os.environ.get('LD_LIBRARY_PATH')}")

if os.path.isdir(plugins_dir):
    os.environ["VLC_PLUGIN_PATH"] = plugins_dir
    os.environ["VLC_DATA_PATH"] = base
    _log(f"VLC_PLUGIN_PATH={os.environ.get('VLC_PLUGIN_PATH')}")
    _log(f"VLC_DATA_PATH={os.environ.get('VLC_DATA_PATH')}")
