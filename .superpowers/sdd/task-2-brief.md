### Task 2: 确定性排版并导出 JPG

**Files:**
- Create: `tools/compose_review_reward_carousel.py`
- Create: `assets/marketing/home-carousel/home-carousel-05-review-reward-1500x1360.jpg`

**Context and inputs:**
- Read `F:/zxd-pro/.superpowers/sdd/task-1-report.md` first.
- Inspect `F:/zxd-pro/assets/marketing/home-carousel/sources/source-05-review-reward.png` at original detail.
- Inspect `F:/zxd-pro/tools/compose_home_carousels.py` for the established local Pillow/font/JPEG conventions, but do not modify it.

**Exact output contract:**
- 1500×1360 px, RGB JPEG, optimized/progressive, below 1,950,000 bytes.
- Destination: `F:/zxd-pro/assets/marketing/home-carousel/home-carousel-05-review-reward-1500x1360.jpg`.
- Do not overwrite or modify any existing carousel image.

**Required text, verbatim:**
- Small top-left tag: `好评有礼`
- Main headline, exactly two lines: `写好评` then `送日卡`
- Subtitle: `美团 · 大众点评 · 抖音｜15字+3张照片`
- CTA button: `截图领日卡`
- Add one restrained brand wordmark: `知行岛自习室`
- Do not add any other words, letters, numbers, symbols, footnotes, terms, emoji, or iconography.

**Composition and style:**
- Continue the approved A direction: left copy, right study-room scene.
- Add a broad deep forest-green semi-transparent readability field over the left side, fading gently toward the right; preserve the right-side desks, daylight, and plants.
- Keep critical content at least 80 px from the canvas edge.
- Tag near the top-left: pale mint pill `#D8F3DC`, dark green text `#205B43`.
- Headline: white, bold Microsoft YaHei, dominant, large, two clear lines; no outline-heavy or promotional-sale treatment.
- Subtitle: warm white, readable, single line if it fits within the left text region; use `·` and full-width `｜` exactly as provided.
- CTA: one white rounded pill with dark green text, min 94 px high; no arrow, icon, badge, or secondary button.
- Brand wordmark: small but clearly legible, placed unobtrusively near the upper-right safe area where contrast is adequate; use text only.
- Palette limited to forest green, mint green, warm white, ivory, and natural wood.
- Maintain quiet premium lifestyle tone; no drop-shadow excess, neon, glassmorphism, red accents, explosive stickers, or ecommerce-sale styling.

**Implementation requirements:**
- Use Python 3 + Pillow only; use `C:/Windows/Fonts/msyh.ttc` and `msyhbd.ttc`, with `simhei.ttf` fallback.
- Implement deterministic cover crop and reusable helpers for font selection, text width, and a left-to-right alpha gradient.
- Preserve Chinese source text as UTF-8 and use literal strings in the script.
- Save through a descending JPEG quality loop (for example 92, 88, 84, 80, 76) until below 1,950,000 bytes; fail if still too large.
- Print JSON with output path, width, height, format, bytes, and SHA-256.
- Run the script and validate by reopening the output with Pillow: exact size `(1500, 1360)`, mode `RGB`, format `JPEG`, non-empty, and under byte limit.

**Visual QA:**
- Inspect the final JPG at original detail after rendering.
- Verify every required string visually, including punctuation and `15字+3张照片`.
- Ensure no text overlaps, clipping, tiny illegible copy, or text crossing into the bright furniture area.

**Report:**
- Write `F:/zxd-pro/.superpowers/sdd/task-2-report.md` with files created, design values actually used, exact command, validation output, visual QA, and concerns.
- Return only `DONE`, files created, a one-line command/result summary, and concerns.
