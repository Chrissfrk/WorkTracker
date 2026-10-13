# Φτιάχνει το worktracker.zip για ανέβασμα στο PythonAnywhere
# Χρήση:  .\make_upload_zip.ps1            (χωρίς τη βάση — για ενημέρωση κώδικα)
#         .\make_upload_zip.ps1 -WithDb    (μαζί με το work_data.db — μόνο την πρώτη φορά!)
param([switch]$WithDb)

Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem

$root = $PSScriptRoot
$items = @("app.py", "core.py", "admin.py", "requirements.txt", "templates", "static")
if ($WithDb) { $items += "work_data.db" }

$out = Join-Path $root "worktracker.zip"
if (Test-Path $out) { Remove-Item $out }

# Χειροκίνητη δημιουργία ώστε τα paths να έχουν "/" (το Compress-Archive του PS 5.1 βάζει "\" που χαλάει το unzip στο Linux)
$zip = [System.IO.Compression.ZipFile]::Open($out, "Create")
try {
    foreach ($item in $items) {
        $full = Join-Path $root $item
        $files = if (Test-Path $full -PathType Container) { Get-ChildItem $full -Recurse -File } else { Get-Item $full }
        foreach ($f in $files) {
            $entry = $f.FullName.Substring($root.Length + 1).Replace("\", "/")
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.FullName, $entry) | Out-Null
        }
    }
} finally {
    $zip.Dispose()
}
Write-Host "OK -> $out"
