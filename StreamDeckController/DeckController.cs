using OpenMacroBoard.SDK;
using SixLabors.ImageSharp;

namespace StarkDeck;

/// <summary>
/// Manages the 15-key (5×3) Stream Deck layout for the Stark Financial Holdings dashboard.
///
/// Layout:
///   Row 0  [0] Portfolio  [1] Crypto   [2] Equities  [3] Signings  [4] Refresh
///   Row 1  [5..12]  Top holdings by value (up to 8 slots)
///   Row 2  [13] Approve signing   [14] Last updated
/// </summary>
public sealed class DeckController : IDisposable
{
    // ── Key index constants ───────────────────────────────────────────────────
    private const int KeyPortfolioTotal = 0;
    private const int KeyCryptoTotal    = 1;
    private const int KeyEquityTotal    = 2;
    private const int KeySigningCount   = 3;
    private const int KeyRefresh        = 4;
    private const int KeyHoldingFirst   = 5;
    private const int KeyHoldingLast    = 12; // 8 holding slots
    private const int KeyApprove        = 13;
    private const int KeyUpdated        = 14;

    // ── Palette ───────────────────────────────────────────────────────────────
    private static readonly Color ColPortfolio  = Color.FromRgb(15,  52,  96);
    private static readonly Color ColCrypto     = Color.FromRgb(230, 126, 34);
    private static readonly Color ColEquity     = Color.FromRgb(39,  174, 96);
    private static readonly Color ColOk         = Color.FromRgb(39,  174, 96);
    private static readonly Color ColAlert      = Color.FromRgb(192, 57,  43);
    private static readonly Color ColRefresh    = Color.FromRgb(52,  73,  94);
    private static readonly Color ColCryptoHold = Color.FromRgb(120, 60,  10);
    private static readonly Color ColEquityHold = Color.FromRgb(20,  80,  40);
    private static readonly Color ColApprove    = Color.FromRgb(180, 140, 0);
    private static readonly Color ColMuted      = Color.FromRgb(30,  30,  50);
    private static readonly Color ColWhite      = Color.White;
    private static readonly Color ColGray       = Color.FromRgb(140, 140, 140);

    private readonly IStreamDeckBoard _deck;
    private readonly LedgerClient     _client;
    private readonly string?          _owner;

    private List<PortfolioItem> _portfolio = [];
    private List<SigningRecord>  _signings  = [];
    private volatile bool        _busy      = false;

    public DeckController(IStreamDeckBoard deck, LedgerClient client, string? owner = null)
    {
        _deck   = deck;
        _client = client;
        _owner  = owner;

        _deck.KeyStateChanged += OnKeyPressed;
        _deck.SetBrightness(80);
        RenderLoading();
    }

