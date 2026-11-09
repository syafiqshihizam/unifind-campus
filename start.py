"""Production entry point for hosting (Render etc.).

First run only: if the persistent disk is empty, copy the bundled database and photos
(data/campusback.db and uploads/) onto it. After that the disk copy is the live database
and is NEVER overwritten by a redeploy.
Then start the unchanged UniFind server.
"""
import os
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = Path(os.environ.get('CAMPUSBACK_DB', BASE / 'data' / 'campusback.db'))
UPLOADS = Path(os.environ.get('CAMPUSBACK_UPLOADS', BASE / 'uploads'))
SEED_DB = BASE / 'data' / 'campusback.db'
SEED_UPLOADS = BASE / 'uploads'


def bootstrap():
    DB.parent.mkdir(parents=True, exist_ok=True)
    UPLOADS.mkdir(parents=True, exist_ok=True)
    if DB.resolve() != SEED_DB.resolve():
        if not DB.exists() and SEED_DB.exists():
            shutil.copy2(SEED_DB, DB)
            print(f'[start] First run: copied bundled database to {DB}')
        if SEED_UPLOADS.exists():
            for f in SEED_UPLOADS.iterdir():
                target = UPLOADS / f.name
                if f.is_file() and f.name != '.gitkeep' and not target.exists():
                    shutil.copy2(f, target)


if __name__ == '__main__':
    bootstrap()
    import server
    server.run(port=int(os.environ.get('PORT', 8000)), host='0.0.0.0')
