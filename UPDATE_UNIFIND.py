
from pathlib import Path
from shutil import copy2

# UniFind UI Update for CampusBack V8
# Does not change database, user accounts, or backend.

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"

required = [
    STATIC / "index.html",
    STATIC / "app.js",
    STATIC / "styles.css",
]

missing = [str(p) for p in required if not p.exists()]

if missing:
    raise SystemExit(
        "Cannot find frontend files: " + ", ".join(missing)
    )

# Backup original frontend files first
BACKUP = BASE / "backup_before_unifind"
BACKUP.mkdir(exist_ok=True)

for file in required:
    target = BACKUP / file.name
    if not target.exists():
        copy2(file, target)


# ==================================================
# 1. NEW UNIFIND HTML
# ==================================================

HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport"
          content="width=device-width, initial-scale=1">

    <meta name="theme-color" content="#385ce8">
    <meta name="description"
          content="UniFind - find and return items around campus.">

    <title>UniFind | Campus Found Items</title>

    <link rel="stylesheet" href="/styles.css?v=9">
    <script defer src="/app.js?v=9"></script>
</head>

<body>

<header class="topbar">
    <div class="shell navrow">

        <button
            class="brand"
            data-page="community"
            aria-label="UniFind home">

            <span class="mark" aria-hidden="true">U</span>

            <span>
                Uni<span class="brand-blue">Find</span>
                <small>FOUND ITEMS COMMUNITY</small>
            </span>

        </button>

        <nav
            id="nav"
            class="nav"
            aria-label="Main navigation">
        </nav>

        <div class="nav-right">

            <button
                class="account"
                id="accountBtn">
                Log in
            </button>

            <button
                class="primary report-nav"
                data-page="report">
                + Report Found Item
            </button>

        </div>

    </div>
</header>

<main
    id="app"
    class="shell"
    aria-live="polite">

    <p>Loading UniFind...</p>

</main>

<footer class="shell site-footer">
    UniFind · Find it. Claim it. Reunite.
    · University project prototype
</footer>

<div
    id="toastArea"
    class="toast-area"
    aria-live="polite">
</div>

<dialog
    id="modal"
    aria-label="UniFind dialog">

    <div id="modalBody"></div>

</dialog>

</body>
</html>
"""


# ==================================================
# 2. NEW UNIFIND UI STYLING
# ==================================================

THEME = r"""
/* === UNIFIND V9 THEME START === */

/* GLOBAL COLORS */

:root {
    color-scheme: light;

    --uf-navy: #142a50;
    --uf-blue: #385ce8;
    --uf-ink: #233a60;
    --uf-muted: #516589;
    --uf-line: #d9e3f4;
    --uf-surface: #ffffff;
    --uf-surface-2: #f1f5fd;

    background: #f2f5fb;
    color: var(--uf-navy);

    font-size: 15.5px;
}

body {
    min-width: 320px;

    background: linear-gradient(
        180deg,
        #eaf1ff 0,
        #f3f6fc 270px,
        #f2f5fa 100%
    );
}

p {
    color: var(--uf-muted);
}

/* PAGE WIDTH */

.shell {
    max-width: 1160px;
    padding-left: 28px;
    padding-right: 28px;
}

/* NAVIGATION BAR */

.topbar {
    background: rgba(255,255,255,.96);
    border-bottom: 1px solid #dce5f6;

    box-shadow: 0 2px 15px #172f5c0a;
    backdrop-filter: blur(12px);
}

.navrow {
    min-height: 74px;
    gap: 18px;
}

/* UNIFIND LOGO */

.brand {
    gap: 11px;
    font-size: 1.43rem;
    letter-spacing: -.055em;
    color: var(--uf-navy);
}

.brand .brand-blue {
    color: var(--uf-blue);
}

.brand small {
    letter-spacing: .13em;
    color: #6980a5;
    font-size: .49rem;
    margin-top: 3px;
}

.mark {
    height: 42px;
    width: 42px;

    display: grid;
    place-items: center;

    font-size: 1.6rem;
    font-weight: 800;

    border-radius: 13px;
    color: white;

    background: linear-gradient(
        145deg,
        #5377f6,
        #3155d8
    );

    box-shadow: 0 7px 15px #315bd02e;
}

/* NAVIGATION BUTTONS */

.navlink,
.account {
    border-radius: 10px;
    font-weight: 700;
}

.navlink {
    color: #435980;
}

.navlink:hover {
    color: #284dc9;
    background: #f0f4fd;
}

.navlink.selected {
    color: #2a52d4;
    background: #eaf0ff;
}

.account {
    background: #eff3fc;
    color: #284477;
    border: 1px solid #e2e9f7;
}

