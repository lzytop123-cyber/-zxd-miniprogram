# Task 2 Report — Review Reward Carousel

## Files created

- `F:/zxd-pro/tools/compose_review_reward_carousel.py`
- `F:/zxd-pro/assets/marketing/home-carousel/home-carousel-05-review-reward-1500x1360.jpg`
- `F:/zxd-pro/.superpowers/sdd/task-2-report.md`

## Design values used

- Canvas: 1500 × 1360 px; centered deterministic cover crop; RGB output.
- Source adjustments: color 0.94, contrast 1.02, brightness 0.98.
- Readability field: forest green RGB `(11, 45, 32)`; alpha 174 through 48% of the width, smoothstep fade from 48% to 84%, transparent thereafter.
- Safe inset: 92 px for all left copy and the right-aligned wordmark; wordmark top inset 86 px.
- Tag: box `(92, 238, 304, 314)`, 76 px high, 38 px bold Microsoft YaHei, fill `#D8F3DC`, text `#205B43`.
- Headline: origin `(92, 350)`, 126 px bold Microsoft YaHei, 8 px line spacing, white `#FFFFFF`; rendered bbox `(92, 379, 470, 643)`.
- Subtitle: origin `(92, 689)`, 36 px Microsoft YaHei, warm white `#F7F1E7`; rendered width 620 px and right edge 712 px.
- CTA: box `(92, 781, 408, 885)`, 104 px high, white fill, 44 px bold Microsoft YaHei, text `#205B43`.
- Wordmark: right-aligned from x=1222 to x=1408 at y=86, 31 px bold Microsoft YaHei, text `#205B43`.
- Font selection: `C:/Windows/Fonts/msyh.ttc` and `C:/Windows/Fonts/msyhbd.ttc`, with `simhei.ttf` fallback.
- JPEG loop: quality 92, 88, 84, 80, 76; optimized, progressive, 4:2:0 subsampling. Quality 92 met the limit.

## Command

```powershell
python tools/compose_review_reward_carousel.py
```

## Composer output

```json
{
  "output_path": "F:\\zxd-pro\\assets\\marketing\\home-carousel\\home-carousel-05-review-reward-1500x1360.jpg",
  "width": 1500,
  "height": 1360,
  "format": "JPEG",
  "bytes": 207970,
  "sha256": "cba0cd98ed5483b5ceb49cc4d56c88f5819e565836524751cceca5e9a057a7c2"
}
```

## Independent validation

- Reopened successfully with Pillow and fully decoded.
- Size: `(1500, 1360)`.
- Mode: `RGB`.
- Format: `JPEG`.
- Non-empty: true.
- Under 1,950,000 bytes: true (207,970 bytes).
- Progressive: true.
- SHA-256: `cba0cd98ed5483b5ceb49cc4d56c88f5819e565836524751cceca5e9a057a7c2`.

## Visual QA

- Inspected the final JPEG at original detail.
- Verified `好评有礼`, the exact two-line headline `写好评` / `送日卡`, `美团 · 大众点评 · 抖音｜15字+3张照片`, `截图领日卡`, and `知行岛自习室`.
- Verified both middle dots, the full-width vertical bar, `15字+3张照片`, and the plus sign.
- No added text, letters, numbers, symbols, footnotes, terms, emoji, or iconography are present.
- No text overlap, clipping, or illegibly small copy was observed.
- Left copy ends at x=712 or earlier; it stays within the dark readability field and does not cross into the bright furniture area.
- Right-side desks, daylight, plants, natural wood, and ivory upholstery remain clear.

## Concerns

- None.
