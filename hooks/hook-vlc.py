import os, sys

base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
lib_dir = os.path.join(base, "lib")
plugins_dir = os.path.join(base, "plugins")

if os.path.isdir(lib_dir):
    os.environ["LD_LIBRARY_PATH"] = lib_dir + ":" + os.environ.get("LD_LIBRARY_PATH", "")

if os.path.isdir(plugins_dir):
    os.environ["VLC_PLUGIN_PATH"] = plugins_dir
    os.environ["VLC_DATA_PATH"] = base  # optional, schadet aber nicht
