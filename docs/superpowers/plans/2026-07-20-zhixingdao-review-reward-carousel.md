# 知行岛好评送日卡轮播图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一张可直接上传至微信小程序首页轮播位的 1500×1360 JPG 营销海报。

**Architecture:** 使用生成式图像只制作无文字的现代自习室实景背景；中文标签、标题、副标题与 CTA 全部由 Pillow 在本地确定性绘制，避免乱码并精确控制尺寸、对比度和安全区。输出沿用现有 `assets/marketing/home-carousel/` 目录与知行岛墨绿、浅绿、暖白视觉体系。

**Tech Stack:** OpenAI built-in image generation、Python 3、Pillow、Microsoft YaHei 系统字体。

## Global Constraints

- 输出必须为 1500×1360 像素 JPG。
- 必须逐字出现：`好评有礼`、`写好评`、`送日卡`、`美团 · 大众点评 · 抖音｜15字+3张照片`、`截图领日卡`。
- 画面为安静明亮的现代自习室，自然光、木质桌椅、绿植，米白、浅木色与墨绿配色。
- 左侧为大面积深色渐变文字区；右侧保留清晰的自习室实景焦点。
- 不出现手机状态栏、微信 UI、爆炸贴、红包雨、假评价话术、过多图标、emoji 或小字条款。
- 不覆盖现有轮播资产；使用新文件名 `home-carousel-05-review-reward-1500x1360.jpg`。

---

### Task 1: 生成无文字自习室背景

**Files:**
- Create: `assets/marketing/home-carousel/sources/source-05-review-reward.png`

**Interfaces:**
- Consumes: 现有 `source-02-calm-space.png` 作为品牌构图参考。
- Produces: 可安全裁切至 1500×1360、左侧留有深色负空间的无文字背景图。

- [ ] **Step 1:** 用内置图像生成工具生成一张无文字、无标识、无 UI 的现代自习室背景。
- [ ] **Step 2:** 目视检查自然光、木质桌椅、绿植和左侧负空间；若出现文字或错误元素，仅针对该问题迭代一次。
- [ ] **Step 3:** 将选中的背景保存为 `assets/marketing/home-carousel/sources/source-05-review-reward.png`。

### Task 2: 确定性排版并导出 JPG

**Files:**
- Create: `tools/compose_review_reward_carousel.py`
- Create: `assets/marketing/home-carousel/home-carousel-05-review-reward-1500x1360.jpg`

**Interfaces:**
- Consumes: `source-05-review-reward.png`。
- Produces: 指定文件名、尺寸和完整中文文案的最终 JPG。

- [ ] **Step 1:** 编写 Pillow 合成脚本：cover 裁切、轻微降饱和、左侧墨绿渐变、圆角标签、两行主标题、副标题与单一 CTA。
- [ ] **Step 2:** 运行 `python tools/compose_review_reward_carousel.py`；预期输出最终 JPG 路径、尺寸和字节数。
- [ ] **Step 3:** 使用 Pillow 断言输出格式为 JPEG、尺寸为 `(1500, 1360)`，并确保文件非空且低于后台 2 MB 上传限制。

### Task 3: 视觉与文案验收

**Files:**
- Verify: `assets/marketing/home-carousel/home-carousel-05-review-reward-1500x1360.jpg`

**Interfaces:**
- Consumes: Task 2 最终 JPG。
- Produces: 可直接交付的轮播图。

- [ ] **Step 1:** 以原始分辨率查看最终图，逐字核对五处中文文案。
- [ ] **Step 2:** 检查白字与背景对比度、边缘安全区、单一 CTA、无 UI/无小字条款/无促销噪音。
- [ ] **Step 3:** 若发现问题，只修改对应的背景裁切或排版参数，重新导出并复检。
