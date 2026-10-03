# Cloud Gateway

Server ini menjadi perantara antara browser dan GitHub Actions. **GitHub Token hanya berada di environment server.**

## Jalankan sendiri

```bash
npm install
GITHUB_OWNER=akun GITHUB_REPO=repo GITHUB_TOKEN=TOKEN npm start
```

Health check:

```text
GET /api/health
```

Build:

```text
POST /api/build
```

Field form: `app_name`, `package_name`, `version_name`, `version_code`, `source_type`, optional `source_url`, file `source`, optional file `icon`.
