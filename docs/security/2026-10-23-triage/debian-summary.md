# Triage Debian final — 2026-10-23

## Hasil final dan baseline

Enam kandidat immutable Node 22/24/26 untuk amd64/arm64 dibuktikan melalui metadata kandidat, audit paket, raw Trivy, SBOM, serta verifikasi OCI. Baseline adalah **348 HIGH + 6 CRITICAL**; hasil final adalah **339 pasangan: 333 HIGH + 6 CRITICAL**, dengan **19 source group, 59 binary package**, dan inventory APT **60 paket**. Penurunan 15 HIGH bukan bukti seluruh isu telah fixed; pasangan tetap dipertahankan dan tidak ada VEX, ignore, penghapusan finding, atau pelonggaran gate.

| Perbandingan | Baseline | Final |
|---|---:|---:|
| HIGH | 348 | 333 |
| CRITICAL | 6 | 6 |
| pasangan audit | — | 339 |
| source group | — | 19 |
| binary package | — | 59 |
| inventory APT | — | 60 |

## Identitas dan toolchain

`candidates.json` memuat enam digest manifest, config/image ID, base digest, arsitektur, Node expected, hash scan+SBOM, serta tautan audit. `final-evidence/<major>-<arch>/` hanya memuat bukti ringkas dan `original-artifact-hashes.json`, yang meng-hash **semua file artefak asli** tanpa menyalin raw report/SBOM besar. `candidate-oci-verification.json` menunjukkan imageID/config, manifest runtime, OS Linux, dan arsitektur yang diamati; hasilnya dicocokkan fail-closed dengan candidate metadata.

Toolchain native yang diamati: **Go 1.26.10**, **x/text v0.41.0**, native compiler SHA-256, dan custom provenance (source commit/tarball, target, test, serta status baseline/compiler). Hash dan metadata scanner Trivy disimpan per kandidat.

## Debian/APT

Enam `debian-<major>-<arch>.json` adalah dokumen triage final aktual dari CI yang disalin byte-for-byte tanpa perubahan. Perbandingan APT memakai nilai `installed` dan `candidate` exact dpkg (bukan perbandingan string naif atau pengabaian epoch); perubahan yang ada, bila ada, dilist di `final-evidence/*/identity-summary.json`. Tidak boleh menyimpulkan candidate APT sudah memperbaiki CVE tanpa versi fixed/advisory vendor.

## Status CI dan keputusan

Run [39915130063](https://github.com/akaanakbaik/img-nodejs/actions/runs/39915130063) pada commit `96cf3edcac7b140df617220637914c3a63971843` selesai `failure` hanya karena dua security gates: CVE-2026-111497 pada severity apa pun, dan 339 temuan HIGH/CRITICAL Debian; seluruh stage build native, runtime/Egg, scan, audit, kandidat, OCI identity, toolchain, Brotli, dan upload evidence yang dieksekusi tercatat sukses. Publish/merge tidak dilakukan.

Pada keenam kandidat, seluruh 60 versi APT kandidat sama dengan versi terpasang. Seluruh 339 finding Debian masih tidak memiliki fixed version dalam snapshot scanner; statusnya 190 affected, 148 fix_deferred, dan satu will_not_fix. Semuanya tetap open/blocking.

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
