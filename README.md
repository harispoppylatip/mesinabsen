# Layanan Wajah Presensi Sekolah

Layanan kecil berbasis FastAPI yang mengubah foto wajah menjadi 128 angka
pembanding. Angka itulah yang disimpan dan dibandingkan oleh aplikasi sekolah,
bukan fotonya. Foto yang dikirim hanya diproses di memori, tidak pernah ditulis
ke disk.

Layanan ini dipakai bersama aplikasi presensi berbasis Laravel, tetapi bisa juga
dipakai sendiri oleh program lain karena antarmukanya hanya HTTP biasa.

## Isi folder

| Berkas               | Keterangan                                                   |
| -------------------- | ------------------------------------------------------------ |
| `face_service.py`    | Layanan wajah. Menyediakan `GET /health` dan `POST /encode`. |
| `enroll_faces.py`    | Skrip pendaftaran wajah secara massal dari folder foto.      |
| `main.py`            | Contoh uji coba lewat kamera laptop. Bukan bagian layanan.   |
| `simple_facerec.py`  | Kelas bantu untuk contoh `main.py`.                          |
| `requirements.txt`   | Daftar paket Python yang dipakai.                            |
| `Dockerfile`         | Resep image layanan.                                         |
| `docker-compose.yml` | Cara menjalankan layanan dengan Docker.                      |
| `.env.example`       | Contoh pengaturan alamat dan port.                           |
| `README-wajah.md`    | Panduan lebih dalam untuk menghubungkan ke aplikasi Laravel. |

## Kenapa dipisah dari aplikasi PHP

Memuat model wajah butuh beberapa detik dan memakan memori cukup besar. Kalau
model itu dimuat ulang setiap kali ada yang memindai wajah, presensi jadi lambat
dan terasa berat. Di sini modelnya dimuat satu kali saat layanan dinyalakan,
lalu aplikasi sekolah cukup mengirim satu foto dan menerima angkanya. Aplikasi
PHP juga tidak perlu memasang Python, dlib, dan seabrek pustaka gambar.

## Menjalankan dengan Docker

Cukup dua perintah:

```
docker compose up -d --build
```

Cek statusnya:

```
docker compose ps
```

Layanan siap dipakai setelah kolom status berbunyi `healthy`. Pemuatan model
butuh waktu, jadi pemeriksaan pertama diberi tenggang dua menit sebelum
dianggap gagal.

Lihat catatan layanan:

```
docker compose logs -f face
```

Untuk menghentikannya:

```
docker compose down
```

Alamat bawaan `http://127.0.0.1:5005`, sama dengan alamat yang dipakai aplikasi
Laravel. Untuk mengubahnya, salin `.env.example` menjadi `.env` lalu sesuaikan
`FACE_PUBLISH_HOST` dan `FACE_PUBLISH_PORT`.

### Menguji layanan

Periksa apakah layanan hidup:

```
curl http://127.0.0.1:5005/health
```

Balasannya:

```json
{ "status": "ok", "model": "dlib-resnet-v1", "dimensions": "128" }
```

Kirim satu foto:

```
curl -F "image=@images/2005221/depan.jpg" http://127.0.0.1:5005/encode
```

Di Windows, tulis `curl.exe` karena `curl` di PowerShell adalah nama lain dari
`Invoke-WebRequest` dan tidak mengenal opsi `-F`.

### Bila port 5005 sudah dipakai

Ubah `FACE_PUBLISH_PORT=5006` di `.env`, jalankan ulang `docker compose up -d`,
lalu samakan `FACE_SERVICE_URL` di `.env` aplikasi Laravel menjadi
`http://127.0.0.1:5006`.

## Menjalankan tanpa Docker

Kalau Docker belum tersedia, layanan bisa dijalankan langsung:

```
python face_service.py
```

Disarankan memakai virtual environment. Di folder ini sudah ada `.venv`, dan
selalu panggil lewat interpreter di dalamnya:

