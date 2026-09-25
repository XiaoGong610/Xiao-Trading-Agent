#!/bin/bash
# SessionStart hook: prepares cloud sessions. No-op on local machines.
# Clones the private research repo into research/ and builds .venv (skills call .venv/bin/python3).

if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR" || exit 0

if [ -d research/.git ]; then
  git -C research pull -q || echo "cloud-setup: research pull failed"
else
  rm -rf research
  git clone -q https://github.com/XiaoGong610/Xiao-Trading-Research.git research \
    || echo "cloud-setup: research clone failed"
fi

if [ ! -x .venv/bin/python3 ]; then
  python3 -m venv .venv || echo "cloud-setup: venv creation failed"
fi
.venv/bin/python3 -m pip install -q --disable-pip-version-check -r requirements.txt || echo "cloud-setup: pip install failed"
exit 0
