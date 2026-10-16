#!/usr/bin/env bash
# P0/P4 macOS real-machine check (G0-06). Same steps as scripts/p0_windows_check.ps1.
# Usage (repo root):  bash scripts/p0_macos_check.sh            # interactive
#                     bash scripts/p0_macos_check.sh --skip-launch
# Writes build/p0-check/summary.md and build/p0-check/log.txt (no host or user names).
set -u
cd "$(dirname "$0")/.."
out=build/p0-check; mkdir -p "$out"; log="$out/log.txt"; : > "$log"
rows=(); failed=0

step() {  # step "name" cmd...
  local name=$1; shift
  echo "==> $name"; echo "==> $name : $*" >> "$log"
  local text; text=$("$@" 2>&1); local code=$?
  printf '%s\n' "$text" >> "$log"; printf '%s\n' "$text" | tail -n 5 | sed 's/^/    /'
  local last; last=$(printf '%s\n' "$text" | grep -v '^\s*$' | tail -n 1 | tr '|' '/')
  rows+=("| $name | $code | $last |"); [ "$code" -ne 0 ] && failed=1
  LAST_OUTPUT=$text
}

env_line="$(sw_vers -productName 2>/dev/null || uname -s) $(sw_vers -productVersion 2>/dev/null || uname -r) ($(uname -m)); CPU: $(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -p); RAM: $(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 )) GB"
echo "$env_line"
step "uv sync --locked" uv sync --locked --all-groups
step "fetch fonts (SHA-256)" uv run python scripts/fetch_fonts.py
step "ruff check" uv run ruff check .
step "ruff format --check" uv run ruff format --check .
step "pytest" uv run pytest
step "smoke build" uv run python packaging/smoke_build.py
versions=$(printf '%s\n' "$LAST_OUTPUT" | grep '^PEDITOR_SMOKE_OK' | head -n 1)

window="NOT RUN (--skip-launch)"
if [ "${1:-}" != "--skip-launch" ]; then
  uv run peditor & pid=$!
  read -r -p "Did a window titled 'PEditor 0.0.1' appear? (y/n) " a1; kill "$pid" 2>/dev/null
  build/smoke/dist/peditor/peditor & pid=$!
  read -r -p "Did the packaged app window appear? (y/n) " a2; kill "$pid" 2>/dev/null
  window="uv run peditor: $a1; packaged app: $a2"
  [ "$a1" = y ] && [ "$a2" = y ] || failed=1
fi

verdict=PASS; [ "$failed" -ne 0 ] && verdict=FAIL
{
  echo "## P0 macOS real-machine check (G0-06)"; echo
  echo "- date: $(date '+%Y-%m-%d %H:%M')"
  echo "- commit: $(git rev-parse --short HEAD)"
  echo "- environment: $env_line"
  echo "- uv: $(uv --version)"
  echo "- versions: $versions"
  echo "- window check: $window"
  echo "- result: **$verdict**"; echo
  echo "| step | exit code | last line |"; echo "| --- | --- | --- |"
  printf '%s\n' "${rows[@]}"
} > "$out/summary.md"
echo; cat "$out/summary.md"
echo; echo "Summary written to build/p0-check/summary.md; full log in build/p0-check/log.txt"
[ "$verdict" = PASS ]
