# Launch ARISE-I

## Product positioning

**ARISE-I makes the folder everyone avoids—their Downloads folder—feel calm again.**

It is a private, one-click desktop organizer for students, professionals, and anyone who saves files faster than they file them. It sorts locally, never deletes files, and every organization run can be undone.

**Short pitch:** *A calmer Downloads folder, in one click.*

## Who it is for

- Students managing notes, submissions, media, and ZIP files.
- Busy professionals whose Downloads folder is a daily dumping ground.
- Creators and freelancers who regularly receive assets, PDFs, and exports.

Start with the Downloads-folder use case. It is easy to understand and gives users a visible result in seconds.

## Landing-page copy

### Hero

**Your Downloads folder, finally under control.**

ARISE-I organizes files into clear folders in one click. Everything stays on your computer, nothing is deleted, and you can undo any run.

**Primary CTA:** Download for Windows  
**Secondary CTA:** See how it works

### Three benefits

**One click, instant order**  
Sort documents, images, videos, code, archives, and more into sensible folders.

**Private by default**  
ARISE-I works locally. Your files are not uploaded to a server.

**Safe to try**  
Use Preview to see planned changes first, or Undo to restore the last organization run.

## Release process

1. Update `version` in `pyproject.toml`, `APP_VERSION` in `gui.py`, and `AppVersion` in `ARISE-I.iss` together.
2. Commit and push the release commit.
3. Create and push a matching tag, for example: `git tag v1.3.0 && git push origin v1.3.0`.
4. GitHub Actions builds and attaches these customer-ready downloads to the GitHub Release:
   - `ARISE-I-Setup-<version>-Windows.exe` — guided Windows installer.
   - `ARISE-I-macOS.zip` — drag `ARISE-I.app` to Applications.
   - `ARISE-I-Linux.tar.gz` — extract and run `ARISE-I/ARISE-I`.

For early distribution, link the Windows installer directly from the landing page. macOS users may need to approve the app in System Settings until you enroll in Apple’s notarization program; Windows SmartScreen reputation similarly improves after code signing and downloads accumulate.

## Launch checklist

- Add a 20-second screen recording: messy Downloads → Preview → Organize → tidy folders.
- Publish the GitHub Release and test each downloaded artifact on a clean machine.
- Put the privacy and undo promises above the fold on the landing page.
- Start with a free beta and collect the one question that matters: “Did this save you time today?”
- Do not promise an all-purpose AI assistant. Lead with the concrete outcome: a tidy Downloads folder.
