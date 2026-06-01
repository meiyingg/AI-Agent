# Deploy — Vercel (frontend) + Render (backend)

Two services:
- **Backend** (FastAPI + multi-agent + RAG) → **Render** (Docker). Holds the API keys.
- **Frontend** (Next.js) → **Vercel**. Talks to the backend via `NEXT_PUBLIC_API_BASE`.

Deploy the **backend first** (you need its URL for the frontend).

---

## 0. Push the deploy files

```powershell
cd "d:\BaiduSyncdisk\5-材料\简历\研究生\笔试资料\meeting-insight-agent"
git add -A
git commit -m "Add Docker + Render/Vercel deploy config"
git push
```

New files: `Dockerfile`, `.dockerignore`, `render.yaml`, plus a startup hook that auto-loads the sample corpus.

---

## 1. Backend → Render  (https://render.com, free, Docker)

**Easiest (Blueprint):**
1. Render → **New → Blueprint** → connect GitHub → pick **meiyingg/AI-Agent**.
2. It reads `render.yaml` and prompts for the secrets — paste them:
   - `DASHSCOPE_API_KEY` = `sk-...`
   - `TAVILY_API_KEY` = `tvly-...`
   - `APP_PASSWORD` = your login password (e.g. `a464746676`).  `APP_USER` defaults to `admin`.
     *(Leave `APP_PASSWORD` blank only if you want the app fully open — not recommended for a public URL.)*
3. **Apply** → wait ~5–8 min for the first Docker build.
4. Copy the service URL, e.g. `https://chamber-advisor-api.onrender.com`.
5. Test: open `https://<your-backend>/api/health` → should return `{"ok":true}`.

**Manual (if you skip the Blueprint):** New → **Web Service** → the repo → Runtime **Docker**, Root Directory **blank**, Instance **Free** → add the two env vars above → Create.

---

## 2. Frontend → Vercel  (https://vercel.com, free, native Next.js)

1. Vercel → **Add New → Project** → import **meiyingg/AI-Agent**.
2. **Root Directory** → set to **`web`**  (important — the Next app lives in `web/`).
3. Framework auto-detects **Next.js**; leave build/install as default (it uses `pnpm`).
4. **Environment Variables** → add:
   - `NEXT_PUBLIC_API_BASE` = `https://<your-backend>.onrender.com`  *(the Render URL from step 1.4, no trailing slash)*
5. **Deploy** → you get `https://<something>.vercel.app`. Share that link.

> `NEXT_PUBLIC_*` is baked in at build time. If you change the backend URL later, update the var and **Redeploy** on Vercel.

---

## 3. Verify

Open the Vercel URL → log in (any name) → ask *"Should our battery factory build a plant in Malaysia?"*.
The first request may take **~30–60s** if the Render free instance was asleep (see below); after that it's fast.

---

## 4. Custom domain (optional — e.g. `ai.fuhua-edu.com`)

Point the domain at the **Vercel frontend** (the backend stays on its Render URL):

1. **Vercel** → your project → **Settings → Domains** → add `ai.fuhua-edu.com`. Vercel shows a DNS target (usually a CNAME to `cname.vercel-dns.com`).
2. **Cloudflare** → `fuhua-edu.com` zone → **DNS** → add a **CNAME**: name `ai`, target = the value Vercel gave.
   - Start with **DNS only** (grey cloud) so Vercel can issue the TLS cert; you may switch to **Proxied** (orange) afterward.
   - If you keep it Proxied, set Cloudflare **SSL/TLS mode = Full** (not Flexible) to avoid redirect loops.
3. Wait for Vercel to show the domain as **Valid / certificate issued** (a few minutes). Done.
4. **No code/env change** — CORS is open and the frontend still calls the Render backend via `NEXT_PUBLIC_API_BASE`.

> Want a tidy backend domain too (e.g. `api.fuhua-edu.com`)? Render → Settings → **Custom Domains** → add it → make the matching Cloudflare CNAME → then set Vercel's `NEXT_PUBLIC_API_BASE` to `https://api.fuhua-edu.com` and redeploy. Optional — the `onrender.com` URL works fine.

---

## Notes / gotchas

- **Cold start:** Render free spins down after ~15 min idle; the next request wakes it (~30–60s). For a live demo, open the site ~1 min beforehand to warm it up.
- **🔒 Access:** the app requires the `APP_PASSWORD` login, enforced on the **backend** (every `/api/*` call checks an `X-Access-Code` header). So only people you give the password to can use it — that's the real protection against quota abuse. The password lives only in the Render env var, never in the repo.
- **💰 Cost:** still set a **budget alert / cap in the Alibaba Cloud DashScope console** as a backstop, and since the keys were shared during development, consider **rotating** them.
- **Data is ephemeral on free tier:** uploaded files and learned long-term memory reset when the instance recycles. The bundled sample corpus re-ingests automatically on startup, so the "internal knowledge" demo always has content.
- **CORS:** already open (`allow_origins=["*"]`), so no extra config.
- **Keys never go in git** — they live only in the Render dashboard.
