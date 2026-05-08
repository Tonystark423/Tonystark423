using OpenMacroBoard.SDK;
using SixLabors.Fonts;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.Drawing.Processing;
using SixLabors.ImageSharp.PixelFormats;
using SixLabors.ImageSharp.Processing;

namespace StarkDeck;

/// <summary>
/// Renders labelled, colour-coded key bitmaps using ImageSharp.Drawing 1.x
/// (compatible with the ImageSharp 2.1.x build used by StreamDeckSharp 6.1.0).
/// </summary>
public static class KeyRenderer
{
    private const int KeySize = 72; // standard Stream Deck key resolution

    private static readonly Font LabelFont;
    private static readonly Font ValueFont;

    static KeyRenderer()
    {
        // Prefer "Arial"; fall back to first available system font.
        FontFamily family;
        try
        {
            family = SystemFonts.Get("Arial");
        }
        catch
        {
            family = SystemFonts.Families.First();
        }

        LabelFont = family.CreateFont(9,  FontStyle.Regular);
        ValueFont = family.CreateFont(13, FontStyle.Bold);
    }

    /// <summary>
    /// Creates a key bitmap with a small label on top and a bold value centred below.
    /// </summary>
    public static KeyBitmap RenderKey(
        string label,
        string value,
        Color  background,
        Color  foreground)
    {
        using var img = new Image<Rgba32>(KeySize, KeySize);

        img.Mutate(ctx =>
        {
            ctx.Fill(background);

            if (!string.IsNullOrWhiteSpace(label))
            {
                var labelOpts = new TextOptions(LabelFont)
                {
                    HorizontalAlignment = HorizontalAlignment.Center,
                    Origin              = new PointF(KeySize / 2f, 8f),
                };
                ctx.DrawText(labelOpts, Truncate(label, 8), foreground);
            }

            if (!string.IsNullOrWhiteSpace(value))
            {
                var valueOpts = new TextOptions(ValueFont)
                {
                    HorizontalAlignment = HorizontalAlignment.Center,
                    VerticalAlignment   = VerticalAlignment.Center,
                    Origin              = new PointF(KeySize / 2f, KeySize / 2f + 10f),
                };
                ctx.DrawText(valueOpts, Truncate(value, 9), foreground);
            }
        });

        return KeyBitmap.Create.FromImageSharpImage(img);
    }

    private static string Truncate(string s, int maxLen) =>
        s.Length <= maxLen ? s : s[..maxLen];
}
