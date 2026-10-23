# Rilis tetap diblokir; triage lengkap dan rebuild compiler sedang divalidasi

## Kelanjutan PR #1

Triage seluruh **339 pasangan Debian HIGH/CRITICAL pada 19 source package** kini tersedia dalam [ringkasan kelompok](docs/security/2026-10-23-triage/debian-summary.md) dan enam JSON per kandidat. Seluruh 59 binary package terhubung ke inventaris dpkg (termasuk hash ELF), versi, source package raw scan, PURL dan SBOM. Tidak ada fixed version vendor pada snapshot baseline. Kandidat APT pada run berikutnya akan direkam setelah refresh repository; versi tersedia bukan bukti suatu CVE sudah fixed.

Remediasi TypeScript yang sedang diuji **tidak memakai beta atau menghapus compiler**: source stabil 7.0.2 yang dipin dibangun native memakai **Go 1.26.10** dan **x/text v0.41.0**, dengan paket native lengkap, lisensi, metadata custom yang transparan, tes upstream `go test -p 2 ./...`, diff dependency, checksum source/paket dan build-info. Source compiler `.go` harus tidak berubah. Stage builder serta toolchain tidak disalin ke runtime. Ini custom rebuild, bukan binary rilis resmi upstream; hasil dan pengurangan finding **belum boleh dinyatakan berhasil sebelum keenam CI native selesai**.

CI menambah uji compiler strict/multi-file/declarations/diagnostics; inventaris compiler aktual; ikatan digest OCI ke config/image ID dan arsitektur; serta triage vendor per kandidat. Gate HIGH/CRITICAL sekarang dievaluasi terpisah walaupun gate CVE target menolak; kegagalan sebelumnya tetap mencegah ekspor image teruji. Ambang, isi laporan, dan gate CVE tidak dilonggarkan. Tidak ada VEX atau ignorelist. Keputusan policy owner diperlukan sebelum pengecualian apa pun; pekerjaan ini tidak membuat pengecualian tersebut.

## Baseline terakhir yang selesai sebelum perubahan ini

**PR #1 belum layak dirilis.** Keenam kandidat supported lulus build dan uji kompatibilitas native, termasuk curl yang benar-benar memakai Brotli 1.1.1. Namun setiap kandidat masih dilaporkan memiliki **348 HIGH + 6 CRITICAL**, serta CVE-2026-111497 berstatus vendor-unfixed pada paket custom. Tidak ada temuan diabaikan, ambang diturunkan, PR di-merge, atau image/tag publik diterbitkan oleh pekerjaan ini.

