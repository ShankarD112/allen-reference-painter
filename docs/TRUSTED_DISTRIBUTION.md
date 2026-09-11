# Trusted desktop distribution

Signing establishes publisher identity and protects artifact integrity. It is not
a guarantee of safety, scientific accuracy, or absence of OS warnings. Our CI tests
functionality; release review also needs actual downloaded-app checks on clean machines.

## macOS

1. Enroll in the Apple Developer Program and create a **Developer ID Application**
   identity. Install its certificate/private key in your signing Mac's keychain.
   Keep the key out of the repository. Use a protected signing environment in CI.
2. Set `MACOS_SIGNING_IDENTITY` to that keychain identity's exact name and build on
   each target Mac architecture:

   ```bash
   python -m pip install -e '.[dev]'
   python -m PyInstaller --clean --noconfirm packaging/AllenReferencePainter.spec
   ```

   PyInstaller signs nested binaries and the app. The entitlement permits the
   atlas dependency's Wasmtime JIT under the hardened runtime. Validate the signed
   app's real-atlas workflow again; unsigned CI does not prove this path.
3. Store notarization credentials locally using `xcrun notarytool store-credentials`
   following Apple's prompts (Apple ID/team/app-specific password or supported
   App Store Connect API key). Set `MACOS_NOTARY_PROFILE` to that profile's name.
4. Run `bash packaging/notarize-macos.sh`. It rejects non-Developer-ID identities,
   verifies signatures, submits to Apple, requires Accepted status, staples the
   ticket, checks Gatekeeper and creates a new notarized ZIP plus result and hash.
   Do not distribute the pre-stapled ZIP or mutate the signed bundle afterward.
5. Download the final ZIP through a browser on a clean Mac and verify launch and
   real-atlas loading. Publish separate arm64 and x86_64 assets with their minimum
   tested macOS version. Current development jobs use macOS 15.

Unsigned/ad-hoc CI apps have no verified publisher identity. They may be rejected
by Gatekeeper. Do not disable Gatekeeper or strip quarantine to claim trusted distribution.

## Windows

Acquire a publicly trusted code-signing identity from a CA or a supported managed
signing service. Modern providers generally protect private keys with hardware or
cloud key storage. Self-signed certificates do not establish public trust.

The helper `packaging/sign-windows.ps1` supports an identity exposed through the
current user's Windows certificate store by a hardware/cloud provider. Install the
Windows SDK (signtool), configure your provider, set `WINDOWS_CERT_SHA1` to the
certificate thumbprint, and run the helper. It signs the executable with SHA256,
requests a timestamp, and requires successful Authenticode verification. For a
service that uses its own signing API, use that provider's supported integration
instead; this script is not a generic cloud-signing client.

Repeat the executable smoke tests after signing. Archive the signed folder and
compute the ZIP hash **after** signing. Publish the publisher name, version,
commit, resolved dependencies, SHA256 and test evidence with the release.
SmartScreen considers file and certificate reputation; a new correctly signed
application can still show warnings. Report false positives through Microsoft's
submission process. Do not instruct recipients to disable protection.

## Credentials and current status

No Developer ID certificate, notarization profile or trusted Windows signing
identity has been provided. Signing scripts are prepared, but CI artifacts remain
unsigned/ad-hoc development builds. Configure credentials using your local
keychain/certificate store or protected repository environments; never paste
private keys, passwords or certificate exports into issues or chat.

## Official references

- [Apple Developer ID](https://developer.apple.com/developer-id/)
- [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
- [PyInstaller macOS signing](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing)
- [Microsoft SmartScreen](https://learn.microsoft.com/en-us/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/)
- [SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
