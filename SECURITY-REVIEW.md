# Image Node.js: patch runtime siap, publikasi masih ditahan

**Belum layak dinyatakan aman untuk produksi.** Source pembaruan ada di [PR #1](https://github.com/akaanakbaik/img-nodejs/pull/1), tetapi tidak di-merge, tidak dipublikasikan, dan tidak di-deploy. Tag GHCR produksi sebelumnya tetap tidak berubah. Keenam kandidat supported memuat patch Node yang tepat, namun library Brotli OS masih terdampak CVE yang sama dan benar-benar dipakai oleh konsumen lain.

## Hasil terpenting

[Rilis keamanan Node.js 21 Oktober 2026](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases) memperbaiki CVE-2026-111497 pada **22.23.4, 24.22.1, dan 26.12.1**. Manifest juga mencatat patch terakhir seluruh major 18–26 berdasarkan indeks resmi. Major 18/19/20/21/23/25 sudah EOL; patch terakhirnya bukan perbaikan resmi untuk insiden ini.

Pada commit **`dc5855c8da3a8946e9ba9aa1dfde8443ddbf2714`**, [CI run 39876738576](https://github.com/akaanakbaik/img-nodejs/actions/runs/39876738576) melakukan build, verifikasi patch exact, uji Brotli, smoke test kontrak Egg, pemeriksaan linkage, pemindaian image final, SBOM, dan audit konsumen pada runner native **amd64 dan arm64**.

| Runtime | Arsitektur | Patch/runtime/Egg | Linkage Node ke Brotli OS | Decoder OS dipanggil curl dengan HTTP aman | Gate CVE |
|---|---|---|---|---|---|
| 22.23.4 | amd64 | Lulus | Tidak ditemukan | Ya | Menolak |
| 22.23.4 | arm64 | Lulus | Tidak ditemukan | Ya | Menolak |
| 24.22.1 | amd64 | Lulus | Tidak ditemukan | Ya | Menolak |
| 24.22.1 | arm64 | Lulus | Tidak ditemukan | Ya | Menolak |
| 26.12.1 | amd64 | Lulus | Tidak ditemukan | Ya | Menolak |
| 26.12.1 | arm64 | Lulus | Tidak ditemukan | Ya | Menolak |

Seluruh 12 job EOL (6 major × 2 arsitektur) berhasil sebagai audit non-publishing. Enam job supported gagal **hanya pada gate khusus CVE-2026-111497** setelah scan dan artifact tersimpan. Kedua job publikasi di-skip. Run lama 39875956770 memakai commit 0d3aa88, sebelum isolasi EOL; jangan gunakan run lama tersebut untuk menilai kebijakan EOL yang baru.

## Node bundled berbeda dari library Debian

Untuk keenam kandidat final, `ldd` dan `readelf -d /usr/local/bin/node` tidak mencantumkan `libbrotli*`, `process.config.variables.node_shared_brotli=false`, dan shared objects proses sesudah operasi Brotli tidak memuat library OS tersebut. String versi Brotli internal adalah **1.1.0** pada Node 22 dan **1.2.0** pada Node 24/26.

String itu tidak cukup untuk menentukan status CVE: catatan rilis resmi [22.23.4](https://nodejs.org/en/blog/release/v22.23.4), [24.22.1](https://nodejs.org/en/blog/release/v24.22.1), dan [26.12.1](https://nodejs.org/en/blog/release/v26.12.1) mencatat cherry-pick perbaikan Brotli `0ed4268`. Bukti linkage mendukung bahwa jalur Brotli built-in Node menggunakan komponen bundled tersebut, bukan `libbrotli1` Debian. Uji fungsional bukan pembuktian matematis atau exploit test bahwa seluruh RCE mustahil.

Sementara itu, scanner masih melaporkan **CVE-2026-111497 pada `libbrotli1 1.1.0-2+b7`**, status **affected**, severity **UNKNOWN**, tanpa fixed version. [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-111497) menandai Brotli Trixie vulnerable/unfixed. Catatan bahwa Debian `nodejs` memakai Brotli sistem berlaku pada packaging Debian; jangan otomatis menyamakannya dengan binary upstream `/usr/local/bin/node`. Status rentan library Debian tetap relevan bagi konsumennya sendiri.

## Library rentan bukan orphan

Audit per kandidat mencatat paket/reverse dependencies dan `DT_NEEDED` serta simbol decoder untuk curl, git-remote-http, ffmpeg/ffprobe, libcurl, libjxl, libfreetype, dan Node. Bukti inti pada keenam kandidat:

- **libcurl OpenSSL dan GnuTLS** membutuhkan `libbrotlidec.so.1` dan mengimpor `BrotliDecoderDecompressStream`.
- **libfreetype** membutuhkan `libbrotlidec.so.1` dan mengimpor `BrotliDecoderDecompress`.
- **libjxl** membutuhkan decoder/encoder Brotli dan mengimpor `BrotliDecoderDecompressStream`.
- **curl** membawa kemampuan Brotli dan memuat library decoder melalui libcurl. Daftar dependency paket juga menunjukkan library tersebut bukan paket tidak terpakai.

Uji dinamis hanya memakai payload Brotli **valid dan tidak berbahaya**: Node membuat fixture, server HTTP loopback mengirim `Content-Encoding: br`, lalu `curl --compressed` mendekodenya. Probe `LD_PRELOAD` memantau dan meneruskan panggilan decoder dengan ABI publik yang benar. **Semua enam kandidat** menghasilkan teks yang benar serta marker `BROTLI_PROBE_CALLED BrotliDecoderDecompressStream`.

Dengan demikian, data yang dikendalikan endpoint HTTP dapat mencapai decoder Brotli sistem ketika auto-decode diaktifkan. [Dokumentasi libcurl](https://curl.se/libcurl/c/CURLOPT_ACCEPT_ENCODING.html) dan [source 8.14.1](https://raw.githubusercontent.com/curl/curl/curl-8_14_1/lib/content_encoding.c) mengonfirmasi jalur tersebut. Ini **tidak** menunjukkan branch rentan atau exploit RCE telah dipicu. Default auto-decode libcurl adalah nonaktif; aplikasi harus mengaktifkannya, misalnya melalui `curl --compressed` atau opsi API terkait.

Jalur [WOFF2 FreeType](https://raw.githubusercontent.com/freetype/freetype/VER-2-13-3/src/sfnt/sfwoff2.c) dan [compressed box JPEG XL](https://raw.githubusercontent.com/libjxl/libjxl/v0.11.1/lib/jxl/box_content_decoder.cc) juga memanggil decoder. Pada audit ini keduanya didukung linkage/simbol dan source, **belum** diuji dengan fixture WOFF2/JXL dinamis. Dependency binary bukan bukti setiap konfigurasi aplikasi otomatis mengonsumsi input tersebut. Audit ini bukan enumerasi seluruh kemungkinan plugin, `dlopen`, modul native, atau aplikasi yang kelak dipasang pengguna; jangan membuat pengecualian global.

## Scan dan digest yang dapat diperiksa

Scanner: **Trivy 0.76.1**, schema database **2**, `UpdatedAt` **2026-10-22T19:14:47.059491382Z**. Snapshot tiap runner juga menyimpan `DownloadedAt` dan digest policy bundle. Setiap kandidat supported memiliki **364 pasangan paket/CVE HIGH dan 6 CRITICAL**, ditambah CVE Brotli target pada UNKNOWN. Hitungan bukan CVE unik atau bukti seluruh temuan dapat dieksploitasi.

Contoh CRITICAL tanpa fixed version pada snapshot: `liblmdb0` (CVE-2019-16224/16225/16227), `libxml2` (CVE-2026-6653), `linux-libc-dev` (CVE-2026-93221), dan `openssh-client` (CVE-2026-60002). Patch Node tidak memperbaiki seluruh paket OS, npm, atau tool Go yang dibundel upstream.

[Ringkasan kandidat final](security/native-candidates-2026-10-23.json) mencatat **digest manifest setiap arsitektur**, image/config ID yang dicocokkan ke laporan scanner, digest base, hash binary Node, snapshot DB, hasil linkage/probe, dan hasil job. [Bukti native per kandidat](security/2026-10-23-native/) menyimpan metadata, linkage, dan audit konsumen. Laporan Trivy lengkap serta SBOM CycloneDX tersedia pada artifact `reports-MAJOR-ARCH` di run CI. Digest kandidat lokal/build bukan bukti image telah tersedia publik; **tidak ada manifest produksi baru yang diterbitkan**.

## Mengapa tidak langsung menghapus atau mengganti library

Pemeriksaan paket Node 24 amd64 setelah `apt-get update` masih menunjukkan installed dan candidate `libbrotli1` sama-sama **1.1.0-2+b7**. Brotli upstream fixed pada 1.1.1/1.2.1, tetapi paket fixed yang kompatibel belum tersedia dari repository Trixie yang dikonfigurasi pada pemeriksaan ini.

Simulasi `apt-get -s remove libbrotli1` mengusulkan penghapusan **28 paket**, termasuk **curl, git, dan ffmpeg**. Tidak ada penghapusan dilakukan: tindakan itu mengubah fitur Yolks/Egg dan tidak boleh dipakai sekadar menyembunyikan hasil scan. Simulasi upgrade OS sebelumnya hanya menawarkan bind9/tzdata; itu tidak memperbaiki seluruh temuan.

## Gerbang dan langkah berikutnya

1. **Pertahankan blokir publikasi.** Kandidat supported ditolak jika CVE-2026-111497 terdeteksi pada severity apa pun, termasuk UNKNOWN; HIGH/CRITICAL dan kegagalan scanner tetap hard-fail. Tidak ada ignorelist atau pengecualian reachability.
2. **Dapatkan library OS fixed yang dapat dipertanggungjawabkan**, melalui pembaruan vendor/packaging yang benar atau rancangan base alternatif yang menjaga fitur yang diperlukan. Custom backport bukan hasil yang sudah diimplementasikan di PR ini. Jangan sekadar menimpa file atau memalsukan versi paket agar scanner diam.
3. Setelah perubahan remediasi, ulangi build native kedua arsitektur, audit consumer, decode/regression test Egg, scan final, dan pencocokan digest. Perubahan ini belum menguji Panel/Wings live atau dependency aplikasi pengguna.
4. **EOL tidak diterbitkan.** Matrix publikasi hanya 22/24/26 × kedua arsitektur; EOL dipindai dan diunggah sebagai laporan nonblocking, tanpa opsi override. Regression test memeriksa matrix/kondisi workflow dan gate CVE pada seluruh severity serta laporan invalid.

Source pembaruan dan pengujian tersedia; **remediasi keseluruhan image belum selesai**. Tag lama serta server produksi tidak otomatis berubah oleh PR ini.
