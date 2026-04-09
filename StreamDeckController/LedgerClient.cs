using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace StarkDeck;

public record PortfolioItem(
    [property: JsonPropertyName("category")]        string  Category,
    [property: JsonPropertyName("subcategory")]     string? Subcategory,
    [property: JsonPropertyName("status")]          string  Status,
    [property: JsonPropertyName("beneficial_owner")]string? BeneficialOwner,
    [property: JsonPropertyName("asset_count")]     int     AssetCount,
    [property: JsonPropertyName("total_value_usd")] double  TotalValueUsd,
    [property: JsonPropertyName("unit")]            string? Unit
);

public record SigningRecord(
    [property: JsonPropertyName("id")]             int     Id,
    [property: JsonPropertyName("batch_ref")]      string  BatchRef,
    [property: JsonPropertyName("asset_category")] string? AssetCategory,
    [property: JsonPropertyName("signer")]         string? Signer,
    [property: JsonPropertyName("num_items")]      int     NumItems,
    [property: JsonPropertyName("total_value")]    string? TotalValue,
    [property: JsonPropertyName("currency")]       string? Currency,
    [property: JsonPropertyName("status")]         string  Status,
    [property: JsonPropertyName("notes")]          string? Notes
);

/// <summary>
/// Thin async HTTP client for the Stark Financial Holdings Flask ledger API.
/// Handles HTTP Basic Auth and JSON deserialization.
/// </summary>
public sealed class LedgerClient : IDisposable
{
    private readonly HttpClient _http;
    private static readonly JsonSerializerOptions JsonOpts = new() { PropertyNameCaseInsensitive = true };

    public LedgerClient(string baseUrl, string username, string password)
    {
        _http = new HttpClient { BaseAddress = new Uri(baseUrl.TrimEnd('/') + "/") };
        var token = Convert.ToBase64String(Encoding.ASCII.GetBytes($"{username}:{password}"));
        _http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Basic", token);
    }

    /// <summary>Returns the portfolio summary view, optionally filtered by beneficial owner.</summary>
    public async Task<List<PortfolioItem>> GetPortfolioSummaryAsync(string? owner = null)
    {
        var url = "api/portfolio/summary";
        if (!string.IsNullOrEmpty(owner))
            url += $"?owner={Uri.EscapeDataString(owner)}";

        var json = await _http.GetStringAsync(url);
        return JsonSerializer.Deserialize<List<PortfolioItem>>(json, JsonOpts) ?? [];
    }

    /// <summary>Returns batch signing records with status = pending (latest 10).</summary>
    public async Task<List<SigningRecord>> GetPendingSigningsAsync()
    {
        var json = await _http.GetStringAsync("api/signings?status=pending&limit=10");
        return JsonSerializer.Deserialize<List<SigningRecord>>(json, JsonOpts) ?? [];
    }

    /// <summary>Advances a signing record to status = signed.</summary>
    public async Task<SigningRecord?> ApproveSigningAsync(int id, string signer)
    {
        var body = JsonSerializer.Serialize(new
        {
            status    = "signed",
            signer,
            signed_at = DateTime.UtcNow.ToString("o"),
        });
        var response = await _http.PutAsync(
            $"api/signings/{id}",
            new StringContent(body, Encoding.UTF8, "application/json"));

        if (!response.IsSuccessStatusCode)
            return null;

        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<SigningRecord>(json, JsonOpts);
    }

    public void Dispose() => _http.Dispose();
}
