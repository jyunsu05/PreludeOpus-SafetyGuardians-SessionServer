# Exit 0: our server is up. 2: port 8080 is taken. 1: nothing listening.
$health = "http://127.0.0.1:8080/health"
try {
    $response = Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 2
    if ($response.StatusCode -eq 200) {
        exit 0
    }
} catch {
}

try {
    $client = New-Object System.Net.Sockets.TcpClient
    $client.Connect("127.0.0.1", 8080)
    $client.Close()
    exit 2
} catch {
    exit 1
}
