#!/bin/zsh
set -eu
cd "${0:A:h}/../.."
app="$PWD/.build/SpaceMouse C4D Trial.app"
mkdir -p "$app/Contents/MacOS"
clang -fobjc-arc -O2 -Wall -Wextra -Wno-unused-parameter \
  -I/Library/Frameworks/3DconnexionClient.framework/Headers \
  -F/Library/Frameworks -framework 3DconnexionClient \
  -framework AppKit -framework ApplicationServices \
  tools/c4d-navigation/main.m -o "$app/Contents/MacOS/SpaceMouseC4DTrial"
cp tools/c4d-navigation/Info.plist "$app/Contents/Info.plist"
codesign --force --sign - --identifier local.spacemouse.c4dtrial "$app"
"$app/Contents/MacOS/SpaceMouseC4DTrial" --self-test
printf 'Built: %s\n' "$app"
