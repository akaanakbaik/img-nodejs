# Triage Debian HIGH/CRITICAL — 2026-10-23

## Cakupan dan hasil

Triage ini memakai `package-cve-audit.json`, `package-paths.json`, raw Trivy image report, dan Trivy CycloneDX SBOM dari `/workspace/img-nodejs-final-evidence`. **Setiap pasangan binary-package/CVE dipertahankan sebagai satu record**; tidak ada threshold yang diturunkan, suppression, penghapusan paket, atau perubahan base image. Semua enam kandidat (Node 22/24/26 × amd64/arm64) memiliki **339/339 pasangan**: **333 HIGH + 6 CRITICAL**, 59 binary packages. Inventory dpkg memuat **60 paket** (59 paket yang memiliki finding + Brotli); suffix multiarch `:amd64`/`:arm64` dinormalisasi hanya untuk pemetaan, sedangkan nama dan arsitektur asli tetap disimpan. Status scanner: **190 affected**, **148 fix_deferred**, **1 will_not_fix**; **0** record memiliki `fixed_version`.

| Kandidat | Pasangan | HIGH | CRITICAL | affected | fix_deferred | will_not_fix | paket inventory | paket path terpetakan | punya SBOM ref |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| nodejs_22-amd64 | 339 | 333 | 6 | 190 | 148 | 1 | 60 | 59 | 339 |
| nodejs_22-arm64 | 339 | 333 | 6 | 190 | 148 | 1 | 60 | 59 | 339 |
| nodejs_24-amd64 | 339 | 333 | 6 | 190 | 148 | 1 | 60 | 59 | 339 |
| nodejs_24-arm64 | 339 | 333 | 6 | 190 | 148 | 1 | 60 | 59 | 339 |
| nodejs_26-amd64 | 339 | 333 | 6 | 190 | 148 | 1 | 60 | 59 | 339 |
| nodejs_26-arm64 | 339 | 333 | 6 | 190 | 148 | 1 | 60 | 59 | 339 |

`sbom_refs` adalah identitas komponen; SBOM Trivy tidak menyediakan path file. Path diambil dari bukti dpkg `package-paths.json`; 339 pasangan kini terpetakan karena nama evidence memakai suffix arsitektur dpkg. `source_package`/`source_version` diambil dari `Packages[].SrcName`/`SrcVersion` raw scan, bukan fallback nama binary. Mapping audit, SBOM, candidate image ID, versi path, dan raw scan divalidasi fail-closed; setiap output menyimpan SHA-256 evidence. Candidate APT, bila diberikan melalui inventory vendor, dilabeli `apt_candidate` dan **bukan bukti bahwa versi tersebut sudah fixed**.

## Rekomendasi aman

1. **Tidak ada vendor fix yang dapat dinyatakan tersedia dari evidence ini**: semua `fixed_version` kosong dan evidence tidak memuat apt candidate. Jangan mengganti base Debian secara luas, menghapus paket/tool, menurunkan threshold, atau men-suppress findings.
2. Untuk setiap package yang kemudian memiliki versi Debian resmi, lakukan hanya upgrade terarah dari repositori Debian 13 yang ditandatangani: `apt-get update` lalu `apt-get install --only-upgrade <semua binary package dari source package terkait>`, kemudian rebuild dan rescan kedua arsitektur. Verifikasi versi terpasang terhadap versi fix DSA/Tracker dan jalankan smoke/runtime tests.
3. Untuk `fix_deferred`/`affected` tanpa versi fix, pertahankan sebagai **open/blocking** dan pantau Debian Security Tracker/DSA. `will_not_fix` bukan alasan untuk mengabaikan; minta penilaian exposure dan mitigasi runtime terukur secara terpisah.
4. Karena findings mencakup kelompok besar (mis. `linux-libc-dev`, FFmpeg/libav*, Python 3.13, systemd/util-linux), jangan melakukan source rebuild atau upgrade upstream besar sebagai “fix”; Debian sendiri menganjurkan backport minimal dan menjaga ABI/API. Candidate fix harus dibuktikan dari apt metadata/DSA, bukan dari asumsi versi terbaru.

## Keputusan per kelompok source

Seluruh **19 kelompok** berikut tetap **open/blocking**, bukan diterima atau diabaikan. Jumlah adalah pasangan paket/CVE per image, bukan CVE unik. Path adalah ownership, bukan bukti fungsi rentan terpanggil. Untuk setiap perbaikan vendor berikutnya, semua binary package terkait harus di-upgrade bersama, lalu diuji pada kedua arsitektur.

