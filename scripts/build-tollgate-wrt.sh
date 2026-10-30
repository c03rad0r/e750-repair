#!/bin/sh
# Build a tollgate-wrt binary for the E750 from the stale-mint fix.
#
# The E750 runs TollGate 0.6.0, which pins gonuts v0.13.0. The wallet fails to
# start when a stored keyset belongs to a mint that answers EOF (isNetworkError
# did not classify EOF). This script builds v0.6.0 against gonuts v0.13.0 plus
# patches/gonuts-isnetworkerror-eof.patch (the backport of
# OpenTollGate/gonuts-tollgate#45), so the device binary matches the deployed
# code line.
#
#   scripts/build-tollgate-wrt.sh [outfile]
#
# Default outfile: tollgate-wrt-mips. Override GOARCH/GOMIPS for the lab:
#   GOARCH=amd64 GOMIPS= scripts/build-tollgate-wrt.sh tollgate-wrt-amd64
#
# Requires: git, go >= 1.24.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
OUT=${1:-"$ROOT/tollgate-wrt-mips"}
WORK=${WORK:-"$ROOT/state/build/tollgate-wrt"}
MODULE_REPO=${MODULE_REPO:-https://github.com/OpenTollGate/tollgate-module-basic-go}
MODULE_TAG=${MODULE_TAG:-v0.6.0}
GONUTS_REPO=${GONUTS_REPO:-https://github.com/OpenTollGate/gonuts-tollgate}
GONUTS_TAG=${GONUTS_TAG:-v0.13.0}
PATCH=${PATCH:-"$ROOT/patches/gonuts-isnetworkerror-eof.patch"}
GOOS=${GOOS:-linux}
GOARCH=${GOARCH:-mips}
GOMIPS=${GOMIPS-softfloat}

mkdir -p "$WORK"
if [ ! -d "$WORK/module/.git" ]; then
	git clone --quiet "$MODULE_REPO" "$WORK/module"
fi
git -C "$WORK/module" fetch --quiet --tags origin
git -C "$WORK/module" checkout --quiet "$MODULE_TAG"

if [ ! -d "$WORK/gonuts/.git" ]; then
	git clone --quiet "$GONUTS_REPO" "$WORK/gonuts"
fi
git -C "$WORK/gonuts" fetch --quiet --tags origin
git -C "$WORK/gonuts" checkout --quiet "$GONUTS_TAG"
git -C "$WORK/gonuts" checkout --quiet -- .
git -C "$WORK/gonuts" apply "$PATCH"

cd "$WORK/module/src"
go mod edit -replace="github.com/OpenTollGate/gonuts-tollgate=$WORK/gonuts"
go mod tidy >/dev/null

mkdir -p "$(dirname "$OUT")"
env GOOS="$GOOS" GOARCH="$GOARCH" GOMIPS="$GOMIPS" CGO_ENABLED=0 \
	go build -trimpath -ldflags '-s -w' -o "$OUT" .

echo "built $OUT"
sha256sum "$OUT"
