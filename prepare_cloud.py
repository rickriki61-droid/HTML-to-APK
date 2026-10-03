import os, re, shutil, zipfile
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path.cwd(); TEMPLATE=ROOT/'android-template'; WORK=ROOT/'build-project'; INPUT=ROOT/'input'
app_name=os.environ.get('APP_NAME','').strip(); package_name=os.environ.get('PACKAGE_NAME','').strip(); version_name=os.environ.get('VERSION_NAME','').strip(); version_code=os.environ.get('VERSION_CODE','').strip(); source_type=os.environ.get('SOURCE_TYPE','').strip().lower(); source_path=os.environ.get('SOURCE_PATH','').strip(); source_url=os.environ.get('SOURCE_URL','').strip()
if not app_name or len(app_name)>50: raise SystemExit('Nama aplikasi tidak valid.')
if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+',package_name): raise SystemExit('Nama package tidak valid.')
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+\-]{0,30}',version_name): raise SystemExit('Version name tidak valid.')
if not version_code.isdigit() or int(version_code)<1: raise SystemExit('Version code harus angka positif.')
if source_type not in {'zip','html','url'}: raise SystemExit('Source type harus zip, html, atau url.')
if source_type=='url':
    u=urlparse(source_url)
    if u.scheme not in {'http','https'} or not u.netloc: raise SystemExit('URL harus http/https yang valid.')
if WORK.exists(): shutil.rmtree(WORK)
shutil.copytree(TEMPLATE,WORK)
assets=WORK/'app/src/main/assets/www'; assets.mkdir(parents=True,exist_ok=True)

def safe_extract(zpath,dest):
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name=info.filename.replace('\\','/')
            if name.startswith('/') or name.startswith('../') or '/../' in name: raise SystemExit('ZIP mengandung path berbahaya.')
            target=(dest/name).resolve()
            if not str(target).startswith(str(dest.resolve())+os.sep): raise SystemExit('ZIP mengandung path berbahaya.')
            if info.is_dir(): target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as src,open(target,'wb') as dst: shutil.copyfileobj(src,dst)
def find_index(root):
    exact=root/'index.html'
    if exact.exists(): return exact
    c=list(root.rglob('index.html'))+list(root.rglob('Index.html'))+list(root.rglob('INDEX.HTML'))
    return c[0] if len(c)==1 else None
if source_type=='html':
    src=ROOT/source_path
    if not src.is_file() or src.suffix.lower() not in {'.html','.htm'}: raise SystemExit(f'File HTML tidak ditemukan/valid: {source_path}')
    shutil.copy2(src,assets/'index.html')
elif source_type=='zip':
    src=ROOT/source_path
    if not src.is_file() or src.suffix.lower()!='.zip': raise SystemExit(f'File ZIP tidak ditemukan/valid: {source_path}')
    temp=WORK/'_website_extract'; safe_extract(src,temp); idx=find_index(temp)
    if not idx: raise SystemExit('ZIP harus memiliki index.html.')
    base=idx.parent
    for item in base.iterdir():
        target=assets/item.name
        if target.exists(): shutil.rmtree(target) if target.is_dir() else target.unlink()
        shutil.copytree(item,target) if item.is_dir() else shutil.copy2(item,target)
    shutil.rmtree(temp,ignore_errors=True)
elif source_type=='url':
    (WORK/'app/src/main/assets/start_url.txt').write_text(source_url,encoding='utf-8')
icon=INPUT/'icon.png'
if icon.is_file(): shutil.copy2(icon,WORK/'app/src/main/res/drawable/icon.png')
manifest=WORK/'app/src/main/AndroidManifest.xml'; text=manifest.read_text(encoding='utf-8')
xml_name=app_name.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&apos;')
text=text.replace('__APP_NAME__',xml_name).replace('__PACKAGE_NAME__',package_name).replace('__VERSION_CODE__',version_code).replace('__VERSION_NAME__',version_name); manifest.write_text(text,encoding='utf-8')
gradle=WORK/'app/build.gradle'; text=gradle.read_text(encoding='utf-8').replace('__PACKAGE_NAME__',package_name).replace('__VERSION_CODE__',version_code).replace('__VERSION_NAME__',version_name); gradle.write_text(text,encoding='utf-8')
print('Prepared cloud Android project successfully.')