Hasil ini berasal dari commit **`db0a8498934ab8526f88ae86775b35754e967921`** pada [CI run 39910150287](https://github.com/akaanakbaik/img-nodejs/actions/runs/39910150287). Commit dokumentasi sesudahnya tidak mengubah image yang diuji.

## Perbaikan yang benar-benar dilakukan

[Advisory resmi Node.js](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases) menetapkan patch **22.23.4, 24.22.1, dan 26.12.1**. Binary upstream tersebut tetap dipakai dan diverifikasi exact; Brotli bundled Node berbeda dari library OS. Linkage dan shared objects sesudah operasi Brotli tidak menunjukkan Node memuat `libbrotli*` sistem (`node_shared_brotli=false`).

Library OS sebelumnya masih `libbrotli1 1.1.0-2+b7`. [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-111497) menyebut perbaikan upstream pada Brotli 1.1.1/1.2.1, tetapi belum menyediakan fixed version paket Debian. Dockerfile sekarang membangun **source upstream Brotli 1.1.1** menjadi paket Debian lokal asli **`1.1.1-0img1~deb13u1`**, bukan menimpa `.so` atau mengganti string versi.

Source dipin ke commit `db0631dfea829194206d269bc7b25d0908cdb97d`, dengan arsip SHA-256 `38f9c17ee36c2e930ce00975b50fcd246a8e5594c1bcf43cd56b14118786b82a`. Packaging Debian, semua checksum input, changelog lokal, `.dsc`, `.changes`, `.buildinfo`, checksum paket, serta alasan custom rebuild dapat ditelusuri dari [metadata source](security/brotli-source.json) dan artifact provenance. Paket custom ini **bukan rilis keamanan resmi Debian**.

Build menjalankan tes CMake normal dan **131 tes Python upstream**, pemeriksaan simbol Debian ketat, serta pembandingan SONAME dan seluruh simbol publik Brotli terhadap baseline. Tidak ada simbol baseline yang boleh hilang. Final image menginstal runtime library dan hanya memperbarui paket Brotli tambahan bila sebelumnya memang terpasang. Curl, git, ffmpeg, compiler, dan fitur Yolks tidak dihapus agar scanner diam.

Pembaruan vendor OS memakai refresh yang fail-closed dan `apt-get upgrade --no-remove`. Pembaruan paralel di branch PR juga dipertahankan: **npm resmi 12.2.1**, diverifikasi SHA-512 sebagai satu rilis utuh; dependency internal tidak ditambal manual. Scan final tidak lagi melaporkan HIGH/CRITICAL pada paket npm tersebut.

## Hasil native kedua arsitektur

| Node exact | Arsitektur | Build + Egg + npm/TypeScript | Decoder OS terverifikasi | HIGH / CRITICAL | Gate CVE target |
|---|---|---|---|---|---|
| 22.23.4 | amd64 | Lulus | Brotli 1.1.1 | 348 / 6 | Menolak |
| 22.23.4 | arm64 | Lulus | Brotli 1.1.1 | 348 / 6 | Menolak |
| 24.22.1 | amd64 | Lulus | Brotli 1.1.1 | 348 / 6 | Menolak |
| 24.22.1 | arm64 | Lulus | Brotli 1.1.1 | 348 / 6 | Menolak |
| 26.12.1 | amd64 | Lulus | Brotli 1.1.1 | 348 / 6 | Menolak |
| 26.12.1 | arm64 | Lulus | Brotli 1.1.1 | 348 / 6 | Menolak |

Smoke test memeriksa user `container`, HOME/PWD, Tini, startup Egg, patch/arsitektur Node, instalasi dan uninstall dependency npm lokal tanpa jaringan, kompilasi TypeScript dan eksekusi hasilnya, serta curl/git/ffmpeg. Ini bukan uji Panel/Wings live atau seluruh aplikasi pengguna.

Pada setiap kandidat, ownership dpkg dan SHA-256 ketiga library Brotli dicatat; API decoder yang benar-benar dimuat mengembalikan `0x1001001` (1.1.1). Probe `LD_PRELOAD` dengan payload HTTP Brotli **valid dan tidak berbahaya** kembali mengamati `BrotliDecoderDecompressStream` saat `curl --compressed` berhasil mendekode respons. Kali ini jalur itu menuju library fixed. Uji ini bukan exploit test atau pembuktian bahwa seluruh RCE mustahil. Audit libfreetype/libjxl tetap berupa linkage dan simbol; tidak diklaim sebagai fixture WOFF2/JXL dinamis.

## Bukti per digest, paket, path, CVE, dan SBOM

[Ringkasan keenam kandidat](docs/security/2026-10-23-remediation/candidates.json) menyimpan digest manifest tiap arsitektur, config/image ID, base digest, snapshot scanner, hasil setiap tahap, temuan priority/critical, dan SHA-256 seluruh artifact. Bukti linkage, konsumen, provenance, dan metadata kecil juga tersimpan di direktori review tersebut. Digest build lokal **bukan** tanda bahwa image sudah dipublikasikan.

Artifact `reports-22/24/26-amd64/arm64` pada run CI berisi:

- Laporan Trivy image lengkap semua severity dan SBOM CycloneDX; image ID scanner dan SBOM harus cocok dengan kandidat.
- `package-cve-audit.json`: setiap temuan dicocokkan ke PURL, referensi SBOM, versi, target/path, layer, dan advisory. Temuan yang tidak mempunyai pasangan SBOM menyebabkan audit gagal.
- `package-paths.json`: inventaris file milik **60 paket OS** yang dilaporkan blocking, termasuk hash ELF. Tidak semua paket OS mempunyai satu path tunggal; path bukan asumsi reachability.
- Metadata kandidat, hash binary Node, linkage, audit decoder, dan provenance source/paket.

Scanner adalah **Trivy 0.76.1**, database schema 2, `UpdatedAt=2026-10-23T01:18:09.482141619Z`. Pemindaian repository menghasilkan dua MEDIUM dan satu LOW, tanpa HIGH/CRITICAL. Hitungan 348/6 adalah pasangan paket/CVE, bukan jumlah CVE unik atau bukti semua temuan dapat dieksploitasi. Baseline sebelumnya 364/6 memakai snapshot database berbeda; jangan menganggap seluruh selisih angka sebagai efek remediasi saja.

## Mengapa gate tetap merah

**CVE target:** scanner masih melaporkan CVE-2026-111497 pada `libbrotli1 1.1.1-0img1~deb13u1`, severity UNKNOWN, tanpa fixed version vendor. Source upstream fixed, paket asli, ABI, ownership, dan decoder yang dimuat kini mempunyai bukti teknis, tetapi database Debian belum mengenali status fixed untuk rebuild ini. Tidak ada VEX, ignorelist, penggantian database, atau pengecualian custom yang digunakan. Gate khusus CVE tetap menolak temuan pada severity apa pun.

**Temuan lainnya:** ada **339 pasangan HIGH/CRITICAL dari paket Debian** tanpa fixed version dalam snapshot, ditambah **15 HIGH pada binary TypeScript Go**. Enam CRITICAL adalah:

| Paket | CVE | Fixed version di snapshot |
|---|---|---|
| liblmdb0 | CVE-2019-16224, CVE-2019-16225, CVE-2019-16227 | Tidak tersedia |
| libxml2 | CVE-2026-6653 | Tidak tersedia |
| linux-libc-dev | CVE-2026-93221 | Tidak tersedia |
| openssh-client | CVE-2026-60002 | Tidak tersedia |

Binary TypeScript berada di `/usr/local/lib/node_modules/typescript/node_modules/@typescript/typescript-linux-x64/lib/tsc` atau path platform arm64 yang dicatat scanner. Ia membawa Go stdlib `1.26.4` dan `golang.org/x/text v0.38.0`; penutupan seluruh temuan yang dilaporkan memerlukan binary dibangun dengan setidaknya Go 1.26.10 dan x/text 0.41.0. Meng-upgrade Node saja tidak mengganti dependency yang tertanam di binary tersebut.

Keenam job supported gagal **hanya pada gate CVE target**, sesudah build, smoke, scan, validasi identitas, audit decoder, dan upload bukti selesai. Gate HIGH/CRITICAL berikutnya tidak dieksekusi karena kegagalan sebelumnya; hitungan scan menunjukkan gate itu juga belum dapat lulus. Kegagalan scanner atau laporan invalid tetap fail-closed.

## EOL dan izin publikasi

Seluruh **12 job EOL** (18/19/20/21/23/25 × dua arsitektur) selesai sebagai laporan non-publishing pada run final. Target `eol-audit` memakai baseline legacy tanpa menjalankan builder Debian supported; ini menghindari kegagalan repositori OS lawas mengganggu audit. `continue-on-error` hanya berlaku untuk EOL, dan matrix publikasi permanen hanya 22/24/26. Tidak ada override publikasi EOL.

Dua job publikasi di-skip. Source sekarang mengizinkan publikasi hanya melalui `workflow_dispatch` pada `main` dengan `publish=true` setelah persetujuan pemilik dan seluruh gate supported lulus; push/jadwal sendiri hanya audit. Artifact tar, checksum, image ID dan arsitektur diverifikasi kembali sebelum jalur publish. Jalur itu tidak dijalankan dalam pekerjaan ini.

## Urutan penyelesaian blocker

1. Pertahankan blokir rilis; jangan menganggap custom Brotli fixed sebagai alasan melewati gate CVE atau 354 temuan HIGH/CRITICAL lain.
2. Dapatkan paket vendor fixed dan status scanner yang sesuai, atau siapkan base/packaging alternatif yang dapat dibuktikan mempertahankan fitur Egg/Yolks. Saat ini pembaruan vendor OS yang tersedia tidak menutup 339 temuan OS tersebut.
3. Dapatkan rilis TypeScript dengan toolchain tertanam fixed, atau lakukan rebuild terpisah dengan provenance dan regression test compiler yang memadai; jangan menimpa dependency binary atau menghapus compiler sekadar untuk menyembunyikan scan.
4. Setelah remediasi berikutnya, ulangi keenam build native, kompatibilitas Egg, audit consumer, scan final, dan pencocokan digest/SBOM. Merge, publikasi, dan deployment tetap memerlukan persetujuan eksplisit pemilik.
