---
name: page-scheduler
description: >
  Schedule optimizer for Loom workflow posting times. Use this skill whenever
  creating a new page, translating a page to another language, activating
  workflows, or when the user asks about scheduling, posting times, or wants
  to set up or review cron schedules for any page's workflows. Also triggers
  when the user says "schedule", "posting time", "when to post", "cron",
  "activate workflow", or asks about best times to post on Facebook. Always
  use this skill before setting any workflow schedule — never guess times.
---

# Page Scheduler

Determines optimal Facebook posting times for Loom workflows, ensuring content is evenly distributed throughout the day and no two workflows across the entire system fire at the same minute.

## Core Principle

Think in terms of **total daily posts per page**, not individual workflows.

A page with 3 workflows, each posting 3 times/day = **9 posts/day**. Those 9 posts should scatter evenly across the day's peak hours — roughly equally spaced, interleaving all workflows. The audience should see a steady stream of content throughout the day, never 3 posts in 30 minutes followed by hours of silence.

## How It Works

1. Determine the page's **market** from its language
2. Look up **peak posting hours** for that market
3. Count **total daily posts** for the page (workflows x slots per workflow)
4. Calculate the **ideal interval** = peak hours / total posts
5. Distribute posts evenly, **round-robin across workflows** so the same workflow doesn't post back-to-back
6. Check against **all existing schedules** in Loom to avoid minute collisions
7. Present the recommendation to the user for approval

## Market Peak Hours

All times are **Asia/Bangkok timezone** (Loom's scheduler timezone).

### Thailand (Thai pages)
- **Peak range**: 6:00 - 21:00 (15 hours)
- **Best hours**: 7-9 AM, 12-1 PM, 6-9 PM
- Posts should favor best hours but still scatter across the full peak range

### Philippines (Tagalog/Filipino pages)
Times in Bangkok timezone (PH is UTC+8, Bangkok is UTC+7).
- **Peak range**: 5:00 - 21:00 (16 hours)
- **Best hours**: 5-8 AM, 11-13, 17-21 (Bangkok time)

### Global / English pages
Wider windows to cover mixed audiences.
- **Peak range**: 5:00 - 22:00 (17 hours)
- **Best hours**: 6-9 AM, 10-14, 18-22 (Bangkok time)

## Scheduling Algorithm

### Step 1: Calculate interval for a page
```
total_posts = number_of_workflows × 3  (each workflow posts 3x/day)
peak_minutes = peak_range in minutes   (e.g., 15 hours = 900 minutes)
interval = peak_minutes / total_posts  (e.g., 900 / 9 = 100 minutes)
```

### Step 2: Generate evenly-spaced time slots
Starting from the beginning of peak range, place posts at each interval:
```
slot[0] = peak_start
slot[1] = peak_start + interval
slot[2] = peak_start + 2 * interval
...
```

### Step 3: Assign slots to workflows via round-robin
Cycle through workflows so the same workflow doesn't get consecutive slots:
```
Example: 3 workflows (V1, V2, Img), 9 slots
  Slot 0 → V1 (1st trigger)
  Slot 1 → V2 (1st trigger)
  Slot 2 → Img (1st trigger)
  Slot 3 → V1 (2nd trigger)
  Slot 4 → V2 (2nd trigger)
  Slot 5 → Img (2nd trigger)
  Slot 6 → V1 (3rd trigger)
  Slot 7 → V2 (3rd trigger)
  Slot 8 → Img (3rd trigger)
```

Each workflow ends up with 3 well-spaced triggers across the day.

### Step 4: Adjust for collisions
Fetch all existing schedules across Loom. For each proposed slot:
- If the exact (hour, minute) is taken by another page's workflow, shift by +/- a few minutes
- Minimum **5-minute gap** between any two workflows system-wide
- When shifting, prefer rounding to the nearest 5 (e.g., :05, :10, :15) for clean times

### Step 5: Build cron expressions
Each workflow gets 3 cron entries combined:
```
{m1} {h1} * * *,{m2} {h2} * * *,{m3} {h3} * * *
```

## Constraints

1. **Unique minutes globally**: No two workflows across all of Loom should trigger at the same (hour, minute)
2. **5-minute minimum gap**: Between any two workflows system-wide
3. **Even distribution per page**: Posts should be roughly equally spaced throughout peak hours
4. **Round-robin assignment**: Same workflow should not post back-to-back; interleave all workflows
5. **No dead hours**: Avoid posting between 22:00-5:00 (all markets)

## Output Format

Present the recommendation as a **timeline view** for each page:

```
Page: Your Page Name (market: Global, 3 workflows, 9 posts/day)
Interval: ~110 minutes

Timeline:
  05:20  Video 1
  07:10  Video 2
  09:00  Image
  10:50  Video 1
  12:40  Video 2
  14:30  Image
  16:20  Video 1
  18:10  Video 2
  20:00  Image

Cron:
  Video 1:  20 5 * * *,50 10 * * *,20 16 * * *
  Video 2:  10 7 * * *,40 12 * * *,10 18 * * *
  Image:    0 9 * * *,30 14 * * *,0 20 * * *
```

Then ask: "Does this schedule look good? I can adjust any times before applying."

## Applying Schedules

Only apply after user confirms. Use the Loom API:
```
API.updateWorkflow(workflowId, { schedule: cronExpression })
```

## When Adding a Page to an Existing System

When the system already has many pages, finding clean slots is harder:
1. Calculate the ideal interval for the new page
2. Find a starting offset that avoids collisions with existing schedules
3. Try offsets in 5-minute increments until a clean set of slots is found
4. If the ideal interval creates unavoidable collisions, shrink or stretch individual gaps slightly while keeping overall distribution even

## Important Notes

- All cron expressions use **Asia/Bangkok timezone** (configured in Loom's scheduler)
- Cron format: `minute hour * * *` (5-field standard, `* * *` = every day)
- Multiple schedules per workflow are comma-separated
- Each workflow always gets exactly 3 triggers per day
- The interval doesn't need to be exact — ±15 minutes is fine to hit better engagement hours or avoid collisions