| Source | Pasangan HIGH/CRITICAL | Tindakan aman berikutnya |
|---|---:|---|
| acl | 1 | Pertahankan library; verifikasi ABI dan operasi filesystem bila paket vendor fixed tersedia. |
| cjson | 5 | Perbaiki melalui paket vendor; uji consumer parser dengan input benign sebelum menerima perubahan. |
| cups | 2 | Jangan menganggap library client sebagai daemon aktif; perbaiki library tanpa menghapus dependency Yolks. |
| curl | 6 | Upgrade curl dan kedua varian libcurl secara konsisten; ulangi HTTPS serta probe decoding Brotli. |
| ffmpeg | 144 | Pertahankan ffmpeg dan library libav/libsw/libpostproc terkait; tunggu backport konsisten, lalu uji decode/encode fixture benign. |
| libsndfile | 1 | Uji parser audio benign dan ABI setelah backport vendor, tanpa membuang library. |
| libx11 | 3 | Perbarui libx11-6, libx11-data, dan libx11-xcb1 bersama; linkage tidak membuktikan server X berjalan. |
| libxml2 | 8, termasuk 1 CRITICAL | Prioritaskan CVE-2026-6653; perlu versi vendor fixed dan regresi parser, bukan penggantian .so manual. |
| libxrender | 1 | Pertahankan library dan validasi linkage/ABI saat vendor menyediakan fix. |
| libxtst | 1 | Pertahankan library dan validasi linkage/ABI saat vendor menyediakan fix. |
| linux | 66, termasuk 1 CRITICAL | Temuan terikat ke **linux-libc-dev (headers)**, bukan bukti versi kernel host. Prioritaskan CVE-2026-93221; pertahankan gate tanpa mengklaim host sudah rentan atau fixed. |
| lmdb | 5, termasuk 3 CRITICAL | Prioritaskan CVE-2019-16224/16225/16227; perlu patch paket tervalidasi dan regresi database. Jangan menafsirkan `will_not_fix` sebagai exception. |
| ncurses | 4 | Perbarui library dan database terminal bersama, lalu uji tooling CLI/terminal. |
| openssh | 6, termasuk 1 CRITICAL | Prioritaskan CVE-2026-60002 pada openssh-client; pertahankan fungsi git-over-SSH, jangan mengklaim sshd berjalan. |
| perl | 4 | Perbarui interpreter dan modul standard sebagai set vendor; uji interpreter serta tooling yang bergantung padanya. |
| python3.13 | 35 | Perbarui interpreter, stdlib, dev, dan minimal bersama; uji interpreter serta build native module. |
| systemd | 9 | Perbarui libsystemd/libudev/NSS/PAM dan paket terkait bersama; paket terpasang tidak membuktikan systemd sebagai PID 1 (image memakai Tini). |
| tiff | 2 | Perlu backport parser vendor serta fixture gambar benign, tanpa mengganti library secara opaque. |
| util-linux | 36 | Pertahankan tooling dan ABI libmount/libblkid/libuuid; uji user, HOME, working directory, filesystem, dan startup non-root. |

Schema JSON v3 menyimpan seluruh path/hash ELF sekali pada `path_inventory`; setiap finding memakai `path_inventory_ref`. Metadata kandidat lengkap (manifest digest, image ID, arsitektur) tidak digantikan nama pendek kandidat. Bukti APT baru dicatat terpisah dan **candidate version bukan bukti CVE fixed**.

## Sumber Debian resmi

- [Debian Security Tracker](https://security-tracker.debian.org/) — data berasal dari database Security Team; menyediakan status stable dan JSON tracker.
- [Debian Security FAQ](https://www.debian.org/security/faq) — stable security fixes dibackport; upgrade dengan `apt-get update` dan package-specific `apt-get install`; semua binary package dari source package terkait perlu diperbarui; hindari perubahan upstream besar/ABI.
- [Debian trixie package index](https://packages.debian.org/stable/) — indeks resmi suite stable/trixie dan `trixie-security`/`trixie-updates` links.

Tanggal, versi scanner, dan digest tetap dapat diaudit melalui `scanner-metadata.json` serta `source`/`evidence_sha256` pada tiap JSON.

## Reproduksi CI

Utility reusable ada di `scripts/triage_groups.py`; inventory vendor ada di `scripts/vendor_package_inventory.py`; test di `scripts/test_triage_groups.py` dan `scripts/test_vendor_package_inventory.py`. Contoh per candidate (nama SBOM mengikuti evidence):

```sh
python3 scripts/triage_groups.py \
  --audit /workspace/img-nodejs-final-evidence/reports-22-amd64/package-cve-audit.json \
  --paths /workspace/img-nodejs-final-evidence/reports-22-amd64/package-paths.json \
  --sbom /workspace/img-nodejs-final-evidence/reports-22-amd64/trivy-sbom-22-amd64.json \
  --scan /workspace/img-nodejs-final-evidence/reports-22-amd64/trivy-image-22-amd64.json \
  --candidate nodejs_22-amd64 \
  --output docs/security/2026-10-23-triage/debian-22-amd64.json
```

CI dapat mengulang command tersebut untuk enam direktori `reports-{22,24,26}-{amd64,arm64}` dan, bila tersedia, menambahkan `--apt-evidence <JSON>` dalam schema `{"packages":[{"package":"...","source_package":"...","candidate":"..."}],"candidate":{...}}`. Utility tidak mengubah audit atau kebijakan gate. Jalankan test dengan `PYTHONPATH=scripts python3 -m unittest discover -s scripts -p 'test_*triage*.py'` dan `PYTHONPATH=scripts python3 -m unittest discover -s scripts -p 'test_vendor*.py'`.
