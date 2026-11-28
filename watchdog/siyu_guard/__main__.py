import sys

from siyu_guard.guard import daemon, sentinel
from siyu_guard.storage import data_root

if sys.argv[1:] == ["--daemon"]:
    raise SystemExit(daemon(data_root()))
if sys.argv[1:] == ["--sentinel"]:
    raise SystemExit(sentinel(data_root()))

from siyu_guard.ui import main
main()
