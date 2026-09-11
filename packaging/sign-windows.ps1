# Requires Windows SDK signtool and a trusted signing certificate backed by
# your configured hardware/cloud key provider in the current user's cert store.
param([string]$Executable = "dist/AllenReferencePainter/AllenReferencePainter.exe")
$ErrorActionPreference = 'Stop'
if (!$env:WINDOWS_CERT_SHA1) { throw 'Set WINDOWS_CERT_SHA1 to the certificate thumbprint; never place private keys in the repository.' }
signtool sign /sha1 $env:WINDOWS_CERT_SHA1 /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Executable
if ($LASTEXITCODE -ne 0) { throw 'Signing failed' }
signtool verify /pa /all /v $Executable
if ($LASTEXITCODE -ne 0) { throw 'Signature verification failed' }
$signature = Get-AuthenticodeSignature $Executable
if ($signature.Status -ne 'Valid') { throw "Invalid Authenticode signature: $($signature.Status)" }
$signature | Format-List Status,SignerCertificate,TimeStamperCertificate
