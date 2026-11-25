#!/bin/bash
# Full render: resumable (finished parts are skipped). Logs to build/render.log
cd "$(dirname "$0")/.."
python3 tools/build_video.py video && python3 tools/build_video.py audio && python3 tools/build_video.py mux && echo RENDER_COMPLETE
