# img-nodejs

Image alias untuk runtime Node.js Parkervcp Yolks yang dapat dipilih dari Egg Pterodactyl. Setiap image di repo ini mewarisi langsung tag upstream yang bersesuaian; tidak ada runtime Node.js yang dikompilasi atau dimodifikasi di sini.

## Tag yang diterbitkan

| Tag GHCR | Image dasar | Status Node.js per 13 Okt 2026 |
|---|---|---|
| `ghcr.io/akaanakbaik/img-nodejs:nodejs_18` | `ghcr.io/parkervcp/yolks:nodejs_18` | EOL |
| `ghcr.io/akaanakbaik/img-nodejs:nodejs_19` | `ghcr.io/parkervcp/yolks:nodejs_19` | EOL |
| `ghcr.io/akaanakbaik/img-nodejs:nodejs_20` | `ghcr.io/parkervcp/yolks:nodejs_20` | EOL |
| `ghcr.io/akaanakbaik/img-nodejs:nodejs_21` | `ghcr.io/parkervcp/yolks:nodejs_21` | EOL |
| `ghcr.io/akaanakbaik/img-nodejs:nodejs_22` | `ghcr.io/parkervcp/yolks:nodejs_22` | LTS |
| `ghcr.io/akaanakbaik/img-nodejs:nodejs_23` | `ghcr.io/parkervcp/yolks:nodejs_23` | EOL |
| `ghcr.io/akaanakbaik/img-nodejs:nodejs_24` | `ghcr.io/parkervcp/yolks:nodejs_24` | LTS |
| `ghcr.io/akaanakbaik/img-nodejs:nodejs_25` | `ghcr.io/parkervcp/yolks:nodejs_25` | EOL |
| `ghcr.io/akaanakbaik/img-nodejs:nodejs_26` | `ghcr.io/parkervcp/yolks:nodejs_26` | Current; latest major |

Image tersedia untuk `linux/amd64`, sesuai target umum node Pterodactyl. Workflow membangun semua versi saat ada perubahan yang relevan, dapat dijalankan manual, dan dijadwalkan mingguan untuk mengambil pembaruan tag upstream.

> Node.js 18, 19, 20, 21, 23, dan 25 sudah EOL dan tidak lagi menerima patch keamanan dari proyek Node.js. Gunakan versi tersebut hanya bila aplikasi lama memang membutuhkannya. Untuk produksi, prioritaskan versi LTS (22 atau 24); Node.js 26 adalah Current.

Versi terkini diverifikasi dari [halaman rilis resmi Node.js](https://nodejs.org/en/about/previous-releases) dan [daftar rilis upstream](https://github.com/nodejs/node/releases). Image dasar disediakan oleh [Parkervcp Yolks](https://github.com/parkervcp/yolks).

## Menghubungkan ke Egg Pterodactyl

Isi field `docker_images` di Egg dengan objek pada [`egg/docker_images.json`](egg/docker_images.json). Potongan tersebut menggunakan nama pilihan yang menjelaskan status EOL/LTS/Current. Egg yang sudah ada tidak diubah otomatis oleh repo ini.

Setelah workflow selesai dan GHCR image dibuat publik, jalankan ulang/reinstall server atau pull image dari node Pterodactyl agar image terbaru tersedia.

## Build lokal

```sh
docker build --build-arg NODE_VERSION=24 \
  -t ghcr.io/akaanakbaik/img-nodejs:nodejs_24 .
```

Workflow GitHub Actions `.github/workflows/publish.yml` menerbitkan seluruh tag `nodejs_18` sampai `nodejs_26` ke GitHub Container Registry (`ghcr.io`).
