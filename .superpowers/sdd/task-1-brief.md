### Task 1: 生成无文字自习室背景

**Files:**
- Create: `assets/marketing/home-carousel/sources/source-05-review-reward.png`

**Interfaces:**
- Consumes: 现有 `assets/marketing/home-carousel/sources/source-02-calm-space.png` 作为品牌构图参考。
- Produces: 可安全裁切至 1500×1360、左侧留有深色负空间的无文字背景图。

**Exact requirements:**
- Modern quiet study room, photorealistic lifestyle photography.
- Natural daylight, light wood desks/chairs, restrained greenery, warm ivory and forest-green palette.
- Main scene detail on the right; broad dark-green negative space on the left for later typography.
- Near-square 1500:1360 composition, visually full, suitable for a WeChat Mini Program homepage carousel.
- No text, letters, numbers, logos, signs, UI, phones, status bars, icons, people, watermarks, sale stickers, red envelopes, or emojis.

**Steps:**
- Use the built-in image generation tool. Treat the existing PNG only as a style/composition reference, not as an edit target.
- Inspect the result for natural light, wood furniture, plants, a calm premium mood, and usable left-side negative space.
- Save the selected result to the exact workspace path above. Do not overwrite any existing asset other than that exact new destination if you created it during this task.
- Validate that the saved file opens successfully and report its pixel dimensions.

**Report:**
- Write a detailed report to `F:/zxd-pro/.superpowers/sdd/task-1-report.md` with the final prompt, built-in generation mode, output path, dimensions, validation notes, and any concerns.
- Return only `DONE`, the saved path, dimensions, and a one-line validation summary.
