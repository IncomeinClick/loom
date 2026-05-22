---
name: run-ads
description: >
  Create and activate Facebook Page Like ad campaigns for Loom pages. Use this skill
  whenever the user wants to run ads, create ad campaigns, launch Page Like campaigns,
  set up Facebook advertising for a page, or anything related to ads management in Loom.
  Also use when the user mentions "run ads", "create campaign", "launch ads", "page like
  campaign", or asks about ad setup for Loom pages.
---

# Run Ads — Facebook Page Like Campaigns

Create and activate Facebook Page Like campaigns for Loom pages.

## Campaign Structure

1 campaign → 1 adset → 4 ads (1 ad per reel, using 4 latest reels from the page)

## Campaign Naming

`{Page Name} - Page Like`

## Fixed Config

- **Objective:** OUTCOME_ENGAGEMENT → PAGE_LIKES
- **Budget:** 100 THB/day (CBO at campaign level)
- **Gender:** Woman (2)
- **Age:** min 25, max 65 (FB Advantage+ audience requires age_min ≤ 25)
- **Advantage audience:** On (age/gender as audience suggestion, not control)
- **Videos:** 4 latest reels from the page
- **Caption:** Auto-fetched from video description
- **Start:** Active immediately (all levels: campaign + adset + ads)

## Language → Country + Locale Mapping

| Page Language | Target Countries | Locale |
|---|---|---|
| Thai | TH | _(none)_ |
| Philippines (Tagalog) | PH | _(none)_ |
| English | TH, LA, SG, MY, PH, VN, BN, ID | English US (6) + English UK (24) |
| Indonesia | ID | _(none)_ |
| Vietnam | VN | _(none)_ |

**Rule:** Only specify locale for English pages (multi-country). Single-country campaigns do NOT set locale — the country alone is enough.

**How to determine language:** The page name tells us the target. Thai name = Thailand, Phil name = Philippines, etc. English pages target all 8 SEA countries.

## Steps

1. Get the page from Loom API
2. Determine language from page data → map to countries + locale
3. Fetch 4 latest videos from the page
4. Create campaign via `POST /api/ads/campaigns`:
   ```json
   {
     "name": "{Page Name} - Page Like",
     "page_id": "{page_id}",
     "daily_budget": 100,
     "targeting": {
       "countries": [...],
       "age_min": 25,
       "age_max": 65,
       "genders": [2],
       "locales": [6, 24]
     },
     "video_ids": [4 latest video IDs],
     "start_active": true
   }
   ```
5. Campaign is created active at all levels (campaign + adset + ads)
6. Dashboard `ads_running` stage is auto-toggled

## SG Regulation

When SG is in target countries (English pages), `SINGAPORE_UNIVERSAL` regional regulated category is automatically added by the backend.

## Verification

After creation, verify:
- Campaign shows as ACTIVE in Loom Ads Manager
- All 4 ads are IN_PROCESS or ACTIVE on Facebook
- Dashboard shows ads_running stage for the page