/* BUTTONS */

.primary,
.secondary {
    border-radius: 11px;

    transition:
        background .15s,
        box-shadow .15s,
        transform .15s;
}

.primary {
    background: #3c61ed;
    box-shadow: 0 6px 13px #355ce521;
}

.primary:hover {
    background: #294ed2;
    transform: translateY(-1px);
}

.secondary {
    border-color: #cfdbf0;
    color: #3155aa;
}

button:focus-visible,
summary:focus-visible,
.item-tile:focus-visible {
    outline: 3px solid #86a2ff;
    outline-offset: 3px;
}

/* PAGE HEADINGS */

.hero {
    padding-top: 34px;
    padding-bottom: 17px;
}

.hero h1 {
    color: #122a54;
    letter-spacing: -.045em;

    font-size: clamp(
        1.8rem,
        2.9vw,
        2.35rem
    );
}

.hero > p:last-child {
    color: #53698d;
    font-size: .95rem;
    max-width: 750px;
}

.eyebrow {
    color: #3d61d9 !important;
}

/* GUIDE SECTION */

.guide {
    background: #e8efff;
    border-color: #d4e2fc;
    color: #3c578c;

    margin-bottom: 18px;
}

.guide b {
    background: #d4e3ff;
    color: #2c51c3;
}

/* MAIN PANELS */

.panel,
.form-panel,
.request-card,
.mini-found,
.history,
.counter-stat {
    border-color: var(--uf-line);

    box-shadow: 0 6px 22px #1d37610b;
}

.panel,
.form-panel {
    background: white;
}

/* SECTION TITLES */

.section-heading {
    margin-top: 22px;
}

.section-heading h2 {
    color: #17325d;
    font-size: 1.16rem;
}

.section-heading p,
.subtle {
    color: #5d7194;
}

/* SEARCH AND FORM INPUTS */

.search-bar {
    margin: 18px 0 24px;
}

input,
select,
textarea,
.search-bar input,
.search-bar select {
    background: white;
    border-color: #cddaf0;
    color: #213a62;
}

input::placeholder,
textarea::placeholder {
    color: #8796ae;
}

/* COMMUNITY ITEM CARDS */

.item-grid {
    gap: 16px;
}

.item-tile {
    border-color: #d9e3f4;
    border-radius: 17px;

    box-shadow: 0 6px 18px #1a38600b;
}

.item-tile:hover {
    transform: translateY(-3px);
    border-color: #abc0f3;

    box-shadow: 0 13px 26px #1b376323;
}

.item-photo {
    height: 190px;
    background: #e9effb;
}

.tile-body {
    padding: 17px 18px 18px;
}

.tile-body h3 {
    color: #162f59;
    margin: 9px 0 6px;
    font-size: 1.02rem;
}

.tile-body p {
    color: #576a89;
    line-height: 1.55;
}

.tile-body .posted {
    color: #647995;
}

.item-link {
    color: #315bd6;
}

/* STATUS BADGES */

.tag {
    font-size: .72rem;
}

.tag.green {
    background: #dff8ed;
    color: #106c4a;
}

.tag.amber {
    background: #fff2d8;
    color: #88590b;
}

.tag.red {
    background: #ffe8eb;
    color: #ac2742;
}

/* MY ACTIVITY */

.choice {
    border-color: #d9e4f3;
    box-shadow: 0 3px 13px #23416d08;
}

.choice.selected {
    border-color: #5f81ed;
    background: #edf3ff;
}

.role-help,
.staff-hint {
    background: #e9f0ff;
    color: #3a5684;
}

.request-card {
    border-radius: 16px;
}

.request-info .meta,
.meta {
    color: #657a9d;
}

.next-step {
    background: #eef3fc;
    color: #34517c;
}

/* PROGRESS STEPS */

.step {
    color: #617393;
}

.step.done {
    color: #2d5bc8;
}

/* COUNTER STAFF */

.counter-stat {
    background: white;
    border-radius: 16px;
}

.counter-stat b {
    color: #244a94;
}

/* EMPTY STATES */

.empty {
    background: #fdfefe;
    border-color: #c6d7f2;
}

.empty p {
    color: #617696;
}

.quiet-empty {
    background: #f8faff;
}

/* COMPLETED HISTORY */

.history {
    background: white;
}

/* FOOTER */

.site-footer {
    color: #7081a0;
    margin-top: 54px;
}

/* NOTIFICATIONS */

.toast-area {
    position: fixed;

    z-index: 3000;

    top: 86px;
    right: 22px;
    left: auto;

    max-width: min(
        420px,
        calc(100vw - 28px)
    );

    pointer-events: none;
}

