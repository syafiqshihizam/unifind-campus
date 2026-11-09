# CampusBack V8 — Simplified Complete Prototype

**FOUND ITEMS ONLY**. This is an actual working campus lost-property prototype, not an image or a static mockup. It uses Python's built-in HTTP server, SQLite, HTML, CSS and JavaScript. No extra `pip install` commands are needed.

## ⭐ START HERE (Windows + VS Code)

1. Extract `CampusBack_V8_COMPLETE.zip`.
2. Open the **CampusBack** folder in VS Code: File → Open Folder.
3. Open Terminal → New Terminal.
4. First time ONLY: type `python seed_demo.py` and press Enter.
5. Type `python server.py` and press Enter.
6. Open **http://localhost:8000** in Edge or Chrome.
7. Keep VS Code's terminal open while using the website.

If Windows says `python` is not recognized, use `py seed_demo.py` and `py server.py` instead. You can also double-click `RUN_CAMPUSBACK.bat` from the project folder; this automatically seeds a fresh database only on first run.

**No need to download a second ZIP, fix script or reset script.**

## Only TWO account types

| Person | Demo email | Demo password | What they do |
|---|---|---|---|
| Sara (student) | `sara@campus.test` | `Demo1234!` | Claims Daniel's found item; can also post her own found items |
| Daniel (student) | `daniel@campus.test` | `Demo1234!` | Finder for wallet, earbuds and backpack |
| Counter staff | `counter@campus.test` | `Demo1234!` | Receives physical items, checks student ID, confirms owner collection |

**Student is one role:** there is no separate finder login or owner login. When Sara posts an item, she acts as a finder; when Sara claims Daniel's item, she acts as an owner.

## Pages — now simple

### Student

**Community**: Only available Found Items, never Lost Items. No lost reporting or automatic matching. Open an item to see picture, location, finder and description; choose *Request to Collect*.

**My Activity**: Clear toggle between **I Want to Collect** (owner's requests) and **Items I Found** (finder's incoming requests and their own Found reports). Each request has a clear *next step* message and only the appropriate buttons for that user. Finished/cancelled requests go into a collapsed History section.

**+ Report Found Item**: Only found reports. Choose name, category, location, date, optional photo, preferred counter, and a **private security question + answer**.

### Counter staff

**Counter Desk** only. Choose a location (Student Affairs Office / Library Counter / Security Office / All), then see a three-step queue:

1. **Finder preparing item** — finder still has item, no staff action yet.
2. **Confirm physical receipt** — staff presses Confirm Item Received only after the finder physically brings it.
3. **Release to owner** — staff checks student ID/evidence, hands it over, and presses Confirm Owner Collected. Completed items are in collapsed History.

## Try Scenario A — Meet Finder

1. Log in as **Sara** → Community → **Black Wallet** → Request to Collect → **Meet the Finder**.
2. Visit **My Activity → I Want to Collect**. Your request says *Waiting for finder reply*.
3. Log out. Log in as **Daniel** → **My Activity → Items I Found** → find the Black Wallet request → **Accept meetup** (or Decline with reason).
4. Log out. Log in as **Sara** → **My Activity → I Want to Collect** → see Daniel's contact (after approval only).
5. Meet Daniel outside the app. After receiving the item, Sara presses **I've Collected My Item**. **Daniel does not need to confirm again.**
6. If it is *not* Sara's wallet, Sara presses **This is not my item**, and the wallet goes back to Available in Community.

**If finder declines because they cannot meet**: Sara sees the reason and can **Wait for Finder**, **Collect at Campus Counter** (private security answer needed) or **Cancel**. If finder declines because claimant is not the owner, claim is rejected and item is relisted.

## Try Scenario B — Campus Counter

1. Log in as **Sara** → Community → **White Wireless Earbuds** → Request to Collect → **Collect at Campus Counter**.
2. Answer the demo private question with `Blue` (capitalisation doesn't matter). A wrong answer shows an error and does not create a collection request.
3. In **My Activity → I Want to Collect**, Sara sees *Finder to bring item*.
4. Log in as **Daniel** → **My Activity → Items I Found** → **I've Submitted This Item** (only after physically handing over the earbuds).
5. Log in as **Counter Staff** → **Counter Desk**. Filter by **Student Affairs Office** → **Step 2: Confirm Item Received**.
6. Item moves to Step 3: **Release to owner**. Only after checking Sara's identity and handing over the item, press **Confirm Owner Collected**.
7. Completed request is in Counter History and Sara's completed history. It is NOT a second item or a duplicate listing.

## Back up / upgrade your V7 project **without losing your records**

This complete ZIP has a fresh-code project with **no SQLite database shipped**. To update your EXISTING V7 project instead:

1. Stop your old Python server with `Ctrl+C`.
2. **Copy your old `data/` and `uploads/` folders somewhere safe** before updating.
3. Extract this ZIP, then copy only these 4 files over the SAME relative paths in your old CampusBack folder:
   - `server.py`
   - `static/app.js`
   - `static/styles.css`
   - `static/index.html`
4. Do NOT replace `data/` or `uploads/`.
5. In VS Code run `python server.py`, open localhost:8000 and press `Ctrl+Shift+R` for a hard refresh.
6. Skip `seed_demo.py` when keeping existing data. Existing V7 user, found-item and pickup records remain; old V3–V5 records may have different semantics.

For a completely clean demo, extract the full project into a NEW folder and run seed_demo.py there. This is safer than deleting or changing your V7 data.

## Files

- `server.py` — authentication, DB schema and migrations, Found items, pickup requests, counter actions
- `static/index.html`, `static/app.js`, `static/styles.css` — real responsive UI
- `seed_demo.py` — demo student accounts, staff account and sample Found items (run once for fresh demo)
- `RUN_CAMPUSBACK.bat` — optional Windows launcher
- `tests/test_v8.py` — isolated backend integration tests
- `screenshots/` — verified interface previews
- `data/`, `uploads/` — local persistent database and images, **created/filled on your machine**

Run backend checks: `python tests/test_v8.py`.

## IMPORTANT classroom-only safety limitations

The system is intended for local coursework demonstration. A private security answer is only a preliminary check, not conclusive proof of ownership. Finder phone numbers are shown to approved meetup claimants only; do not post phone numbers in public item descriptions. Counter staff must physically verify ID and ownership before releasing an item. Demo passwords, local SQLite and local uploads are **not safe for public internet deployment** without stronger authentication, persistent storage, abuse protection and privacy safeguards.