```
.\.venv\Scripts\python.exe face_service.py
```

Di Windows, `python` yang ada di PATH sering tidak punya `uvicorn` sehingga
muncul `ModuleNotFoundError: No module named 'uvicorn'`. Memanggil lewat venv
menghindari masalah itu.

Membuat environment dari awal:

```
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-deps face-recognition==1.3.0
```

Baris terakhir memang perlu dipisah. Penjelasannya ada di bagian Catatan teknis
di bawah.

### Mengatur alamat dan port tanpa Docker

Isi `FACE_HOST` dan `FACE_PORT` sebagai variabel lingkungan sebelum menjalankan
berkasnya:

```
$env:FACE_HOST = "0.0.0.0"
$env:FACE_PORT = "5005"
.\.venv\Scripts\python.exe face_service.py
```

Nilai bawaan `127.0.0.1:5005` sengaja dipilih supaya layanan tidak terbuka ke
jaringan tanpa diminta. Di dalam Docker, `docker-compose.yml` sendiri yang
mengisi `FACE_HOST` dengan `0.0.0.0` supaya kontainer bisa dihubungi, sedangkan
siapa yang boleh masuk dari luar diatur oleh bagian `ports`.

## Kontrak layanan

### `GET /health`

Penanda layanan hidup. Aplikasi sekolah memanggilnya sebelum memakai fitur
wajah, jadi pengguna tidak menunggu lama hanya untuk mengetahui layanan mati.

```json
{ "status": "ok", "model": "dlib-resnet-v1", "dimensions": "128" }
```

### `POST /encode`

Menerima satu foto pada field bernama `image` (bukan `file`), dengan tipe
`multipart/form-data`. Balasannya:

```json
{
  "status": "success",
  "encoding": [128 angka],
  "face_count": 1,
  "model": "dlib-resnet-v1",
  "message": "Wajah terbaca."
}
```

Bila tidak ada wajah yang terlihat:

```json
{
  "status": "no_face",
  "encoding": null,
  "face_count": 0,
  "model": "dlib-resnet-v1",
  "message": "Wajah tidak terlihat."
}
```

Bila fotonya rusak atau kosong, balasannya berstatus HTTP 400 dengan
`"status": "error"`.

Kalau dalam foto ada beberapa orang, yang diambil adalah wajah terbesar karena
biasanya itulah yang berdiri paling dekat dengan kamera. Jumlah wajah tetap
dilaporkan lewat `face_count`, sehingga aturan "satu foto satu orang" bisa
ditegakkan oleh program pemanggil.

Nilai `dimensions` harus sama dengan `FaceEmbedding::Dimensions` di aplikasi
Laravel. Angka 128 sendiri berasal dari model dlib resnet v1.

## Menghubungkan ke aplikasi Laravel

Di `.env` aplikasi Laravel:

```
FACE_SERVICE_URL=http://127.0.0.1:5005
FACE_SERVICE_TIMEOUT=90
```

Kalau alamatnya diubah, bersihkan cache pengaturan:

```
php artisan config:clear
```

Tenggang 90 detik bukan angka asal. Satu foto butuh 12 sampai 15 detik di mesin
tanpa kartu grafis, dan percobaan pertama selalu paling lama karena pemuatan
model. Tenggang yang ketat membuat pendaftaran massal gagal padahal layanannya
sehat.

## Pendaftaran massal dari folder foto

Susun satu folder per nomor induk:

```
images/
  25001/
    depan.jpg
    kiri.jpg
  25002/
    depan.jpg
```

Lalu jalankan skripnya. Dengan Docker:

```
docker compose run --rm --entrypoint python face enroll_faces.py --images /srv/images --service http://face:5005 --url http://host.docker.internal:8000 --dry-run
```

Hapus `--dry-run` untuk menyimpan sungguhan. Beberapa keterangan:

- `--service http://face:5005` memakai nama layanan di jaringan Docker, karena
  `127.0.0.1` di dalam kontainer menunjuk ke kontainer itu sendiri.
