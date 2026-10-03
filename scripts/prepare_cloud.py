import os
import shutil
import urllib.request
import zipfile
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ANDROID = os.path.join(ROOT, "android-template")
APP = os.path.join(ANDROID, "app")
SRC = os.path.join(APP, "src", "main")

# ============================================================
# Ambil konfigurasi dari GitHub Actions
# ============================================================

APP_NAME = os.environ.get("APP_NAME", "HTML to APK")
PACKAGE_NAME = os.environ.get("PACKAGE_NAME", "com.builder.generated")
VERSION_NAME = os.environ.get("VERSION_NAME", "1.0")
VERSION_CODE = os.environ.get("VERSION_CODE", "1")

SOURCE_TYPE = os.environ.get("SOURCE_TYPE", "file")
SOURCE_PATH = os.environ.get("SOURCE_PATH", "")
SOURCE_URL = os.environ.get("SOURCE_URL", "")

# Bersihkan nilai agar aman untuk Gradle / Android
APP_NAME = APP_NAME.strip() or "HTML to APK"
PACKAGE_NAME = PACKAGE_NAME.strip() or "com.builder.generated"
VERSION_NAME = VERSION_NAME.strip() or "1.0"

try:
    VERSION_CODE = int(VERSION_CODE)
except Exception:
    VERSION_CODE = 1

# ============================================================
# Pastikan package name valid
# ============================================================

if not re.fullmatch(
    r"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)+",
    PACKAGE_NAME
):
    print("Package name tidak valid, menggunakan default.")
    PACKAGE_NAME = "com.builder.generated"

# ============================================================
# Buat folder yang diperlukan
# ============================================================

os.makedirs(SRC, exist_ok=True)

ASSETS = os.path.join(SRC, "assets")
WWW = os.path.join(ASSETS, "www")

os.makedirs(ASSETS, exist_ok=True)
os.makedirs(WWW, exist_ok=True)

# ============================================================
# Salin HTML / ZIP ke assets
# ============================================================

source_file = None

if SOURCE_PATH:
    source_file = os.path.join(ROOT, SOURCE_PATH)

if source_file and os.path.isfile(source_file):

    print("Source ditemukan:", source_file)

    if source_file.lower().endswith(".zip"):

        print("Mengekstrak ZIP...")

        # Bersihkan www terlebih dahulu
        if os.path.exists(WWW):
            shutil.rmtree(WWW)

        os.makedirs(WWW, exist_ok=True)

        with zipfile.ZipFile(source_file, "r") as z:
            z.extractall(WWW)

        # Jika ZIP memiliki folder utama,
        # cari index.html secara rekursif.
        index_found = None

        for root, dirs, files in os.walk(WWW):
            if "index.html" in files:
                index_found = os.path.join(root, "index.html")
                break

        if index_found:
            print("index.html ditemukan:", index_found)

        else:
            print("WARNING: index.html tidak ditemukan di ZIP.")

    else:

        print("Menyalin HTML...")

        if os.path.exists(WWW):
            shutil.rmtree(WWW)

        os.makedirs(WWW, exist_ok=True)

        shutil.copy2(
            source_file,
            os.path.join(WWW, "index.html")
        )

elif SOURCE_URL:

    print("Menggunakan URL:", SOURCE_URL)

    url_file = os.path.join(ASSETS, "start_url.txt")

    with open(url_file, "w", encoding="utf-8") as f:
        f.write(SOURCE_URL.strip())

else:

    print("Tidak ada source file atau URL.")
    print("Membuat index.html kosong.")

    with open(
        os.path.join(WWW, "index.html"),
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HTML to APK</title>
</head>
<body>
<h1>HTML to APK</h1>
<p>Source HTML belum tersedia.</p>
</body>
</html>
"""
        )

# ============================================================
# AndroidManifest.xml
# ============================================================

manifest_path = os.path.join(
    SRC,
    "AndroidManifest.xml"
)

if os.path.isfile(manifest_path):

    with open(
        manifest_path,
        "r",
        encoding="utf-8"
    ) as f:
        manifest = f.read()

    manifest = manifest.replace(
        "__PACKAGE_NAME__",
        PACKAGE_NAME
    )

    manifest = manifest.replace(
        "__APP_NAME__",
        APP_NAME
    )

    with open(
        manifest_path,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(manifest)

    print("AndroidManifest.xml diperbarui.")

# ============================================================
# MainActivity.java
# ============================================================

java_path = os.path.join(
    SRC,
    "java",
    "com",
    "builder",
    "generated",
    "MainActivity.java"
)

if os.path.isfile(java_path):

    with open(
        java_path,
        "r",
        encoding="utf-8"
    ) as f:
        java = f.read()

    java = java.replace(
        "__PACKAGE_NAME__",
        PACKAGE_NAME
    )

    with open(
        java_path,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(java)

# ============================================================
# app/build.gradle
# ============================================================

gradle_path = os.path.join(
    APP,
    "build.gradle"
)

if not os.path.isfile(gradle_path):
    raise FileNotFoundError(
        "android-template/app/build.gradle tidak ditemukan."
    )

with open(
    gradle_path,
    "r",
    encoding="utf-8"
) as f:
    gradle = f.read()

# Ganti SEMUA placeholder yang mungkin masih tersisa.
replacements = {
    "__APP_NAME__": APP_NAME,
    "__PACKAGE_NAME__": PACKAGE_NAME,
    "__VERSION_NAME__": VERSION_NAME,
    "__VERSION_CODE__": str(VERSION_CODE),
}

for old, new in replacements.items():
    gradle = gradle.replace(old, new)

with open(
    gradle_path,
    "w",
    encoding="utf-8"
) as f:
    f.write(gradle)

print("app/build.gradle diperbarui.")

# ============================================================
# Verifikasi placeholder
# ============================================================

remaining = []

for file_path in [
    gradle_path,
    manifest_path,
    java_path
]:

    if os.path.isfile(file_path):

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:
            content = f.read()

        for placeholder in [
            "__APP_NAME__",
            "__PACKAGE_NAME__",
            "__VERSION_NAME__",
            "__VERSION_CODE__"
        ]:

            if placeholder in content:
                remaining.append(
                    f"{placeholder} masih ada di {file_path}"
                )

if remaining:

    print("ERROR: Placeholder masih ditemukan:")

    for item in remaining:
        print(item)

    raise RuntimeError(
        "Placeholder Android belum berhasil diganti."
    )

print("")
print("==========================================")
print("ANDROID PROJECT READY")
print("==========================================")
print("App name     :", APP_NAME)
print("Package name :", PACKAGE_NAME)
print("Version name :", VERSION_NAME)
print("Version code :", VERSION_CODE)
print("Source type  :", SOURCE_TYPE)
print("==========================================")
