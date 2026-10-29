#!/bin/sh
# Cron wrapper for the E750 critical health check.
#
# Runs the quiet health check, appends one timestamped block to
# /tmp/e750-health.log, keeps the last 500 lines, and sends failures to syslog
# (logread) with the tag e750-health. The exit code is the health exit code so
# a manual run still fails loudly.
set -u

LOG="${E750_HEALTH_LOG:-/tmp/e750-health.log}"
HEALTH="${E750_HEALTH_BIN:-/usr/bin/e750-health}"
MAX_LINES="${E750_HEALTH_MAX_LINES:-500}"

ts=$(date +%Y-%m-%dT%H:%M:%S%z 2>/dev/null || date)
out=$("$HEALTH" --quiet 2>&1)
rc=$?

{
	printf '%s ' "$ts"
	if [ "$rc" -eq 0 ]; then
		printf 'OK\n'
	else
		printf 'FAIL\n'
		printf '%s\n' "$out"
	fi
} >> "$LOG"

# Rotate without a second file: keep the tail in a temp file, then replace.
if [ "$(wc -l < "$LOG")" -gt "$MAX_LINES" ]; then
	tail -n "$MAX_LINES" "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

if [ "$rc" -ne 0 ]; then
	logger -t e750-health -p daemon.err "health check failed: $(printf '%s' "$out" | tr '\n' ';')"
fi

exit "$rc"
