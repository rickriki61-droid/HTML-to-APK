import express from 'express';
import cors from 'cors';
import multer from 'multer';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';

const app = express();
const port = Number(process.env.PORT || 3000);
const owner = process.env.GITHUB_OWNER;
const repo = process.env.GITHUB_REPO;
const token = process.env.GITHUB_TOKEN;
const workflow = process.env.GITHUB_WORKFLOW || 'build-apk.yml';
const maxUpload = 60 * 1024 * 1024;
const upload = multer({ dest: '/tmp/html-apk-builder', limits: { fileSize: maxUpload } });

app.use(cors({ origin: process.env.CORS_ORIGIN || '*', methods: ['GET','POST','OPTIONS'] }));
app.use(express.json({ limit: '1mb' }));

function assertConfig() {
  if (!owner || !repo || !token) throw new Error('Cloud builder belum dikonfigurasi oleh admin.');
}
function ghHeaders(json=false) {
  const h = { 'Accept':'application/vnd.github+json', 'Authorization':`Bearer ${token}`, 'X-GitHub-Api-Version':'2022-11-28' };
  if (json) h['Content-Type']='application/json';
  return h;
}
async function gh(pathname, options={}) {
  const r = await fetch(`https://api.github.com${pathname}`, { ...options, headers: { ...ghHeaders(Boolean(options.body)), ...(options.headers||{}) } });
  const text = await r.text();
  let data; try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!r.ok) throw new Error(data?.message || `GitHub API ${r.status}`);
  return data;
}
function b64(buf) { return Buffer.from(buf).toString('base64'); }
function safeName(v, fallback='app') { return String(v||fallback).replace(/[^A-Za-z0-9._-]/g,'_').slice(0,80) || fallback; }
function validPackage(v) { return /^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$/.test(v); }
function validVersion(v) { return /^[A-Za-z0-9][A-Za-z0-9._+\-]{0,30}$/.test(v); }

async function defaultBranch() {
  const r = await gh(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`);
  return r.default_branch || 'main';
}
async function putFile(filePath, buffer, message) {
  let sha;
  try { sha = (await gh(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${filePath}`)).sha; } catch (e) { if (!String(e.message).toLowerCase().includes('not found')) throw e; }
  const body = { message, content: b64(buffer) }; if (sha) body.sha = sha;
  return gh(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${filePath}`, { method:'PUT', body:JSON.stringify(body) });
}
async function deleteFile(filePath, message) {
  try {
    const old = await gh(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${filePath}`);
    await gh(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${filePath}`, { method:'DELETE', body:JSON.stringify({ message, sha:old.sha }) });
  } catch {}
}
async function dispatch(branch, inputs) {
  return gh(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/actions/workflows/${encodeURIComponent(workflow)}/dispatches`, {
    method:'POST', body:JSON.stringify({ ref:branch, inputs })
  });
}
async function findRun(since) {
  for (let i=0;i<30;i++) {
    const data = await gh(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/actions/workflows/${encodeURIComponent(workflow)}/runs?event=workflow_dispatch&per_page=20`);
    const runs = (data.workflow_runs||[]).filter(r => new Date(r.created_at).getTime() >= since - 15000).sort((a,b)=>new Date(b.created_at)-new Date(a.created_at));
    if (runs.length) return runs[0];
    await new Promise(r=>setTimeout(r,2000));
  }
  throw new Error('GitHub Actions run tidak ditemukan.');
}
async function waitRun(id) {
  for (let i=0;i<180;i++) {
    const r = await gh(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/actions/runs/${id}`);
    if (r.status === 'completed') return r;
    await new Promise(x=>setTimeout(x,3000));
  }
  throw new Error('Build cloud timeout.');
}
async function getReleaseAsset(tag) {
  const rel = await gh(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/releases/tags/${encodeURIComponent(tag)}`);
  const asset = (rel.assets||[]).find(a => a.name.toLowerCase().endsWith('.apk'));
  if (!asset) throw new Error('APK hasil build tidak ditemukan.');
  const r = await fetch(asset.url, { headers:{...ghHeaders(), 'Accept':'application/octet-stream'} });
  if (!r.ok) throw new Error('Gagal mengambil APK dari GitHub.');
  return { asset, buffer:Buffer.from(await r.arrayBuffer()) };
}

app.get('/api/health', async (_req,res) => {
  try { assertConfig(); res.json({ ok:true, service:'html-apk-builder-gateway' }); }
  catch(e) { res.status(503).json({ ok:false, error:e.message }); }
});

app.post('/api/build', upload.fields([{ name:'source', maxCount:1 }, { name:'icon', maxCount:1 }]), async (req,res) => {
  const uploaded = [...(req.files?.source||[]), ...(req.files?.icon||[])];
  try {
    assertConfig();
    const appName=String(req.body.app_name||'').trim();
    const packageName=String(req.body.package_name||'').trim();
    const versionName=String(req.body.version_name||'1.0').trim();
    const versionCode=String(req.body.version_code||'1').trim();
    const sourceType=String(req.body.source_type||'').trim().toLowerCase();
    const sourceUrl=String(req.body.source_url||'').trim();
    if (!appName || appName.length>50) throw new Error('Nama aplikasi tidak valid.');
    if (!validPackage(packageName)) throw new Error('Nama package tidak valid.');
    if (!validVersion(versionName)) throw new Error('Version name tidak valid.');
    if (!/^\d+$/.test(versionCode) || Number(versionCode)<1) throw new Error('Version code tidak valid.');
    if (!['html','zip','url'].includes(sourceType)) throw new Error('Source type tidak valid.');
    if (sourceType !== 'url' && !req.files?.source?.[0]) throw new Error('File sumber belum dipilih.');
    if (sourceType === 'url' && !/^https?:\/\/[^\s]+$/i.test(sourceUrl)) throw new Error('URL website tidak valid.');

    const buildId = `${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
    const source = req.files?.source?.[0];
    const icon = req.files?.icon?.[0];
    const sourcePath = source ? `input/build-${buildId}-${safeName(source.originalname)}` : '';
    const iconPath = icon ? `input/build-${buildId}-icon.png` : '';
    const branch = await defaultBranch();

    if (source) await putFile(sourcePath, await fs.readFile(source.path), `Cloud Builder: source ${buildId}`);
    if (icon) await putFile(iconPath, await fs.readFile(icon.path), `Cloud Builder: icon ${buildId}`);

    const started=Date.now();
    await dispatch(branch, { app_name:appName, package_name:packageName, version_name:versionName, version_code:versionCode, source_type:sourceType, source_path:sourcePath || 'input/unused.txt', source_url:sourceUrl, build_id:buildId, icon_path:iconPath });
    const run=await findRun(started);
    const done=await waitRun(run.id);
    if (done.conclusion !== 'success') throw new Error(`Build gagal (${done.conclusion||'unknown'}).`);
    const result=await getReleaseAsset(`apk-build-${buildId}`);
    res.setHeader('Content-Type','application/vnd.android.package-archive');
    res.setHeader('Content-Disposition',`attachment; filename="${safeName(appName,'app')}.apk"`);
    res.setHeader('Content-Length',String(result.buffer.length));
    res.send(result.buffer);
  } catch(e) {
    res.status(400).json({ ok:false, error:e.message || 'Build gagal.' });
  } finally {
    for (const f of uploaded) { try { await fs.unlink(f.path); } catch {} }
  }
});

app.listen(port, ()=>console.log(`HTML APK Builder Gateway listening on :${port}`));
