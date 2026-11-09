# Deploy UniFind sebagai PWA (GitHub + Render)

## 1. Push ke GitHub (repo mesti PRIVATE)
Folder ini mengandungi `data/campusback.db` (akaun & rekod sebenar) dan gambar dalam `uploads/`.
```
cd UniFind
git init
git add .
git commit -m "UniFind PWA"
git branch -M main
git remote add origin https://github.com/<username>/unifind.git
git push -u origin main
```

## 2. Render
1. render.com -> New -> **Blueprint** -> pilih repo `unifind` (ia baca `render.yaml`).
2. Render buat web service + Persistent Disk (`/var/data`). Disk memerlukan pelan berbayar (Starter).
3. Deploy pertama: `start.py` salin `data/campusback.db` dan `uploads/` ke disk **sekali sahaja**.
   Selepas itu database di disk adalah yang sebenar; deploy seterusnya TIDAK menimpanya.
4. Buka pautan `https://unifind-xxxx.onrender.com`.

## 3. Pasang di telefon
- Android (Chrome): banner "Install UniFind" atau menu ⋮ -> Install app.
- iPhone (Safari): Share -> Add to Home Screen.

## Tanpa disk (Free plan)
Aplikasi tetap berjalan, tetapi data baharu akan hilang setiap kali Render restart/redeploy.
Untuk ujian sahaja: buang bahagian `disk:` dan dua env `CAMPUSBACK_DB` / `CAMPUSBACK_UPLOADS` dalam `render.yaml`.

## Jalankan di komputer (tiada perubahan)
`python server.py` -> http://localhost:8000
