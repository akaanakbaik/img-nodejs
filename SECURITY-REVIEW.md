# Compiler sudah diremediasi; rilis image tetap diblokir

**Keenam kandidat sekarang memiliki 333 HIGH + 6 CRITICAL per image**, turun dari 348 HIGH + 6 CRITICAL. Seluruh 15 HIGH terkait Go/x/text pada compiler TypeScript sudah tidak muncul. Namun 339 pasangan Debian tetap terbuka, ditambah CVE Brotli target pada severity UNKNOWN. **Tidak ada VEX, ignorelist, perubahan severity/threshold, penghapusan fitur, merge, atau publikasi image/tag.**

Hasil final berasal dari commit **`96cf3edcac7b140df617220637914c3a63971843`**, [CI run 39915130063](https://github.com/akaanakbaik/img-nodejs/actions/runs/39915130063). [PR #1](https://github.com/akaanakbaik/img-nodejs/pull/1) tetap draft. Commit dokumentasi berikutnya tidak mengubah kandidat yang dipindai.

## Hasil enam build native

| Node exact | Arsitektur | Build, tes upstream, Egg, runtime, provenance, SBOM | HIGH / CRITICAL | Kedua gate keamanan |
|---|---|---|---|---|
| 22.23.4 | amd64 | Lulus | 333 / 6 | Menolak |
| 22.23.4 | arm64 | Lulus | 333 / 6 | Menolak |
| 24.22.1 | amd64 | Lulus | 333 / 6 | Menolak |
| 24.22.1 | arm64 | Lulus | 333 / 6 | Menolak |
| 26.12.1 | amd64 | Lulus | 333 / 6 | Menolak |
| 26.12.1 | arm64 | Lulus | 333 / 6 | Menolak |

Kedua gate benar-benar dijalankan dan gagal: gate CVE-2026-111497 pada severity apa pun, serta gate HIGH/CRITICAL image/repository. Semua langkah teknis sebelumnya berhasil; ekspor image untuk publikasi tidak dijalankan. Dua job publikasi di-skip. Seluruh 12 job EOL (18/19/20/21/23/25 × dua arsitektur) selesai sebagai laporan non-publishing, tanpa override publikasi EOL.

Scanner tetap **Trivy 0.76.1**, database schema 2, `UpdatedAt=2026-10-23T01:18:09.482141619Z`, sama dengan snapshot vulnerability DB baseline. Timestamp unduh berbeda dan dicatat per kandidat. Repository scan tetap dua MEDIUM dan satu LOW, tanpa HIGH/CRITICAL. Semua severity tetap disimpan; angka di tabel adalah pasangan paket/CVE, bukan CVE unik atau bukti eksploitabilitas.

## Remediasi nyata TypeScript, bukan beta atau binary opaque

Source stabil **TypeScript 7.0.2** dari [commit upstream `2bd066d`](https://github.com/microsoft/typescript-go/commit/2bd066d87f5bafd315be9f40889d0a60b9e58e0b) dipin dengan SHA-256 arsip `25cca8ec9d89e4ceec5181a677ded2c6d690fa18b81e1277846303973eb71fcf`. Builder terpisah memakai distribusi resmi **Go 1.26.10**, diverifikasi checksum untuk setiap arsitektur, dan memperbarui dependency source **golang.org/x/text ke v0.41.0**. `go mod verify`, seluruh tes Go upstream, dan pembandingan hash seluruh source `.go` dijalankan fail-closed. Diff `go.mod`/`go.sum`, source hashes, Go build-info, serta checksum seluruh output disimpan.

Paket native stabil npm diunduh dan diverifikasi SHA-512, lalu dipakai sebagai layout paket lengkap agar lisensi, deklarasi, library, dan metadata platform tetap dipertahankan. Hasilnya diinstal sebagai **paket custom source-rebuild lengkap** dengan metadata `official_upstream_binary=false`, bukan diklaim sebagai binary resmi upstream. Signature binary upstream yang tidak lagi berlaku tidak dipertahankan. Toolchain dan cache builder tidak disalin ke runtime; compiler serta fungsi Yolks tetap tersedia. [Manifest sumber/toolchain](security/typescript-source.json) menjelaskan seluruh pin dan keputusan menolak beta.

Binary yang benar-benar disalin dari masing-masing image final terbukti membawa **Go 1.26.10 + x/text v0.41.0**, memiliki checksum yang cocok dengan inventaris runtime, dan melaporkan **`Version 7.0.2`**. Scan final dan SBOM tidak lagi memuat 15 pasangan HIGH pada toolchain lama Go 1.26.4/x/text v0.38.0. Tidak ada perubahan dependency binary secara opaque atau penghapusan compiler untuk mengurangi angka scan.

### Perbedaan baseline help dijelaskan dan diverifikasi

Run awal [39913259633](https://github.com/akaanakbaik/img-nodejs/actions/runs/39913259633) sengaja tetap gagal saat tes upstream menemukan mismatch help. Pada source release, `getHeader()` menghitung padding dari panjang versi sebelum harness mengganti teks versi menjadi `FakeTSVersion`; baseline berasal dari versi dev sembilan karakter, sedangkan `7.0.2` lima karakter.

Run final pertama-tama mereproduksi failure menggunakan versi stabil, lalu verifier membuktikan diff aktual **tepat satu baris header: tambahan empat spasi sebelum icon**, tanpa perubahan opsi, isi, warna/icon, struktur baris, atau reference. Bukti lengkap beserta hash reference/actual dan unified diff tersedia dalam `typescript-provenance/help-baseline-analysis.json` untuk setiap kandidat. Perbedaan lain akan menggagalkan build.

Selanjutnya seluruh suite dijalankan dengan `-ldflags='-X github.com/microsoft/typescript-go/internal/core.version=7.0.0-dev'` **khusus executable tes**. Tidak ada golden yang diterima ulang, tes yang dilewati, atau source compiler yang diubah. Build compiler runtime tidak memakai override itu dan exact-version 7.0.2 diuji terpisah.

## Triage lengkap 339 temuan Debian

[Ringkasan 19 kelompok source](docs/security/2026-10-23-triage/debian-summary.md) dan JSON per kandidat mencakup **333 HIGH + 6 CRITICAL**, **59 binary package**, serta inventaris path **60 paket termasuk Brotli**. Semua 339 pasangan terhubung ke versi terpasang, source package raw scan, PURL/SBOM, dan path dpkg beserta hash ELF. Statusnya 190 `affected`, 148 `fix_deferred`, dan satu `will_not_fix`; semuanya tetap blocking, bukan exception.

Inventaris APT pada container sementara dari immutable image ID menyegarkan indeks tanpa menginstal paket. Pada keenam kandidat, seluruh 60 versi kandidat sama dengan versi terpasang. Semua 339 temuan Debian tetap tidak mempunyai `FixedVersion` dalam snapshot scanner. Ini bukti tidak ada upgrade kandidat yang tersedia pada repositori saat pemeriksaan, bukan klaim tidak mungkin ada patch upstream atau bahwa paket tersebut aman.

| Paket | Enam pasangan CRITICAL yang tetap terbuka |
|---|---|
| liblmdb0 | CVE-2019-16224, CVE-2019-16225, CVE-2019-16227 |
| libxml2 | CVE-2026-6653 |
| linux-libc-dev | CVE-2026-93221 |
| openssh-client | CVE-2026-60002 |

Temuan source `linux` melekat pada paket headers `linux-libc-dev`, bukan bukti versi kernel host. Paket systemd/SSH terpasang tidak membuktikan daemon sedang berjalan; image tetap memakai Tini. Sebaliknya, path/linkage juga bukan pembuktian suatu finding tidak reachable. Tidak ada base migration besar, pencampuran suite Debian, atau penghapusan ffmpeg/curl/git/compiler untuk membuat gate hijau.

## Brotli patched tetap dilaporkan feed

Remediasi sebelumnya tetap dipertahankan: source upstream Brotli 1.1.1 dibangun menjadi paket Debian custom **`1.1.1-0img1~deb13u1`**, dengan source checksum, Debian source metadata, package checksums, ABI/SONAME/simbol, tes upstream, dan provenance build. Ini bukan rilis keamanan resmi Debian.

Pada keenam image final, ownership/hash library, API decoder, linkage, serta benign HTTP Brotli probe membuktikan curl memuat Brotli 1.1.1. Node upstream yang exact tetap memakai bundled Brotli terpisah. Probe bukan exploit test atau bukti seluruh RCE mustahil.

Scanner masih mengaitkan **CVE-2026-111497**, `affected/UNKNOWN`, `FixedVersion:null`, ke PURL `libbrotli1@1.1.1-0img1~deb13u1` per arsitektur. Source provenance dan runtime fixed tidak menghapus finding vendor. Tidak ada VEX atau pengecualian ditambahkan. Setiap kemungkinan pengecualian spesifik paket/CVE/digest/arsitektur tetap memerlukan keputusan eksplisit policy owner, alasan, owner, dan expiry; pekerjaan ini tidak membuat keputusan tersebut atau melonggarkan gate.

## Bukti per digest dan arsitektur

[Ringkasan kandidat final](docs/security/2026-10-23-triage/candidates.json) mencatat manifest OCI, config/image ID, base digest, arsitektur, expected Node, scanner snapshot, gate, dan SHA-256 artifact. Verifier OCI membaca dan memverifikasi descriptor/blob graph, termasuk config dan layer, lalu mengikat digest ke config image yang diuji. Image ID scan dan CycloneDX SBOM harus cocok dengan kandidat. Digest ini adalah kandidat build lokal, bukan publikasi registry.

Artifact `reports-22/24/26-amd64/arm64` pada run final menyimpan laporan Trivy semua severity, SBOM, audit semua finding, triage source/package/path, kandidat APT, linkage dan probe Brotli, inventaris compiler/binary, full compiler provenance, diff help, serta bukti OCI. Evidence kecil dan triage final juga tersimpan di direktori review repo. Smoke mencakup user/HOME/PWD, Tini/Egg startup, npm install/uninstall offline, TypeScript strict/multi-file/declarations/diagnostic negatif serta eksekusi JavaScript hasil compile, curl/git/ffmpeg. Ini bukan uji Panel/Wings live atau seluruh aplikasi pengguna.

## Urutan blocker berikutnya

1. Pertahankan blokir rilis dan seluruh gate. Tidak ada merge/publish/deploy tanpa persetujuan eksplisit berikutnya.
2. Dapatkan fix vendor Debian yang dapat dibuktikan untuk masing-masing 19 kelompok; upgrade semua binary package dari source terkait secara konsisten dan uji kompatibilitas kedua arsitektur. Jangan mengganti library sistem secara manual atau mencampur suite sekadar demi versi lebih tinggi.
3. Untuk temuan Brotli yang tampak sebagai keterlambatan feed mengenali revision lokal, lanjutkan klarifikasi vendor/feed atau ajukan keputusan policy owner terpisah. Jangan membuat VEX otomatis.
4. Setelah perubahan berikutnya, ulangi enam build native, suite/regresi compiler, Egg/runtime/provenance, probe consumer, scan semua severity, dan SBOM dengan ikatan digest yang sama ketatnya.
