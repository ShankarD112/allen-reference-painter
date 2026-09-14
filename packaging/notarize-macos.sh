#!/bin/bash
# Run after building with MACOS_SIGNING_IDENTITY on your configured signing Mac.
set -euo pipefail
: "${MACOS_NOTARY_PROFILE:?Set a notarytool keychain profile name}"
app="${1:-dist/AllenReferencePainter.app}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
codesign --verify --deep --strict --verbose=2 "$app"
# Reject ad-hoc/development identity; notarization is for Developer ID releases.
codesign -dv "$app" 2>&1 | /usr/bin/grep -q 'Authority=Developer ID Application:'
ditto -c -k --sequesterRsrc --keepParent "$app" "$work/submission.zip"
xcrun notarytool submit "$work/submission.zip" --keychain-profile "$MACOS_NOTARY_PROFILE" --wait --output-format json > "$work/result.json"
python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); print(r); assert r["status"]=="Accepted", "Notarization rejected"' "$work/result.json"
xcrun stapler staple "$app"
xcrun stapler validate "$app"
spctl --assess --type execute --verbose=2 "$app"
ditto -c -k --sequesterRsrc --keepParent "$app" "${app%.app}-notarized.zip"
cp "$work/result.json" "${app%.app}-notarization.json"
shasum -a 256 "${app%.app}-notarized.zip" > "${app%.app}-notarized.sha256"
