- 👋 Hi, I’m @Tonystark423
- 👀 I’m interested in ...
- 🌱 I’m currently learning ...
- 💞️ I’m looking to collaborate on ...
- 📫 How to reach me ...

<!---
Tonystark423/Tonystark423 is a ✨ special ✨ repository because its `README.md` (this file) appears on your GitHub profile.
You can click the Preview link to take a look at your changes.
--->

## RSP vs SPY 30-Day Relative Performance

This Google Sheets formula calculates the **relative performance** of RSP (Invesco S&P 500 Equal Weight ETF) versus SPY (SPDR S&P 500 ETF Trust) over the past 30 days.

It shows whether equal-weight exposure (RSP) is outperforming or underperforming cap-weight exposure (SPY).

```
=((GOOGLEFINANCE("RSP", "price") / INDEX(GOOGLEFINANCE("RSP", "price", TODAY()-30), 2, 2))
 - (GOOGLEFINANCE("SPY", "price") / INDEX(GOOGLEFINANCE("SPY", "price", TODAY()-30), 2, 2)))
```

### How it works

| Part | Meaning |
|------|---------|
| `GOOGLEFINANCE("RSP", "price")` | Current RSP price |
| `INDEX(GOOGLEFINANCE("RSP", "price", TODAY()-30), 2, 2)` | RSP price 30 days ago |
| `RSP_now / RSP_30d_ago` | RSP 30-day return ratio (1.05 = +5%) |
| `SPY_now / SPY_30d_ago` | SPY 30-day return ratio |
| **Result** | RSP return minus SPY return |

- **Positive value**: RSP outperformed SPY (equal-weight beat cap-weight)
- **Negative value**: SPY outperformed RSP (cap-weight beat equal-weight)
- **~0**: Both ETFs had similar 30-day performance