.toast {
    border-radius: 12px;
    font-size: .88rem;

    box-shadow: 0 13px 30px #1a2e4c29;
}

/* POPUPS */

dialog {
    border-color: #d5e1f4;
    border-radius: 20px;

    width: min(
        560px,
        calc(100vw - 28px)
    );

    box-shadow: 0 30px 80px #10284b55;
}

dialog::backdrop {
    background: #132845a3;
    backdrop-filter: blur(3px);
}

#modalBody {
    padding: 25px;
}

.modal-head-title {
    color: #3159dc;
    font-size: 1.02rem;
}

.modal-intro h2 {
    color: #16325a;
}

.detail-description {
    background: #f0f4fc;
    color: #405a80;
}

/* COLLECTION METHODS */

.method {
    border-color: #d3e0f5;
}

.method:hover {
    background: #ebf2ff;
    border-color: #6686eb;
}

/* SECURITY QUESTION */

.question {
    background: #eaf1ff;
    color: #284b97;
}

/* LOGIN ERROR */

.inline-error.bad {
    background: #fff0f1;
    border-color: #eeb1be;
}

/* LARGE DESKTOP */

@media (min-width: 1200px) {

    .item-grid {
        grid-template-columns:
            repeat(3, minmax(0,1fr));
    }

    .item-photo {
        height: 195px;
    }

}

/* TABLET */

@media (max-width: 900px) {

    .shell {
        padding-left: 20px;
        padding-right: 20px;
    }

    .navrow {
        row-gap: 8px;
    }

    .nav {
        order: 3;
        width: 100%;
        justify-content: flex-start;
    }

    .navlink {
        flex: 1;
    }

}

/* MOBILE PHONE */

@media (max-width: 640px) {

    .shell {
        padding-left: 15px;
        padding-right: 15px;
    }

    .navrow {
        min-height: 0;
        gap: 9px;

        padding: 13px 0 10px;
    }

    .brand {
        font-size: 1.18rem;
    }

    .brand small {
        font-size: .42rem;
    }

    .mark {
        height: 38px;
        width: 38px;
        font-size: 1.45rem;
    }

    .nav-right {
        margin-left: auto;
        gap: 7px;
    }

    .account {
        padding: 9px 10px;
        font-size: .74rem;
    }

    .report-nav {
        padding: 9px 10px;
        font-size: .72rem;
        min-height: 39px;
    }

    .nav {
        padding-top: 5px;
        justify-content: stretch;
    }

    .navlink {
        padding: 10px 9px;
        font-size: .8rem;
    }

    .hero {
        padding-top: 26px;
    }

    .guide {
        gap: 10px;
        padding: 12px 13px;
    }

    .item-grid {
        grid-template-columns:
            repeat(2, minmax(0,1fr));

        gap: 12px;
    }

    .item-photo {
        height: 145px;
    }

    .tile-body {
        padding: 13px;
    }

    .tile-body h3 {
        font-size: .87rem;
    }

    .tile-body p {
        font-size: .76rem;
    }

    .request-card {
        padding: 15px;
    }

    .buttons button {
        min-height: 44px;
    }

    #modalBody {
        padding: 20px 17px;
    }

    .toast-area {
        top: 110px;
        right: 12px;
    }

}

/* SMALL PHONE */

@media (max-width: 370px) {

    .item-grid {
        grid-template-columns: 1fr;
    }

    .item-photo {
        height: 170px;
    }

}

/* === UNIFIND V9 THEME END === */
"""


# ==================================================
# 3. APPLY NEW BRANDING
# ==================================================

html_file, js_file, css_file = required

# Update HTML
html_file.write_text(
    HTML,
    encoding="utf-8"
)

# Update JavaScript text, preserving all functions
js = js_file.read_text(encoding="utf-8")

js = js.replace("CAMPUSBACK", "UNIFIND")
js = js.replace("CampusBack", "UniFind")

js_file.write_text(
    js,
    encoding="utf-8"
)

# Add updated UI theme to existing CSS
css = css_file.read_text(encoding="utf-8")

start_marker = "/* === UNIFIND V9 THEME START === */"

# Prevent duplicate themes when run again
if start_marker in css:
    css = css.split(start_marker)[0].rstrip()

css_file.write_text(
    css + "\n\n" + THEME.strip() + "\n",
    encoding="utf-8"
)

print()
print("SUCCESS! UniFind interface updated.")
print()
print("Files updated:")
print("- static/index.html")
print("- static/app.js")
print("- static/styles.css")
print()
print("Database, photos, passwords and server.py unchanged.")
print()
print("Run python server.py and refresh your browser.")
