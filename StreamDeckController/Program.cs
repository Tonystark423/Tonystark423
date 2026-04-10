using OpenMacroBoard.SDK;
using StreamDeckSharp;
using StarkDeck;

// ── Configuration from environment variables ─────────────────────────────────
// LEDGER_API_BASE  Base URL of the Flask ledger (default: http://localhost:5000)
// LEDGER_USER      HTTP Basic Auth username      (default: admin)
// LEDGER_PASS      HTTP Basic Auth password      (default: changeme)
// LEDGER_OWNER     beneficial_owner filter value (default: no filter)
//                  e.g. "All-Star Financial Holdings"
var apiBase  = Environment.GetEnvironmentVariable("LEDGER_API_BASE") ?? "http://localhost:5000";
var username = Environment.GetEnvironmentVariable("LEDGER_USER")     ?? "admin";
var password = Environment.GetEnvironmentVariable("LEDGER_PASS")     ?? "changeme";
var owner    = Environment.GetEnvironmentVariable("LEDGER_OWNER");   // optional

Console.WriteLine("Stark Financial Holdings — Stream Deck Controller");
Console.WriteLine($"  API  : {apiBase}");
Console.WriteLine($"  Owner: {owner ?? "(all holdings)"}");
Console.WriteLine();

using var cts = new CancellationTokenSource();
Console.CancelKeyPress += (_, e) => { e.Cancel = true; cts.Cancel(); };

IStreamDeckBoard deck;
try
{
    deck = StreamDeck.OpenDevice();
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Stream Deck not found: {ex.Message}");
    Console.Error.WriteLine("Make sure the device is plugged in and no other app is using it.");
    return 1;
}

using (deck)
using (var client = new LedgerClient(apiBase, username, password))
using (var ctrl   = new DeckController(deck, client, owner))
{
    Console.WriteLine($"Connected — {deck.Keys.Count} keys detected.");
    Console.WriteLine("Ctrl+C to exit.");
    await ctrl.RunAsync(cts.Token);
}

Console.WriteLine("Disconnected. Goodbye.");
return 0;
