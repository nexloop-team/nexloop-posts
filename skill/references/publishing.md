# Publishing to Instagram through Metricool

## Facts

- Connector: Metricool (tools `mcp__Metricool_Social_Media_Management__*`; load with ToolSearch "metricool").
- Brand: `blogId` / `brandId` **7762809**, timezone **Asia/Calcutta**, Instagram account @nexloop.io.
- Plan: Metricool Free, **max 20 scheduled posts per calendar month**. Before scheduling, call
  `getScheduledPosts` for the month and count; if 20 would be exceeded, don't schedule — save the
  post and tell the owner.
- Instagram carousel = `providers: [{"network":"instagram"}]`, `instagramData.type: "POST"`, 2–20
  images in `media`, JPEG, 4:5. Set `instagramData.isAiGenerated: false` unless AI images were used
  (the slides are designed graphics, not AI imagery).
- `media` takes **public URLs** (or Google Drive / Dropbox links if the owner linked that service
  inside Metricool). Local files can't be sent directly.

## Getting the slides to a public URL — GitHub (set up and tested 2026-11-01)

Repo: **nexloop-team/nexloop-posts** (public, branch `main`). It holds post images only.

1. Attach it: `add_repo(owner="nexloop-team", repo="nexloop-posts", access="push")`, then
   `git clone --depth 1 https://github.com/nexloop-team/nexloop-posts`.
2. Copy the slides into a folder named `YYYY-MM-DD-<theme>-<slug>/` (plus `caption.txt`, `post.json`).
3. Commit and `git push origin main`.
4. Each slide's public URL is
   `https://raw.githubusercontent.com/nexloop-team/nexloop-posts/main/<folder>/slide_01.jpg`.
   Check every URL returns 200 and `image/jpeg` (`curl -s -o /dev/null -w '%{http_code} %{content_type}'`)
   before scheduling.
5. Metricool copies the images to its own storage when the post is created, so the repo files
   only need to exist at that moment. Never put anything private in this repo.

If push is refused, the GitHub account connected to Claude has lost write access to the repo:
stop, deliver the slides and caption, and say so.

## createScheduledPost template

```json
{
  "autoPublish": true,
  "draft": false,
  "descendants": [],
  "firstCommentText": "",
  "hasNotReadNotes": false,
  "media": ["<url slide 1>", "<url slide 2>", "..."],
  "mediaAltText": ["<alt 1>", "<alt 2>", "..."],
  "providers": [{"network": "instagram"}],
  "publicationDate": {"dateTime": "2026-11-02T19:00:00", "timezone": "Asia/Calcutta"},
  "shortener": false,
  "smartLinkData": {"ids": []},
  "text": "<caption>",
  "instagramData": {"type": "POST", "collaborators": [], "carouselTags": {}, "showReelOnFeed": true, "isAiGenerated": false}
}
```

Call: `createScheduledPost(blogId="7762809", date="2026-11-02T19:00:00+05:30", info=<the JSON above as a string>)`.
Report the returned `plannerUrl`. On an error, report it as-is; never claim a post is scheduled
unless the tool returned success.

## Topic log (so fresh sessions don't repeat topics)

The file **`LOG.md`** at the root of the nexloop-posts repo (create it if missing), committed and
pushed with each post's slides.

- Header lines: `Hosting: GitHub nexloop-team/nexloop-posts` and `Plan: Metricool Free (20/month)`.
- One line per post: `YYYY-MM-DD | weekday | pillar | topic # | cover line | status (scheduled/delivered) | plannerUrl`

Read it before choosing a topic; append the new line after scheduling, then commit and push.
Also check Metricool `getScheduledPosts` for the coming 14 days so two runs never book the same slot.
