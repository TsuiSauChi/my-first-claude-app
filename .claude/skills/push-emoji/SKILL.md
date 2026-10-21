---
name: push-emoji
description: Adds a new emoji line to the root README.md before every push to GitHub. Use whenever you are about to run `git push`, or the user asks to push, publish or sync commits to GitHub in this repo.
---

# Push emoji

Every push to GitHub carries one new emoji in the root `README.md`, so the README keeps a small visual log of pushes. Do this before running `git push`, every time.

## Steps

1. **Check there is something to push.** Run `git log --oneline @{u}..` (or `git log --oneline origin/main..` if no upstream is set). If it lists no commits, there is nothing to push: skip this skill and don't touch the README.

2. **Pick the emoji.** Read the `## Emoji log` section at the bottom of the root `README.md` (not `weather/README.md` or `image-upload/README.md`). Choose one emoji that:
   - is **not already used** anywhere in that section, and
   - fits what the commits being pushed do (e.g. 🌧️ for weather changes, 🖼️ for image-upload, 🎨 for styling, 🐛 for a bug fix, 📝 for docs).

3. **Add the line.** Append it as the last line of the section, in this format:

   ```
   - <emoji> YYYY-MM-DD — <subject of the newest commit being pushed>
   ```

   If the section doesn't exist yet, add it at the end of the file:

   ```
   ## Emoji log

   One new emoji for every push to GitHub.

   - <emoji> YYYY-MM-DD — <subject>
   ```

   Change nothing else in the README.

4. **Commit it.** Stage only `README.md` and commit with the message `Add push emoji <emoji> to README`. Don't sweep other uncommitted changes into this commit.

5. **Push.** Run the push the user asked for. The emoji commit goes out with it.

6. **Report** the emoji you added and the line it's on, alongside the push result.

## Notes

- One emoji per push, even when several commits go out together.
- If the push fails (rejected, no remote, auth), say so and leave the emoji commit in place: it will go out with the next successful push, so don't add a second emoji on retry.
