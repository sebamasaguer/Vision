param(
  [int]$AckSeconds = 20,
  [int]$ResolveSeconds = 60,
  [int]$EscalationSeconds = 20,
  [int]$RepeatSeconds = 20,
  [int]$MaxLevel = 3
)
$ErrorActionPreference='Stop'
function Read-Env([string]$Name){$line=Get-Content '.env'|Where-Object{$_ -match "^$([regex]::Escape($Name))="}|Select-Object -First 1;if(-not $line){return $null};return ($line -split '=',2)[1]}
$email=Read-Env 'BOOTSTRAP_ADMIN_EMAIL';$password=Read-Env 'BOOTSTRAP_ADMIN_PASSWORD'
$login=Invoke-RestMethod 'http://localhost:8160/api/v1/auth/login' -Method Post -ContentType 'application/json' -Body (@{email=$email;password=$password}|ConvertTo-Json)
$h=@{Authorization="Bearer $($login.access_token)"}
$p=Invoke-RestMethod 'http://localhost:8160/api/v1/monitoring/policies' -Headers $h
$items=@($p.items | ForEach-Object {$_})
foreach($row in $items){
  $body=@{
    acknowledge_sla_seconds=$AckSeconds
    resolve_sla_seconds=$ResolveSeconds
    escalation_after_seconds=$EscalationSeconds
    escalation_repeat_seconds=$RepeatSeconds
    max_escalation_level=$MaxLevel
    notification_channels=@('IN_APP')
    active=$true
  }|ConvertTo-Json
  Invoke-RestMethod "http://localhost:8160/api/v1/monitoring/policies/$($row.id)" -Headers $h -Method Patch -ContentType 'application/json' -Body $body | Out-Null
  Write-Host "[OK] $($row.severity): ACK=${AckSeconds}s RESOLVE=${ResolveSeconds}s ESC=${EscalationSeconds}s REP=${RepeatSeconds}s MAX=$MaxLevel" -ForegroundColor Green
}
Write-Host 'Demo SLA configurado. Solo IN_APP esta activo: no se enviaran mensajes externos.' -ForegroundColor Cyan
Write-Host 'Abra http://localhost:5200 -> Monitoreo y observe vencimientos/escalamientos sobre nuevos Safety Events.' -ForegroundColor Cyan