    /// <summary>Refresh once immediately then poll every 30 s until cancelled.</summary>
    public async Task RunAsync(CancellationToken ct)
    {
        await RefreshAsync();

        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(30));
        while (!ct.IsCancellationRequested)
        {
            try   { await timer.WaitForNextTickAsync(ct); }
            catch (OperationCanceledException) { break; }
            await RefreshAsync();
        }
    }

    // ── Data refresh ─────────────────────────────────────────────────────────

    private async Task RefreshAsync()
    {
        if (_busy) return;
        _busy = true;
        SetKey(KeyRefresh, KeyRenderer.RenderKey("REFRESH", "...", ColRefresh, ColWhite));

        try
        {
            var portfolioTask = _client.GetPortfolioSummaryAsync(_owner);
            var signingsTask  = _client.GetPendingSigningsAsync();
            await Task.WhenAll(portfolioTask, signingsTask);

            _portfolio = portfolioTask.Result;
            _signings  = signingsTask.Result;
            RenderAll();
        }
        catch (Exception ex)
        {
            var msg = ex.Message.Length > 7 ? ex.Message[..7] : ex.Message;
            SetKey(KeyRefresh, KeyRenderer.RenderKey("ERROR", msg, ColAlert, ColWhite));
        }
        finally
        {
            _busy = false;
        }
    }

    // ── Rendering ─────────────────────────────────────────────────────────────

    private void RenderAll()
    {
        var activeRows = _portfolio.Where(p => p.Status == "active").ToList();

        double cryptoTotal    = activeRows.Where(p => p.Category == "Cryptocurrency")           .Sum(p => p.TotalValueUsd);
        double equityTotal    = activeRows.Where(p => p.Category == "Securities & Commodities") .Sum(p => p.TotalValueUsd);
        double portfolioTotal = activeRows.Sum(p => p.TotalValueUsd);

        SetKey(KeyPortfolioTotal, KeyRenderer.RenderKey("PORTFOLIO", Fmt(portfolioTotal), ColPortfolio, ColWhite));
        SetKey(KeyCryptoTotal,    KeyRenderer.RenderKey("CRYPTO",    Fmt(cryptoTotal),    ColCrypto,    ColWhite));
        SetKey(KeyEquityTotal,    KeyRenderer.RenderKey("EQUITIES",  Fmt(equityTotal),    ColEquity,    ColWhite));

        int pending = _signings.Count;
        SetKey(KeySigningCount, KeyRenderer.RenderKey(
            "SIGN QUEUE",
            pending.ToString(),
            pending > 0 ? ColAlert : ColOk,
            ColWhite));

        SetKey(KeyRefresh, KeyRenderer.RenderKey("REFRESH", "\u27f3", ColRefresh, ColWhite));

        // Holdings slots (keys 5–12) — top 8 by value
        var topHoldings = activeRows
            .OrderByDescending(p => p.TotalValueUsd)
            .Take(KeyHoldingLast - KeyHoldingFirst + 1)
            .ToList();

        for (int key = KeyHoldingFirst; key <= KeyHoldingLast; key++)
        {
            int idx = key - KeyHoldingFirst;
            if (idx < topHoldings.Count)
            {
                var h    = topHoldings[idx];
                var bg   = h.Category == "Cryptocurrency" ? ColCryptoHold : ColEquityHold;
                var name = (h.Subcategory ?? h.Category[..Math.Min(6, h.Category.Length)]).ToUpperInvariant();
                SetKey(key, KeyRenderer.RenderKey(name, Fmt(h.TotalValueUsd), bg, ColWhite));
            }
            else
            {
                SetKey(key, KeyBitmap.Black);
            }
        }

        // Approve key
        SetKey(KeyApprove, pending > 0
            ? KeyRenderer.RenderKey("APPROVE", $"SIGN ({pending})", ColApprove, ColWhite)
            : KeyRenderer.RenderKey("APPROVE", "NONE",              ColMuted,   ColGray));

        SetKey(KeyUpdated, KeyRenderer.RenderKey("UPDATED", DateTime.Now.ToString("HH:mm"), ColMuted, ColGray));
    }

    private void RenderLoading()
    {
        int total = _deck.Keys.Count;
        for (int i = 0; i < total; i++)
            SetKey(i, KeyBitmap.Black);
        SetKey(KeyRefresh, KeyRenderer.RenderKey("LOADING", "...", ColRefresh, ColWhite));
    }

    // ── Key press handling ────────────────────────────────────────────────────

    private async void OnKeyPressed(object? sender, KeyEventArgs e)
    {
        if (!e.IsDown || _busy) return;

        switch (e.Key)
        {
            case KeyRefresh:
                await RefreshAsync();
                break;

            case KeyApprove when _signings.Count > 0:
                await ApproveFirstSigningAsync();
                break;
        }
    }

    private async Task ApproveFirstSigningAsync()
    {
        var first = _signings[0];
        SetKey(KeyApprove, KeyRenderer.RenderKey("SIGNING", "...", ColApprove, ColWhite));

        var signerName = Environment.GetEnvironmentVariable("LEDGER_USER") ?? "deck-ctrl";
        await _client.ApproveSigningAsync(first.Id, signerName);
        await RefreshAsync();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static string Fmt(double v) => v switch
    {
        >= 1_000_000 => $"${v / 1_000_000:F1}M",
        >= 1_000     => $"${v / 1_000:F1}K",
        _            => $"${v:F0}",
    };

    private void SetKey(int keyId, KeyBitmap bitmap) => _deck.SetKeyBitmap(keyId, bitmap);

    public void Dispose()
    {
        _deck.KeyStateChanged -= OnKeyPressed;
        _deck.Dispose();
    }
}
