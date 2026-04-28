# Step 12A — User Review (GitHub Pages Deployment)

**What Step 12 covers:** Automated CI/CD pipeline that builds the game with pygbag
and deploys it to GitHub Pages on every push to `master`.  After this step, anyone
can play the game by navigating to the public URL — no installer, no setup.

---

## 1. What changed

| File | Change |
|---|---|
| `.github/workflows/deploy.yml` | New — GitHub Actions workflow: checkout → install uv → build with pygbag → deploy to GitHub Pages |

No game code was touched.

---

## 2. One-time GitHub setup (do this first)

### 2a. Create a GitHub repository

1. Go to https://github.com/new
2. Repository name: `avalanche` (or any name you prefer)
3. Visibility: **Public** (GitHub Pages requires public repo on the free plan)
4. Do **not** initialise with a README — the repo will get its first commit from you.
5. Click **Create repository**.

### 2b. Connect your local repo

```bash
cd F:/Python/Avalanche
git remote add origin https://github.com/<your-username>/avalanche.git
```

### 2c. Enable GitHub Pages via Actions

1. Go to your repo on GitHub → **Settings** → **Pages** (left sidebar).
2. Under **Build and deployment → Source**, select **GitHub Actions**.
3. Click **Save** (there may be no button — the setting is applied on first workflow run).

> **Note:** Do this **before** your first push so GitHub Pages is ready when the
> workflow tries to deploy.

### 2d. Initial commit and push

```bash
cd F:/Python/Avalanche

# Stage all project files (adjust if you want to exclude some)
git add CLAUDE.md README.md main.py constants.py renderer.py cube_data.py \
        grid_manager.py wave_manager.py wave_data.py player.py game_manager.py \
        hud.py effects.py pygbag.ini pyproject.toml uv.lock run_dev.sh \
        custom.tmpl static/ scripts/ docs/ .github/ .gitignore .python-version

git commit -m "Initial commit: Avalanche v1 + GitHub Pages CI"
git push -u origin master
```

---

## 3. Verify the workflow runs

1. Go to your repo on GitHub → **Actions** tab.
2. You should see a workflow run named **"Build & Deploy to GitHub Pages"** in progress.
3. Click into it. You should see one job: **build-deploy**.
4. The job takes ~60–90 s on a cold runner (uv downloads pygbag + dependencies on
   first run; subsequent runs are faster).
5. All steps should show ✅. The **Deploy to GitHub Pages** step shows the live URL.

---

## 4. Verify the live game

1. Open the URL shown in the Actions run.
   Canonical format: `https://<username>.github.io/<repo>/` (with trailing slash).
   Omitting the slash works but triggers a redirect — bookmark the trailing-slash form.
2. **While loading:** pygbag's built-in loading bar is visible from the very first frame
   (white progress bar on a black background with status text).  This is expected and
   means the build is correct.  The first load takes ~30 s while the CDN downloads the
   CPython WASM runtime.
3. **After loading:** the title screen appears.  Press SPACE or click to start.
4. Play through at least one wave to confirm nothing broke in the build.

---

## 5. Verify PWA features still work on the deployed URL

HTTPS is now real (not localhost), so all PWA features are fully active.

| Check | How |
|---|---|
| **Manifest** | DevTools → Application → Manifest — all fields populated, no errors |
| **Service worker** | DevTools → Application → Service Workers — `activated and is running` |
| **Install prompt** | Chrome address bar shows install icon (monitor + ↓ arrow) |
| **Install works** | Standalone window opens, title "Avalanche", gold cube icon |

**Offline note:** after the service worker activates and the page has loaded once,
the shell (`index.html`, manifest, icons) loads from cache when offline.  Gameplay
itself requires the CDN WASM runtime on first visit.  Once that CDN asset has been
fetched and the browser caches it independently, fully offline play becomes possible
in subsequent sessions.

---

## 6. Verify automatic redeploy

Make a trivial change (e.g. add a space to `README.md`), commit, and push to `master`.
The workflow should trigger within seconds and deploy the update within ~90 s.

---

## 7. Success criteria

- [ ] **Workflow passes** — all steps green in Actions tab.
- [ ] **Game loads** at the public URL without any errors.
- [ ] **Playable** — at least one wave completes correctly.
- [ ] **PWA manifest** visible in DevTools at the public URL.
- [ ] **Service worker active** at the public URL.
- [ ] **Install prompt** appears in Chrome on the public URL.
- [ ] **Auto-redeploy** — a follow-up push triggers a new successful run.

---

## 8. Intentionally out of scope for Step 12

- **Custom domain** — add a CNAME file to `static/` and configure the domain in
  GitHub Pages settings when desired.
- **Lighthouse 100** — run Lighthouse against the public URL once deployed; add a
  `screenshots` entry to `manifest.json` when a good screenshot is available.
- **Caching uv/pygbag** — uv tool caching is enabled via `cache: true` in the
  workflow; further optimisation with `actions/cache` is possible but not needed.
- **Mobile layout** — the game is `orientation: landscape` and designed for keyboard
  play.  Mobile touchscreen support is not implemented; the game is playable on a
  phone only with a Bluetooth keyboard.  This is intentional and not a regression.

---

## 9. Expert panel findings (Step 12A)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | CONCERNS → APPROVED | `SHELL_URLS` absolute paths (`/index.html`) resolve to domain root, not to `/<repo>/` on GitHub Pages — SW pre-cache 404s on all shell assets. | `SHELL_URLS` now uses `BASE + 'filename'` where `BASE = new URL('./', self.location.href).pathname`. Works on both localhost (`/`) and GitHub Pages (`/repo/`). `CACHE_NAME` bumped to `avalanche-v2` to force re-registration. |
| Code Quality | CONCERNS → APPROVED | (1) `timeout 60 … || true` swallows build errors; 60 s too short for cold runners. (2) Missing `set -euo pipefail` in run block. | (1) Replaced with `pygbag --build` which exits on build completion with correct exit code; `set -euo pipefail` added. (2) `cache: true` added to `setup-uv`. |
| UX Tester | CONCERNS → APPROVED | (1) Loading bar not mentioned for end-player. (2) Redundant URL format in Section 4. (3) Offline expectation missing for players. (4) Mobile touchscreen scope not addressed. | (1-3) Review doc updated: loading bar described, canonical URL form shown, offline note added. (4) Mobile added to "out of scope" with explanation. |
| Platform Engineer | CONCERNS → APPROVED (with post-deploy correction) | (1) `timeout 60` too short on cold runners. (2) Suggested `--no_server` flag — incorrect, flag does not exist in 0.9.3; actual flag is `--build` (confirmed from pygbag help output). (3) SW sub-path bug. (4) `.python-version`/`run_dev.sh` in APK. | (1-2) Replaced with `--build` (corrected after first CI run failed). (3) Fixed in `sw.js`. (4) Added both to `ignorefiles` in `pygbag.ini`. |

---

## 10. What to tell me after you review

- **"Step 12 approved, proceed"** — move on to B1 (turbo key).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
