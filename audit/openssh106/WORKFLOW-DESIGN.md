# OpenSSH 10.6 audit workflow — implementasi lokal terbatas

**Status: parsial, statis saja.** `.github/workflows/openssh-audit.yml` kini menjalankan satu tes kebijakan PR yang memastikan batas tanpa publikasi. Ia bukan workflow build atau pemindaian OpenSSH dan kelulusannya tidak berarti kandidat atau produk telah diaudit. Tidak ada image kandidat, ekstraksi DB, GSSAPI E2E, atau hasil scan enam target.

## Bagian yang dibuat runnable

- Trigger hanya PR `opened`, `synchronize`, dan `reopened`, dengan filter perubahan pada workflow audit, `audit/openssh106/**`, dan `README.md`.
- Job berjalan hanya untuk PR dari repo yang sama, pada runner gratis publik `ubuntu-24.04`, dengan timeout lima menit.
- Izin workflow hanya `contents: read`; checkout dipin ke SHA penuh dan `persist-credentials: false`.
- Satu-satunya perintah adalah `python3 -I -S audit/openssh106/ci/test_workflow_policy.py -v`. Ini memanggil satu checker standar-library yang eksplisit (bukan unittest discovery), dan tes mengunci event, izin, runner, action pin, same-repository guard serta larangan kemampuan publish/scan/upload. Checker juga memastikan hanya file itu yang ada sebagai file Python di direktori CI.
- Workflow tidak memakai secret, login GHCR, build image, upload artifact, cache, workflow dispatch, atau event publish. Tes lokal statis memeriksa file workflow saja.

Validasi lokal: jalankan `python3 -I -S audit/openssh106/ci/test_workflow_policy.py -v` dan `git diff --check`. Pemeriksaan ini tidak mengeksekusi build atau scan. Keberhasilan tes kebijakan hanya menunjukkan bahwa workflow tetap berada dalam batas statis yang ditetapkan.

## Mengapa enam target belum dapat dijalankan

1. `audit/openssh106/package/Dockerfile` menggunakan `debian:13.7-slim` tanpa digest immutable.
2. `build.sh` menambahkan source snapshot tetapi tidak secara eksplisit menonaktifkan seluruh source APT bawaan image. Karena itu resolusi dependensi belum terbukti terbatas pada snapshot terkunci.
3. Builder saat ini menyalin dan mencoba memasang semua `.deb` biasa yang dihasilkan, bukan membatasi paket runtime menjadi `openssh-client` dan `openssh-common`.
4. Manifest sumber hanya mengunci hash; source archive dan delta patch yang dibutuhkan sebagai input staging tidak tersedia lengkap dalam checkout ini. Verifikasi SecureApt/source chain, package-index hash, dan dependency closure belum diuji end-to-end.
5. Belum ada orkestrasi yang secara otoritatif mengikat enam pasangan Node/arsitektur ke source, base digest, paket, root/config digest, dan hasil scan yang cocok.
6. `run-gssapi-e2e.sh` dan fixture hanya pernah diperiksa sintaksnya; tidak ada E2E native `amd64`/`arm64` yang berhasil direkam.
7. Tidak ada pemeriksaan runtime kapasitas runner sebelum ekstraksi/build. Workspace lokal `/run` memiliki sekitar 1,69 GB ruang, kurang dari kebutuhan minimum extractor 3.221.291.008 byte. Tidak ada DB segar diekstrak dalam pekerjaan ini.

Sampai kekurangan itu diselesaikan, bagian workflow berikutnya harus tetap tertahan. Jangan menambah job yang menghasilkan status hijau untuk enam target tanpa bukti digest-bound, jangan memakai fallback runner berbayar, dan jangan mengunggah image, DB, SBOM, laporan, atau arsip OCI.

## Bukti lokal yang berlaku

Hash file extractor/test saat ini diverifikasi sebagai:

- `audit/openssh106/db_snapshot.py`: `0903ba0c19a4dfbda87dcee430d34385e250c8a47dbc973cb57aa53ab47fdfed`
- `audit/openssh106/test_db_snapshot.py`: `fb8901be68531c8713057dd0694fcc32712169f6210f7594c84c26faae5b80c0`

Catatan hasil yang disediakan untuk pasangan persis tersebut melaporkan pemeriksaan statis SECURITY/VALIDATOR lulus dan 57/57 tes sintetis; log suite `/tmp/openssh-validator/suite-0903-fb890.log` memiliki SHA-256 `76f4f06085632021189ba7c0cee09a4ee43ddb4b45cf4b79dadbf62f5a709ff0`. File extractor/test tidak diubah atau dijalankan ulang di sini. Hasil sintetis ini bukan hasil fetch database live, build, atau pemindaian kandidat.

Workflow produksi `.github/workflows/publish.yml`, Dockerfile produksi, dan release gate tetap tidak berubah. Tidak ada GitHub PAT, kredensial akun, atau secret yang dipakai untuk perubahan lokal ini; pemeriksaan GHCR publik sebelumnya menggunakan token pull anonim yang hanya dikirim ke `ghcr.io` dan tidak diteruskan ke CDN. Tidak ada run CI, build image, pengunduhan/ekstraksi DB penuh, upload, push, PR, atau publikasi.


## Bukti tambahan, bukan scan

Tes kebijakan statis yang ditambahkan lulus 9/9 secara lokal dan `git diff --check` bersih. Untuk pasangan extractor/test yang hash-nya dicantumkan di atas, bukti terpisah menunjukkan GET `Range: bytes=0-0` terhadap blob DB Trivy yang dipin berhasil lewat redirect allowlist: HTTP 206, `Content-Range` total 136.143.534 byte, satu byte dibaca, manifest/layer digest cocok dengan lock, dan hash stabil sebelum/sesudah. CDN hanya menerima header `Range` dan `User-Agent`, tanpa header kredensial. Ini tidak menunjukkan blob penuh diunduh, DB diekstrak, atau temuan CVE dipindai.
