# img-nodejs

Runtime Node.js berbasis [Parkervcp Yolks](https://github.com/parkervcp/yolks) untuk Egg Pterodactyl, dengan pemeriksaan patch exact dan pemindaian sebelum publikasi. Target: Linux `amd64` dan `arm64`; bukan Windows container atau ARM 32-bit. Repo ini tidak mengompilasi atau mem-backport Node.js. Library Brotli OS dibangun sebagai paket Debian lokal dari source upstream fixed; ini bukan paket keamanan resmi Debian.

## Patch keamanan Oktober 2026

[Rilis keamanan resmi 21 Oktober 2026](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases) memperbaiki **CVE-2026-111497**, out-of-bounds write pada decoder Brotli yang dapat menyebabkan RCE, serta isu DNS, TLS, permission model dan dependensi lainnya. Versi minimum perbaikannya adalah **22.23.4, 24.22.1, dan 26.12.1**. Versi EOL tidak mempunyai patch resmi untuk insiden ini dan tidak boleh dianggap aman.

| Major/tag `nodejs_N` | Patch exact pada manifest | Status 23 Oktober 2026 | Kebijakan workflow |
|---|---|---|---|
| 18 | 18.20.8 | EOL | Verifikasi dan laporan saja |
| 19 | 19.9.0 | EOL | Verifikasi dan laporan saja |
| 20 | 20.20.2 | EOL | Verifikasi dan laporan saja |
| 21 | 21.7.3 | EOL | Verifikasi dan laporan saja |
| 22 | 22.23.4 | LTS | Kandidat publikasi, wajib lolos scan |
| 23 | 23.11.1 | EOL | Verifikasi dan laporan saja |
| 24 | 24.22.1 | LTS | Kandidat publikasi, wajib lolos scan |
| 25 | 25.9.0 | EOL | Verifikasi dan laporan saja |
| 26 | 26.12.1 | Current | Kandidat publikasi, wajib lolos scan |

Versi bersumber dari [indeks rilis resmi](https://nodejs.org/dist/index.json) dan [status dukungan resmi](https://nodejs.org/en/about/previous-releases), dicatat pada [`versions.json`](versions.json). Jika ada rilis baru, pemeriksaan `--check` akan gagal sampai manifest diperbarui dan diperiksa; workflow tidak diam-diam memakai patch lama. Tag lama di GHCR **tidak dihapus atau diperbarui** oleh perubahan source saja. Lihat [hasil pemeriksaan keamanan](SECURITY-REVIEW.md) sebelum deployment.

**Patch RCE bukan berarti seluruh image bebas kerentanan.** Pemindaian upstream saat pembaruan ini menemukan HIGH/CRITICAL pada paket OS/tool tambahan. Gerbang publikasi sengaja gagal selama temuan itu masih ada; tidak ada pengecualian diam-diam atau `--ignore-unfixed`. Hasil scanner adalah temuan paket, bukan bukti setiap CVE dapat dieksploitasi pada aplikasi Anda. Uji Brotli adalah uji fungsional dan penolakan input invalid, bukan pembuktian bahwa exploit RCE mustahil.

Baseline lama menemukan **CVE-2026-111497 pada Debian `libbrotli1 1.1.0-2+b7`**, severity `UNKNOWN`, dan probe HTTP aman membuktikan `curl --compressed` mencapai decoder sistem. Dockerfile remediasi membangun **Brotli upstream 1.1.1** sebagai paket Debian asli `1.1.1-0img1~deb13u1`, dengan source/checksum dipin, pengujian CMake/Python, serta pemeriksaan SONAME dan simbol ABI. Paket dan metadata dpkg tidak disamarkan atau ditimpa manual. Source dan packaging dapat diperiksa di [`security/brotli-source.json`](security/brotli-source.json).

[Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-111497) masih mencatat status vendor unfixed. Scanner dapat tetap menandai paket custom meskipun source fixed; **tidak ada pengecualian dibuat dan gate CVE tetap menolak semua severity**. Node upstream menggunakan Brotli bundled yang berbeda dari library OS. Hasil final dan blocker aktual ada pada [review keamanan](SECURITY-REVIEW.md); jangan menganggap keberhasilan build sebagai izin rilis.

## Verifikasi dan publikasi

Workflow [`.github/workflows/publish.yml`](.github/workflows/publish.yml) mempertahankan jadwal Senin 04:23 UTC, juga berjalan pada PR/perubahan source dan dapat dijalankan manual. Tidak ada akses tulis registry dari PR atau branch selain `main`. Push dan jadwal hanya melakukan audit: publikasi mensyaratkan `workflow_dispatch` pada `main`, input boolean `publish=true`, persetujuan pemilik, dan seluruh gate supported lulus.

1. Validasi pemetaan Egg, unit test, dan kecocokan seluruh patch terhadap indeks resmi.
2. Resolve digest immutable image dasar, lalu build kandidat pada runner native `amd64` dan `arm64`.
3. Build-time verifier menolak patch/major yang salah atau di bawah minimum CVE; jalankan Brotli synchronous/streaming round-trip dan input invalid yang aman.
4. Smoke test user non-root `container`, `/home/container`, `HOME`, entrypoint Tini, fixture startup Egg, instalasi/uninstall paket npm lokal tanpa jaringan, kompilasi TypeScript, serta tersedianya curl/git/ffmpeg. Ini bukan uji integrasi Panel/Wings live.
5. Trivy versi tetap dengan verifikasi checksum memindai kerentanan OS/library, secret dan misconfiguration repo, dan menghasilkan SBOM CycloneDX. Laporan, snapshot database scanner, digest kandidat, bukti linkage/consumer, korelasi paket/path/CVE/SBOM dan hash ELF paket OS tetap diunggah jika gerbang gagal. CVE-2026-111497 pada severity apa pun, temuan HIGH/CRITICAL atau kegagalan scanner menahan publikasi.
6. Hanya image kandidat yang sudah diuji dan lolos gerbang yang disimpan, dipush, dan digabung menjadi manifest multi-platform berdasarkan digest, tanpa rebuild setelah pengujian. Image ID dan arsitektur scanner/SBOM harus cocok dengan kandidat; checksum tar dan image ID dicek ulang setelah artifact dimuat kembali. SBOM tersedia sebagai artifact; workflow ini tidak mengklaim signature keyless atau provenance attestation yang belum dibuat.

Semua major tetap tercatat untuk kompatibilitas dan audit. Publikasi EOL dinonaktifkan tanpa opsi override; matrix publikasi hanya memuat 22/24/26 untuk kedua arsitektur. Temuan atau error audit EOL tetap terlihat di job/artifact, tetapi tidak menjadi prasyarat publikasi supported (`continue-on-error` hanya untuk EOL). Semua gerbang keamanan kandidat supported tetap hard-fail. Untuk produksi, migrasikan ke line LTS yang didukung; jangan memilih EOL hanya karena versi terakhirnya cocok.

## Menghubungkan ke Egg Pterodactyl

[`egg/docker_images.json`](egg/docker_images.json) hanya isi objek `docker_images`, bukan Egg lengkap. Nama dan tag dipertahankan agar kompatibel dengan Egg yang sudah ada. Label `Node.js 18/19/20/21/23/25` adalah legacy EOL, bukan pilihan aman.

Cadangkan/ekspor Egg, ganti hanya objek `docker_images`, simpan, dan pilih runtime yang masih didukung. Audit ekspor sebelum import:

```sh
python3 scripts/validate_egg.py
python3 scripts/validate_egg.py --egg /path/ke/egg-export.json
```

Pastikan major installer sama dengan runtime untuk modul native; jangan memakai installer Node 14 yang sudah EOL. Jangan menyisipkan token ke URL Git. Matikan auto-update aplikasi secara default, deklarasikan seluruh placeholder startup, dan normalisasi skrip ke LF. Validator hanya memeriksa pola dasar, bukan audit aplikasi lengkap.

Setelah **publikasi benar-benar berhasil**, pull image baru pada node/Wings, periksa digest dan `node --version`, lalu recreate/redeploy server sesuai prosedur panel. Restart saja dapat tetap memakai image/cache lama. Migrasi major mungkin memerlukan instalasi ulang dependensi native. Repo tidak mengubah Panel, Wings, Egg aktif, atau server produksi secara otomatis.

## Build dan validasi lokal

Default Dockerfile dipin ke digest upstream Node 24 yang diperiksa. Gunakan host native arsitektur target. Untuk major lain, tentukan `BASE_IMAGE` digest, `NODE_MAJOR`, dan `NODE_PATCH` bersama-sama; arg lama `NODE_VERSION` tidak dipakai karena bertabrakan dengan environment image upstream.

```sh
python3 scripts/resolve_versions.py --check
node scripts/test_verify_runtime.js
python3 scripts/test_resolve_versions.py
python3 scripts/validate_egg.py

docker build -t local/img-nodejs:nodejs_24 .
bash scripts/smoke_test_image.sh 24 amd64 local/img-nodejs:nodejs_24 24.22.1

docker run --rm --env EXPECTED_NODE_VERSION=24.22.1 \
  local/img-nodejs:nodejs_24 node /usr/local/share/image-security/verify_runtime.js
```

Smoke test juga menerima `CONTAINER_ENGINE`, `CONTAINER_NETWORK`, dan `RUN_ARGS` untuk lingkungan pengujian Podman. Verifikasi patch runtime berdasarkan rilis resmi, bukan hanya `process.versions.brotli`: vendor dapat mem-backport fix tanpa mengubah nomor library tersebut.