- `--url http://host.docker.internal:8000` menunjuk ke aplikasi Laravel yang
  berjalan di komputer ini. Nama itu sudah didaftarkan di `docker-compose.yml`
  lewat `extra_hosts`.
- `--device kamera-wajah` bisa ditambahkan bila aplikasi memakai ID alat lain.

Tanpa Docker:

```
.\.venv\Scripts\python.exe enroll_faces.py --dry-run
.\.venv\Scripts\python.exe enroll_faces.py --report
```

Menjalankan ulang perintah yang sama akan menggantikan wajah lama, jadi aman
diulang. Tambahkan `--append` bila memang ingin menambah tanpa menghapus.

Foto di folder itu dipasang ke kontainer sebagai baca saja, sehingga layanan
maupun pendaftaran massal tidak akan mengubah apa pun di folder tersebut.

## Catatan teknis

### Kenapa memakai dlib-bin

Paket `face-recognition` mencantumkan `dlib>=19.7` sebagai syarat. Masalahnya,
distribusi `dlib` di PyPI hanya tersedia sebagai berkas sumber, sehingga pip
akan mengompilasinya. Kompilasi itu butuh cmake dan bisa berjalan belasan menit,
sering gagal di Windows.

Paket `dlib-bin` menyediakan roda siap pakai untuk Windows dan Linux x86_64,
namun memasang modul dengan nama `dlib` juga. Jadi `dlib-bin` dipasang lebih
dulu, lalu `face-recognition` dipasang tanpa dependensi:

```
pip install -r requirements.txt
pip install --no-deps face-recognition==1.3.0
```

Karena dependensi tidak ikut dipasang, kebutuhan lain dari `face-recognition`
didaftarkan sendiri di `requirements.txt` dengan versi yang terkunci. Ini juga
membuat image hasil build selalu memakai versi yang sama, bukan versi terbaru
yang kebetulan ada saat itu.

`setuptools` dikunci di bawah versi 81 karena `face-recognition-models` masih
memakai `pkg_resources` yang sudah dijadwalkan dihapus. Bila kunci itu dilepas,
pemasangan bisa tiba-tiba gagal di kemudian hari.

Dockerfile memasang paket-paket itu dengan urutan yang sama, jadi tidak ada
kompilasi dlib saat build.

### Kinerja

Satu foto sekitar 12 sampai 15 detik di mesin tanpa kartu grafis. Deteksi wajah
memakai model `hog` yang memang dipilih karena tidak memerlukan kartu grafis.
Pengenalan pertama setelah layanan dinyalakan selalu paling lama.

Karena itu `docker-compose.yml` memberi layanan batas memori 1500 MB dan 2 CPU,
serta tenggang dua menit pada pemeriksaan kesehatan pertama.

### Keamanan

Layanan ini tidak punya autentikasi, jadi alamatnya sengaja diikat ke
`127.0.0.1` pada bawaan `docker-compose.yml`. Hanya program di komputer yang
sama yang bisa memanggilnya.

Bila layanan memang perlu diakses dari komputer lain, jangan mengubah
`FACE_PUBLISH_HOST` menjadi `0.0.0.0` begitu saja. Pasang dulu pembatas seperti
reverse proxy yang meminta kata sandi, atau jaringan internal yang tertutup.

### Privasi

Foto wajah tidak pernah disimpan. Foto yang masuk ke `POST /encode` dibaca ke
memori, dihitung angkanya, lalu dibuang. Yang tersimpan di database aplikasi
sekolah hanya 128 angka pembanding, yang tidak bisa dikembalikan menjadi gambar.

## Berkas terkait

`README-wajah.md` berisi panduan yang lebih dekat ke aplikasi sekolah, termasuk
pendaftaran wajah lewat halaman web, pembatasan jumlah foto per anggota, dan
istilah yang dipakai di antarmuka admin.
