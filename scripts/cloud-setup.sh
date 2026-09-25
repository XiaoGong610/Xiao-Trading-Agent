#!/bin/bash
# Prepares cloud sessions. No-op on local machines.
# - Links research/ to the attached Xiao-Trading-Research clone (sibling folder),
#   falling back to a direct clone if it isn't attached.
# - Builds .venv (skills call .venv/bin/python3).
# Runs as a SessionStart hook (single-repo sessions) and from the environment's
# setup script (multi-repo sessions, where repo hooks don't load).

if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
  exit 0
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 0

if [ ! -e research ]; then
  SIBLING="$(find "$ROOT/.." -maxdepth 1 -type d -iname 'xiao-trading-research' | head -1)"
  if [ -n "$SIBLING" ]; then
    ln -s "$(cd "$SIBLING" && pwd)" research
  else
    git clone -q https://github.com/XiaoGong610/Xiao-Trading-Research.git research \
      || echo "cloud-setup: research not found — attach Xiao-Trading-Research to the session"
  fi
fi

if [ ! -x .venv/bin/python3 ]; then
  python3 -m venv .venv || echo "cloud-setup: venv creation failed"
fi
.venv/bin/python3 -m pip install -q --disable-pip-version-check -r requirements.txt || echo "cloud-setup: pip install failed"
exit 0
