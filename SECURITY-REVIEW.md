# Pemeriksaan keamanan image Node.js

## Kesimpulan

CVE-2026-111497 (RCE decoder Brotli) diperbaiki oleh Node.js **22.23.4, 24.22.1, dan 26.12.1**, menurut [advisori resmi](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases). Manifest patch repo kini mencatat rilis terbaru setiap major 18–26 dan build menolak runtime yang tidak cocok.

**Jangan menganggap tag GHCR yang sudah ada ikut diperbarui hanya karena source diperbaiki.** Tag produksi sebelumnya dilaporkan masih memakai 22.23.3, 24.21.0 dan 26.10.0. Perubahan ini disiapkan melalui PR; penggantian tag produksi ditahan sampai hasil pengujian dan keamanan ditinjau.

## Temuan yang menghambat publikasi

Image upstream terbaru membawa patch Node.js yang benar, tetapi pemindaian Trivy 0.76.1 masih menemukan HIGH/CRITICAL pada paket OS dan tool global. Contoh pada Node 24: 364 temuan HIGH dan 6 CRITICAL jika seluruh target OS, npm, dan binary Go dijumlahkan. Ini adalah pasangan paket/CVE, bukan jumlah CVE unik atau bukti seluruh temuan dapat dieksploitasi dalam aplikasi.

Contoh temuan kritis Node 24 mencakup `liblmdb0` (CVE-2019-16224/16225/16227), `libxml2` (CVE-2026-6653), `linux-libc-dev` (CVE-2026-93221), dan `openssh-client` (CVE-2026-60002). Scanner tidak melaporkan fixed version untuk temuan ini pada snapshot yang dipakai. Tidak ada ignorelist atau pengecualian yang ditambahkan. Perlu validasi upstream/vendor dan pengurangan atau pembaruan paket; mengganti major Node saja tidak memperbaikinya.

Versi 18, 19, 20, 21, 23 dan 25 sudah EOL. Rilis terakhir masing-masing bukan patch keamanan untuk insiden Oktober 2026; migrasi ke line yang didukung tetap diperlukan.

### CVE target masih ditemukan pada library OS

Keenam kandidat supported (22/24/26 × amd64/arm64) pada run [39874754860](https://github.com/akaanakbaik/img-nodejs/actions/runs/39874754860) masih melaporkan **CVE-2026-111497** pada `libbrotli1 1.1.0-2+b7`, status `affected`, severity `UNKNOWN`, tanpa fixed version. Gate HIGH/CRITICAL saja tidak mencakup temuan ini; workflow diperbaiki agar CVE tersebut selalu memblokir kandidat terlepas severity, tanpa ignorelist.

[Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-111497) menandai Brotli Trixie vulnerable/unfixed dan menyatakan paket Debian `nodejs` memakai Brotli sistem. Binary `/usr/local/bin/node` pada image ini harus diperiksa sendiri: bukti lokal ketiga versi amd64 menunjukkan tidak ada `DT_NEEDED`/hasil `ldd` ke `libbrotli*`, `node_shared_brotli=false`, dan tidak memuat library itu setelah operasi Brotli. Node membawa perbaikan vendored menurut rilis resmi, meskipun string versi Brotli belum berubah. Ini tidak membuktikan library Debian aman bagi konsumen lain dan **tidak digunakan sebagai pengecualian**. Bukti native CI per-digest/arsitektur disimpan bersama laporan.

## Pemeriksaan yang ditambahkan

- Kecocokan patch exact terhadap indeks rilis resmi, dengan penolakan manifest kedaluwarsa.
- Minimum perbaikan CVE untuk line 22/24/26; major dan arsitektur runtime diperiksa.
- Brotli synchronous/streaming round-trip serta penolakan fixture invalid yang tidak mengeksploitasi RCE.
- Smoke test kontrak Pterodactyl: non-root, HOME, working directory, Tini, npm dan fixture startup.
- CI native amd64/arm64; pemindaian OS/library dan secret/misconfiguration; SBOM CycloneDX; laporan, digest kandidat, snapshot DB scanner dan linkage disimpan walaupun gerbang gagal.
- Tag produksi dibuat dari image kandidat yang persis sudah diuji, bukan rebuild berbeda. HIGH/CRITICAL atau kegagalan scanner menahan publikasi.
- CVE-2026-111497 memblokir kandidat pada severity apa pun, termasuk UNKNOWN.

## Batas verifikasi

Metadata manifest kedua arsitektur telah diperiksa pada registry upstream; metadata bukan pengganti eksekusi runtime. Hasil native CI dan hasil build/scan kandidat final akan dicatat saat tersedia. Belum ada klaim uji integrasi Panel/Wings, audit dependency aplikasi yang dipasang pengguna, eksploitasi RCE, ataupun image yang bebas seluruh CVE.

Digest image dasar yang dipilih dicatat di log build; digest kandidat serta hasil scanner tersimpan pada artifact workflow. Tidak ada digest manifest produksi baru selama gerbang publikasi masih gagal.

Sumber: [advisori keamanan Node.js](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases), [indeks rilis](https://nodejs.org/dist/index.json), [status dukungan](https://nodejs.org/en/about/previous-releases), dan laporan scanner per-image dari workflow PR.
