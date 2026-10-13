# img-nodejs

Image runtime Node.js berbasis [Parkervcp Yolks](https://github.com/parkervcp/yolks), dipublikasikan ke GitHub Container Registry (GHCR) agar dapat dipilih dari **Egg Pterodactyl**. Image ini hanya meneruskan major Node.js upstream yang sama; Node.js tidak dikompilasi atau dimodifikasi oleh repo ini.

## Tag yang tersedia

| Pilihan di Egg | Image |
|---|---|
| Node.js 18 | `ghcr.io/akaanakbaik/img-nodejs:nodejs_18` |
| Node.js 19 | `ghcr.io/akaanakbaik/img-nodejs:nodejs_19` |
| Node.js 20 | `ghcr.io/akaanakbaik/img-nodejs:nodejs_20` |
| Node.js 21 | `ghcr.io/akaanakbaik/img-nodejs:nodejs_21` |
| Node.js 22 | `ghcr.io/akaanakbaik/img-nodejs:nodejs_22` |
| Node.js 23 | `ghcr.io/akaanakbaik/img-nodejs:nodejs_23` |
| Node.js 24 | `ghcr.io/akaanakbaik/img-nodejs:nodejs_24` |
| Node.js 25 | `ghcr.io/akaanakbaik/img-nodejs:nodejs_25` |
| Node.js 26 | `ghcr.io/akaanakbaik/img-nodejs:nodejs_26` |

Setiap tag dirancang sebagai **manifest multi-platform Linux `amd64` + `arm64`**. Pada `docker pull`, Docker memilih varian yang cocok dengan arsitektur host secara otomatis; Egg tidak perlu tag terpisah per arsitektur. Ini mencakup host Linux 64-bit yang didukung Docker/Wings. Ini **bukan** image Windows-container dan tidak menjanjikan dukungan `arm/v7`, `riscv64`, `s390x`, atau OS lain. Pterodactyl/Wings tetap memerlukan Docker-compatible host, akses jaringan ke GHCR, dan konfigurasi node yang benar.

Tag mayor bersifat mutable: job terjadwal membangun ulang tag yang sama dari tag upstream yang bersesuaian, sehingga digest dapat berubah. Untuk deployment yang harus reproducible, pin digest yang sudah diverifikasi. Periksa siklus dukungan Node.js pada [halaman rilis resmi](https://nodejs.org/en/about/previous-releases); utamakan major LTS yang masih didukung. Tag EOL disediakan hanya untuk kompatibilitas aplikasi lama dan tidak menerima patch keamanan upstream.

## Memasang image pada Egg Pterodactyl

File [`egg/docker_images.json`](egg/docker_images.json) adalah **isi objek `docker_images` saja**, bukan Egg lengkap. Di Panel, sebagai administrator:

1. Buka **Nests → Egg** yang ingin diperbarui dan ekspor/cadangkan Egg terlebih dahulu.
2. Ganti hanya nilai objek `docker_images` dengan isi file tersebut. Jangan mengganti seluruh JSON Egg dengan file snippet ini dan jangan menghapus field lain.
3. Simpan perubahan, lalu pilih label **Node.js N** pada konfigurasi Docker image server. Reinstall/redeploy aplikasi bila dependensi perlu dipasang ulang; restart saja tidak selalu membangun ulang `node_modules`.
4. Pastikan node Pterodactyl dapat menarik image GHCR publik. Contoh:

   ```sh
   docker pull ghcr.io/akaanakbaik/img-nodejs:nodejs_24
   docker run --rm ghcr.io/akaanakbaik/img-nodejs:nodejs_24 \
     /bin/bash -lc 'node --version && npm --version'
   ```

Validator metadata dan audit Egg disertakan:

```sh
python3 scripts/validate_egg.py
python3 scripts/validate_egg.py --egg /path/ke/egg-export.json
```

### Catatan penting untuk Egg pada lampiran

Lampiran yang diaudit berformat `PTDL_v2`; peta saat ini menunjuk langsung ke Parkervcp Yolks untuk Node 18–25 dan belum mencantumkan 26. Peta repo ini memberi nama pilihan yang lebih jelas dan mencakup 18–26. **Penggantian peta saja tidak memperbaiki bagian Egg lain.** Sebelum memakai ekspor tersebut di produksi, tinjau hal-hal ini:

- Startup merujuk `{{AUTO_UPDATE}}`, tetapi variabel itu belum dideklarasikan. Deklarasikan dengan default `0` (nonaktif), atau hapus referensinya. Deklarasikan juga variabel lain yang memang ingin digunakan (`NODE_PACKAGES`, `UNNODE_PACKAGES`, dan `CUSTOM_ENVIRONMENT_VARIABLES`); referensi installer ke `USER_UPLOAD` juga perlu dideklarasikan atau dirapikan.
- `AUTO_UPDATE=1` menjalankan `git pull` saat server start dan dapat mengeksekusi kode remote terbaru. Biarkan nonaktif secara default; aktifkan hanya untuk repo/branch tepercaya dan pahami konsekuensinya. Untuk rilis yang dapat diulang, pin aplikasi ke tag/commit, bukan branch bergerak.
- Installer memakai `node:14-buster-slim`, yang sudah EOL dan berbeda major dari runtime 18–26. Modul native yang dibuat saat instalasi dapat gagal pada runtime karena ABI Node.js berbeda. Gunakan installer yang major-nya cocok untuk runtime yang dipilih (misalnya Egg/installer per major), atau build dependensi native di lingkungan runtime yang cocok. Jangan menganggap `npm install` sekali dengan Node 14 kompatibel untuk semua major.
- Skrip installer dalam ekspor memakai line ending CRLF. Pemeriksaan `bash -n` langsung gagal pada CRLF, sedangkan setelah dinormalisasi ke LF sintaksnya lolos. Normalisasi ke LF atau pastikan proses import Panel mengubahnya sebelum dijalankan.
- Variabel `ACCESS_TOKEN` pada lampiran dapat dilihat pengguna dan skrip menyisipkannya ke URL Git. Jangan masukkan token ke URL remote, log, atau `.git/config`; gunakan akses publik bila memungkinkan. Untuk repo privat, batasi token hanya-baca dan gunakan mekanisme kredensial sementara yang tidak menyimpan token pada remote. Menyembunyikan field dari pengguna panel saja tidak mencegah token tertinggal di URL remote.

Jalankan validator pada ekspor Egg sebelum import: masalah template yang belum dideklarasikan dan pola token berisiko akan ditandai. Repo ini hanya menyediakan image dan snippet; ia tidak mengubah Egg yang sudah terpasang.

## Pembaruan otomatis dan pengujian

GitHub Actions di [`.github/workflows/publish.yml`](.github/workflows/publish.yml) dijadwalkan **setiap Senin pukul 04:23 UTC** dan juga dapat dijalankan manual melalui **Actions → Build and publish Pterodactyl Node.js images → Run workflow**. Schedule berjalan dari default branch; GitHub dapat menunda atau melewatkan jadwal saat beban tinggi.

Sebelum publish, workflow membangun dan menjalankan smoke test untuk setiap Node.js 18–26 pada runner Linux native `amd64` dan `arm64`, termasuk verifikasi `node`, `npm`, user `container`, `HOME`, working directory, entrypoint Tini, dan fixture startup Egg. Semua tes harus lolos dahulu; setelah itu Buildx menerbitkan manifest multi-platform untuk setiap tag. Build menghasilkan SBOM dan provenance. Aksi GitHub dipin ke SHA penuh dan memakai runtime Node 24; `GITHUB_TOKEN` hanya diberi izin `contents: read` secara default dan `packages: write` pada job publish. Tidak perlu GitHub CLI atau token pribadi.

Pengujian native menggunakan runner [GitHub-hosted Linux ARM64](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) karena repo ini publik. Ini menguji image container dan fixture command, **bukan** import Egg di Panel maupun integrasi live Panel/Wings. Tidak ada akses Panel/Wings yang tersedia dalam task ini, jadi uji integrasi tersebut belum dapat diklaim.

Setelah job berhasil, GHCR tags yang sama diperbarui. Wings/Docker memilih arsitektur dari manifest saat menarik image; perilaku cache/pull tetap bergantung konfigurasi node dan tag mutable. Jika Dockerfile kelak menambah instruksi `RUN` lintas arsitektur, workflow build juga perlu memakai native runner per arsitektur atau emulator yang sesuai.

## Build dan validasi lokal

Pada host Linux yang arsitekturnya sesuai:

```sh
python3 scripts/validate_egg.py

docker buildx build --pull --platform linux/amd64 --load \
  --build-arg NODE_VERSION=24 -t local/img-nodejs:nodejs_24 .
bash scripts/smoke_test_image.sh 24 amd64 local/img-nodejs:nodejs_24
```

Untuk menguji `arm64`, jalankan pada host ARM64 atau siapkan emulator binfmt/QEMU pada mesin lokal. Workflow CI menguji kedua arsitektur pada runner native. Major yang didukung pada matrix saat ini adalah 18–26; saat menambah/menghapus major, perbarui matrix dan peta Egg bersama-sama.
