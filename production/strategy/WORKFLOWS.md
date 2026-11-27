# vidIQ research workflows — Ancient World Files

Channel: Ancient World Files (@ancientworldfiles) · `UCw0s1jDKX3Y8UznLnyfryDg`
Tools: the connected vidIQ MCP server (`mcp__vidIQ__*`). Every number in a report must come from a tool call made in that session.
Anything not returned by vidIQ is labelled **estimate** or **judgement**.

## Credit budget (vidIQ plan: 2,000 renewable credits a month)
| Call | Credits |
|---|---|
| `vidiq_keyword_research` (any mode) | 5 |
| `vidiq_outliers`, `vidiq_trending_videos`, `vidiq_youtube_search` | 5 |
| `vidiq_channel_analytics`, `vidiq_channel_stats`, `vidiq_channel_videos`, `vidiq_similar_channels` | 5 |
| `vidiq_score_title` | 5 |
| `vidiq_youtube_channel_audit` | 10 |
| `vidiq_balance`, `vidiq_user_channels`, `vidiq_job_poll`, `vidiq_list_competitors` | 0 |

Caps: weekly scheduled run ≤ 80 credits · pre-production research ≤ 100 credits per documentary.
Check `vidiq_balance` first and stop if fewer than 300 credits remain.

---

## 1. Weekly trend and competitor scan (scheduled, Mondays)
1. `vidiq_balance` (0).
2. `vidiq_keyword_research` mode `rising`, niche "ancient history, archaeology, ancient civilizations documentaries", period `week` (5).
   Drop off-niche rows (sports, politics, celebrities, games). Keep only what Ancient World Files could make.
3. `vidiq_outliers` long-form, `publishedWithin: thisMonth`, three keywords rotated from the list below (15):
   underground places · ancient Egypt tombs · Roman Empire · ancient Greece · lost cities · new archaeological discoveries · Bronze Age · ancient engineering · ancient murders and mysteries · fallen empires.
4. `vidiq_outliers` with `channelIds` = the competitor set below, `publishedWithin: thisMonth` (5).
5. `vidiq_channel_analytics` traffic sources and YT_SEARCH search terms for the last 28 days (10).
6. `vidiq_channel_analytics` `top_videos` for the last 28 days (5).
7. Write `reports/YYYY-MM-DD_weekly.md` with the template in section 6, then commit and push it.

Competitor set (from `vidiq_similar_channels`, 2026-11-27):
History Time `UCN9v4QG3AQEP3zuRvVs2dAg` · Ancient Architects `UCscI4NOggNSN-Si5QgErNCw` · The Helix Report `UCSIY635D06diBmhOWd-0c8A` ·
Rome Unscrolled `UCuyKlvQhPbPKdENL8y1lDrA` · The Ancients `UC2J29LPhS9vMiWyYEqBRB0w` · IntoTheMap `UCRWH9H1yxLfNQo84P1NWC3w` ·
History with Cy `UCZzqG2zfeRKMoJwDwk1FTvQ` · Bright Side History Legends Awakened `UCGF4Q7GAugyb4xKR23YeHOQ` ·
Ancient Mysteries Lab `UCY35rQvQF9lCeIq4loli-Mg` · Echoes of History `UCJ5VTXHGmYQNqRc86IwVcyA`

## 2. Monthly channel review (first Monday of the month)
`vidiq_youtube_channel_audit` (10), then `audience_retention` for the two most-viewed new uploads (10).
Do not judge a video on CTR alone. Read impressions, traffic source, retention at 2% / 10% / 50%, and watch time together.

## 3. Before every new documentary (pre-production, ≤ 100 credits)
1. `vidiq_keyword_research` on the topic (research mode) and its two best related phrases (15).
2. `vidiq_keyword_research` mode `questions` on the topic (5): these become chapter questions and description lines.
3. `vidiq_outliers` keyword = topic, long-form, all time and then this year (10). Read titles, lengths and channel sizes. Breakout score is relative to the channel, so compare it with subscriber count.
4. `vidiq_youtube_search` order `viewCount`, `videoDuration: long` (5): see who already owns the search results.
5. Write 10 titles. Score the best 4 with `vidiq_score_title` (20).
   A score is a CTR model. It does not check facts, so every title must also pass the accuracy rules in `../QC_RULES.md`.
6. Three thumbnail concepts (section 5).
7. Fill in the scoring table (section 7) and write `reports/YYYY-MM-DD_<topic>.md`. Do not start production until the report exists.

## 4. Title rules
- People first, search second. The main keyword goes in the first 40 characters where it reads naturally.
- One concrete hook: a number, a date, a named object, or a real open question.
- No claim the documentary does not support. Avoid the "Not What You Were Told" formula unless the film really overturns a common belief.
- Under 70 characters.

## 5. Thumbnail rules (1280 × 720)
- One focal subject that reads at phone size (about 160 px wide). At most three words of text, and never the title repeated.
- High contrast between subject and background. Leave the bottom-right corner clear for the duration badge.
- Use a real artefact or place when one exists. An AI reconstruction must not be passed off as a photograph.
- Check the shortlist with `vidiq_youtube_preview` (1 credit) beside real competitors before publishing.

## 6. Report template
```
# <title> — <date>
## Data (from vidIQ, with the tool used)
## Competing videos
## Judgement (ours, not vidIQ)
## Recommendation and risks
## Credits used
```

## 7. Opportunity score (each factor 1–10; say which are data and which are judgement)
| Factor | Source |
|---|---|
| Search demand | vidIQ volume and monthly estimate (data) |
| Competition (10 = easy) | vidIQ competition score (data) |
| Competitor performance | outlier breakout scores (data) |
| Fit with our search traffic | our YT_SEARCH terms (data) |
| Historical significance | judgement |
| Curiosity / mystery | judgement |
| Can carry 45–60 min | judgement |
| Evergreen | judgement, plus the growth % if vidIQ gives one |
| Fits Ancient World Files | judgement |
Overall = mean. Data factors are listed first so the evidence is visible.
