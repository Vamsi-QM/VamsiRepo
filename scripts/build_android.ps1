$ErrorActionPreference = "Stop"
$Root = "D:\VamsiCompanion"
Set-Location $Root

$AndroidStudioJava = "C:\Program Files\Android\Android Studio\jbr"
if (Test-Path (Join-Path $AndroidStudioJava "bin\java.exe")) {
    $env:JAVA_HOME = $AndroidStudioJava
    $env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
}

$CachedGradle = "C:\Users\Ravipati-Vamsidhar\.gradle\wrapper\dists\gradle-9.4.1-bin\arn2x92ynaizyzdaamcbpbhtj\gradle-9.4.1\bin\gradle.bat"
if (Test-Path $CachedGradle) {
    & $CachedGradle --no-daemon :android-app:assembleDebug
    exit $LASTEXITCODE
}

if (Get-Command gradle -ErrorAction SilentlyContinue) {
    gradle --no-daemon :android-app:assembleDebug
    exit $LASTEXITCODE
}

Write-Host "Gradle was not found. Open this folder in Android Studio and build the android-app module."
exit 1
