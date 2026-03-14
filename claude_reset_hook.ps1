<#
.SYNOPSIS
Hook script called upon Claude quota reset.
Pings Claude CLI in background and sends Telegram notification with the response.
#>

# --- SETTINGS ---
$EnvFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -match '=' -and $_ -notmatch '^#' } | ForEach-Object {
        $Name, $Value = $_.Split('=', 2).Trim()
        if (-not (Get-Item "Env:\$Name" -ErrorAction SilentlyContinue)) {
            Set-Item "Env:\$Name" $Value
        }
    }
}

$TelegramBotToken = $env:CLAUDE_TG_BOT_TOKEN
$TelegramChatID = $env:CLAUDE_TG_CHAT_ID

if (-not ($TelegramBotToken -and $TelegramChatID)) {
    Write-Warning "Telegram credentials missing. Check .env file."
    exit
}

# --- RANDOM PROMPTS ---
$Prompts = @("hi", "hello", "ping", "status report", "help", "ready for work?", "test connection", "verify status")
$RandomPrompt = $Prompts | Get-Random

# --- START CLAUDE CLI ---
$ClaudeResult = ""
$ClaudeStatus = "OK"

try {
    $ClaudeCmd = Get-Command "claude" -ErrorAction SilentlyContinue
    $ExePath = $null
    if (-not $ClaudeCmd) {
        $LocalBinPath = Join-Path $HOME ".local\bin\claude.exe"
        if (Test-Path $LocalBinPath) { $ExePath = $LocalBinPath }
    } else {
        $ExePath = if ($ClaudeCmd.Source) { $ClaudeCmd.Source } else { $ClaudeCmd.Name }
    }

    if ($ExePath) {
        Write-Host "Pinging Claude CLI (Timeout: 30s)..." -ForegroundColor Cyan
        
        $LogFile = Join-Path $PSScriptRoot "claude_temp_response.log"
        
        $Process = Start-Process -FilePath $ExePath -ArgumentList "`"$RandomPrompt`"" -NoNewWindow -PassThru -RedirectStandardOutput $LogFile
        $WaitResult = $Process | Wait-Process -Timeout 30 -ErrorAction SilentlyContinue
        
        if (-not $Process.HasExited) {
            $ClaudeResult = "Claude CLI timed out after 30 seconds."
            $ClaudeStatus = "Timeout"
            $Process | Stop-Process -Force
        } elseif (Test-Path $LogFile) {
            $Response = Get-Content $LogFile -Raw
            if ([string]::IsNullOrWhiteSpace($Response)) {
                $ClaudeResult = "Claude started but returned no output."
                $ClaudeStatus = "No Output"
            } else {
                $ClaudeResult = $Response.Trim() -replace "`r", ""
            }
        }
        
        # Cleanup temp log
        if (Test-Path $LogFile) { Remove-Item $LogFile -Force }
    } else {
        $ClaudeResult = "Claude CLI not found."
        $ClaudeStatus = "Not Found"
    }
} catch {
    $ClaudeResult = "Failed to start Claude CLI: $_"
    $ClaudeStatus = "Error"
}

# --- SEND TO TELEGRAM ---
$Rocket = [char]::ConvertFromUtf32(0x1F680)

# Limit Claude result length for Telegram to avoid message size limits
if ($ClaudeResult.Length -gt 2000) {
    $ClaudeResult = $ClaudeResult.Substring(0, 2000) + "... [Truncated]"
}

# Escape HTML for Telegram parse_mode = "HTML"
$SafePing = $RandomPrompt.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;")
$SafeResult = $ClaudeResult.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;")

$Robot = [char]::ConvertFromUtf32(0x1F916)
$Check = [char]::ConvertFromUtf32(0x2705)
$Warning = [char]::ConvertFromUtf32(0x26A0)

if ($ClaudeStatus -eq "OK") {
    $HtmlMessage = "$Rocket <b>Claude quotas have been reset!</b>`nTime to resume tasks.`n`n$Robot <b>Ping:</b> <code>$SafePing</code>`n`n$Check <b>Response:</b>`n<pre>$SafeResult</pre>"
} else {
    $HtmlMessage = "$Rocket <b>Claude quotas have been reset!</b>`nTime to resume tasks.`n`n$Robot <b>Ping:</b> <code>$SafePing</code>`n`n$Warning <b>Status: $ClaudeStatus</b>`n<pre>$SafeResult</pre>"
}

$TgUrl = "https://api.telegram.org/bot$TelegramBotToken/sendMessage"
$TgBody = @{
    chat_id = $TelegramChatID
    text    = $HtmlMessage
    parse_mode = "HTML"
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri $TgUrl -Method Post -ContentType "application/json; charset=utf-8" -Body $TgBody -ErrorAction Stop | Out-Null
    Write-Host "Success: Telegram notification sent with Claude's response!" -ForegroundColor Green
    Write-Host "`n--- Claude CLI Response ---`n$ClaudeResult`n---------------------------" -ForegroundColor Yellow
} catch {
    Write-Warning "Failed to send Telegram notification: $_"
}
