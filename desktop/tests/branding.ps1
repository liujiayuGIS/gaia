param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$ExpectedIcon,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$expectedPath = (Resolve-Path $ExpectedIcon).Path
$results = @()
foreach ($entry in @(@{kind='application';path=$Executable}, @{kind='installer';path=$Installer})) {
    $file = Get-Item $entry.path
    if ($file.VersionInfo.ProductName -ne 'GAIA') { throw "Incorrect product name: $($file.VersionInfo.ProductName)" }
    $actualIcon = [System.Drawing.Icon]::ExtractAssociatedIcon($file.FullName)
    $actual = $actualIcon.ToBitmap()
    $expectedIcon = [System.Drawing.Icon]::new($expectedPath, [int]$actual.Width, [int]$actual.Height)
    $expected = $expectedIcon.ToBitmap()
    try {
        $sum = 0.0
        for ($y=0; $y -lt $actual.Height; $y++) {
            for ($x=0; $x -lt $actual.Width; $x++) {
                $a=$actual.GetPixel($x,$y); $b=$expected.GetPixel($x,$y)
                $sum += [Math]::Pow($a.R-$b.R,2)+[Math]::Pow($a.G-$b.G,2)+[Math]::Pow($a.B-$b.B,2)
            }
        }
        $rmse = [Math]::Sqrt($sum / ($actual.Width*$actual.Height*3))
        if ($rmse -gt 8) { throw "Packaged icon does not match GAIA: $($entry.kind), RMSE=$rmse" }
        $png = Join-Path (Resolve-Path $Output) ($entry.kind+'-icon-win-x64.png')
        $actual.Save($png,[System.Drawing.Imaging.ImageFormat]::Png)
        $results += @{kind=$entry.kind;productName=$file.VersionInfo.ProductName;iconRmse=$rmse;icon=$png}
    } finally { $actual.Dispose(); $expected.Dispose(); $actualIcon.Dispose(); $expectedIcon.Dispose() }
}
$start = [Environment]::GetFolderPath('Programs')
$shortcut = Get-ChildItem $start -Recurse -Filter 'GAIA.lnk' | Select-Object -First 1
if (-not $shortcut) { throw 'Installed GAIA Start Menu shortcut missing' }
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut.FullName)
if ($link.TargetPath -ne (Resolve-Path $Executable).Path) { throw 'GAIA shortcut points to the wrong program' }
@{passed=$true;name='GAIA';icons=$results;shortcut=$shortcut.FullName;target=$link.TargetPath;iconLocation=$link.IconLocation} |
    ConvertTo-Json -Depth 5 | Set-Content (Join-Path $Output 'branding-win-x64.json')
Write-Host 'Installed Windows app, installer, and shortcut use GAIA branding'
