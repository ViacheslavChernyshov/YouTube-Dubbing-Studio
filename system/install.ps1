$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

try {

function Download-FileFast {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Url,
        [Parameter(Mandatory=$true)]
        [string]$OutFile
    )
    
    $fullPath = Join-Path -Path (Get-Location).Path -ChildPath $OutFile
    $request = [System.Net.WebRequest]::Create($Url)
    if ($request -is [System.Net.HttpWebRequest]) {
        $request.UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    $response = $request.GetResponse()
    $totalBytes = $response.ContentLength
    
    $stream = $response.GetResponseStream()
    $fileStream = [System.IO.File]::Create($fullPath)
    
    $buffer = New-Object byte[] 65536
    $totalRead = 0
    $read = 0
    
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $lastUpdate = 0
    
    try {
        do {
            $read = $stream.Read($buffer, 0, $buffer.Length)
            if ($read -gt 0) {
                $fileStream.Write($buffer, 0, $read)
                $totalRead += $read
                
                if ($timer.ElapsedMilliseconds - $lastUpdate -gt 300) {
                    $lastUpdate = $timer.ElapsedMilliseconds
                    if ($totalBytes -gt 0) {
                        $percent = [math]::Floor(($totalRead / $totalBytes) * 100)
                        $readMB = [math]::Round($totalRead / 1MB, 2)
                        $totalMB = [math]::Round($totalBytes / 1MB, 2)
                        Write-Host "`r    Downloading... $readMB MB / $totalMB MB ($percent%)" -NoNewline
                    } else {
                        $readMB = [math]::Round($totalRead / 1MB, 2)
                        Write-Host "`r    Downloading... $readMB MB" -NoNewline
                    }
                }
            }
        } while ($read -gt 0)
        Write-Host "`r    Downloading completed!                                   "
    } finally {
        $fileStream.Close()
        if ($null -ne $stream) { $stream.Close() }
        if ($null -ne $response) { $response.Close() }
    }
}

# 1. СКАЧИВАНИЕ PYTHON
$pyVersion = "3.11.9"
$pyUrl = "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-embed-amd64.zip"
$pyZip = "python.zip"
$pyDir = "python"

if (-not (Test-Path "$pyDir\python.exe")) {
    Write-Host "[1/5] Downloading Portable Python $pyVersion..."
    Download-FileFast -Url $pyUrl -OutFile $pyZip
    Write-Host "[1/5] Extracting Python..."
    Expand-Archive -Path $pyZip -DestinationPath $pyDir -Force
    Remove-Item $pyZip
    
    # Разблокируем pip
    $pthFile = Get-ChildItem -Path $pyDir -Filter "python*._pth" | Select-Object -First 1
    if ($pthFile) {
        $pthContent = Get-Content $pthFile.FullName
        $pthContent = $pthContent -replace '^#import site', 'import site'
        Set-Content -Path $pthFile.FullName -Value $pthContent
    }
} else {
    Write-Host "[1/5] Python is already installed."
}

# 2. УСТАНОВКА PIP
$pythonExe = "$pyDir\python.exe"
if (-not (Test-Path "$pyDir\Scripts\pip.exe")) {
    Write-Host "[2/5] Installing pip..."
    Download-FileFast -Url "https://bootstrap.pypa.io/get-pip.py" -OutFile "$pyDir\get-pip.py"
    & $pythonExe "$pyDir\get-pip.py" --no-warn-script-location
    Remove-Item "$pyDir\get-pip.py"
} else {
    Write-Host "[2/5] Pip is already installed."
}

# 3. УСТАНОВКА FFMPEG
$toolsDir = "..\data\tools"
$ffmpegDir = "$toolsDir\ffmpeg"
$ffmpegZip = "$toolsDir\ffmpeg.zip"
$ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

if (-not (Test-Path "$ffmpegDir\bin\ffmpeg.exe")) {
    Write-Host "[3/5] Downloading FFmpeg..."
    if (-not (Test-Path $toolsDir)) { New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null }
    Download-FileFast -Url $ffmpegUrl -OutFile $ffmpegZip
    Write-Host "[3/5] Extracting FFmpeg..."
    Expand-Archive -Path $ffmpegZip -DestinationPath $toolsDir -Force
    $extractedFolder = Get-ChildItem -Path $toolsDir -Filter "ffmpeg-master-latest-win64-gpl" | Select-Object -First 1
    if ($extractedFolder) {
        if (Test-Path $ffmpegDir) { Remove-Item -Path $ffmpegDir -Recurse -Force }
        Rename-Item -Path $extractedFolder.FullName -NewName "ffmpeg"
    }
    Remove-Item $ffmpegZip
} else {
    Write-Host "[3/5] FFmpeg is already installed."
}

# 4. УСТАНОВКА PYTORCH
Write-Host "[4/5] Installing Machine Learning algorithms (PyTorch)..."
& $pythonExe -m pip install --no-warn-script-location torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 5. УСТАНОВКА ОСТАЛЬНЫХ БИБЛИОТЕК
Write-Host "[5/5] Installing required libraries from requirements.txt..."
& $pythonExe -m pip install --no-warn-script-location -r requirements.txt

New-Item -Path "$pyDir\.installed_ok" -ItemType File -Force | Out-Null
Write-Host "All components have been downloaded and configured!"
} catch {
    Write-Host "`n[ERROR] An error occurred during installation:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Yellow
    Write-Host "Please send a screenshot of this error." -ForegroundColor Cyan
    Read-Host "Press Enter to exit..."
    exit 1
}
