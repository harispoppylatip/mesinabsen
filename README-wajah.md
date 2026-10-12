# Absen wajah untuk aplikasi sekolah

Bagian ini menjalankan mesin wajah dan mendaftarkan wajah anggota. Aplikasi
sekolah (Laravel) hanya menyimpan angka pembanding wajah, tidak menyimpan foto.

## Menyiapkan

```
pip install -r requirements.txt
```

Kalau `face_recognition` gagal dipasang di Windows karena dlib, pasang dulu roda
siap pakainya:

```
pip install dlib-bin
pip install face_recognition
```

Kalau folder ini sudah punya `.venv`, pakai langsung tanpa memasang apa pun lagi:

```
.\.venv\Scripts\python.exe -c "import uvicorn, fastapi, multipart"
```

Di Windows, `python` yang ada di PATH sering tidak punya `uvicorn`, sehingga
muncul `ModuleNotFoundError: No module named 'uvicorn'`. Selalu panggil lewat venv
di atas.

## 1. Nyalakan layanan wajah

```
.\.venv\Scripts\python.exe face_service.py
```

Layanan hidup di `http://127.0.0.1:5005` (port dan `HOST` diatur di bagian atas
`face_service.py`). Biarkan jendela ini terbuka selama absen wajah dipakai.
Alamatnya bisa diubah lewat `FACE_SERVICE_URL` di `.env` aplikasi Laravel.

Layanan ini hanya menerima koneksi dari mesin yang sama selama `HOST` masih
`127.0.0.1`. Kalau dipindah ke komputer lain, ubah `HOST` menjadi `0.0.0.0` di
sini, isi `FACE_SERVICE_URL` dengan IP komputer itu, lalu jalankan
`php artisan config:clear` di aplikasi Laravel.

**Satu foto butuh 12-15 detik** di mesin tanpa kartu grafis, dan percobaan
pertama selalu paling lama karena pemuatan model. Karena itu pendaftaran massal
sebaiknya dikirim bertahap (aplikasi sekolah membatasi tiga foto per kiriman),
dan `FACE_SERVICE_TIMEOUT` di aplikasi dibuat longgar, 90 detik.

## 2. Siapkan foto

Susun satu folder per nomor induk (NIS):

```
images/
  25001/
    depan.jpg
    kiri.jpg
  25002/
    depan.jpg
```

Satu foto sebaiknya berisi satu orang, wajah terlihat jelas, dan cahaya cukup.
Tiga sampai lima sudut wajah per orang memberi hasil pengenalan yang lebih
tenang daripada satu foto.

## 3. Daftarkan wajah

Cek dulu tanpa menyimpan:

```
python enroll_faces.py --dry-run
```

Simpan sungguhan:

```
python enroll_faces.py
```

Lihat siapa saja yang sudah terdaftar:

```
python enroll_faces.py --report
```

Menjalankan ulang perintah yang sama bersifat mengganti wajah lama, jadi aman
diulang. Pakai `--append` kalau memang ingin menambah foto tanpa menghapus yang
lama.

### Daftar lewat website aplikasi sekolah

Folder `images/` dan skrip `enroll_faces.py` di atas tetap berguna untuk
pendaftaran massal dari server. Pendaftaran lewat website dilakukan tanpa membuka
terminal, dan di aplikasi sekolah halaman `/wajah` menyediakan:

- panel **Tambah foto wajah** - pilih satu anggota, lampirkan paling banyak
  sepuluh foto sekali kirim, lalu pantau kemajuannya di panel Proses pendaftaran
  wajah karena pengubahannya menjadi angka wajah berjalan di latar belakang;
- kotak centang **Ganti foto wajah anggota ini** pada panel yang sama;
- kolom **Foto wajah (opsional)** pada form tambah anggota di halaman Anggota.

Impor folder langsung dari peramban sudah tidak ada, jadi pendaftaran sekaligus
banyak anggota memakai skrip `enroll_faces.py` di atas.

Batasnya 20 foto per anggota. Tanpa mencentang kotak ganti, foto baru ditumpuk
dan yang paling lama dibuang begitu jumlahnya lewat batas. Dengan kotak itu
dicentang, seluruh foto lama diganti oleh seluruh foto baru yang berhasil
diproses, dan penggantiannya baru dikerjakan setelah seluruh foto kiriman itu
selesai diproses. Foto yang gagal tidak pernah ikut tersimpan, dan bila seluruh
foto baru gagal maka foto lama tetap dipertahankan. Foto yang memuat lebih dari
satu orang ditolak dengan pesan yang bisa dibaca.

## 4. Pakai di aplikasi

Alat kamera wajah harus terdaftar di halaman Alat Sensor dengan ID `kamera-wajah`
(terisi otomatis saat penyemaian). Setelah itu:

- admin mengatur siapa saja guru petugas kamera di halaman Data Wajah;
- petugas membuka halaman Kamera Absen Wajah dari HP, menekan Nyalakan kamera,
  lalu menaruh wajah di depan kamera.

Halaman kamera memeriksa SEMUA wajah yang terlihat pada satu bingkai, bukan
hanya satu orang. Setiap orang yang dikenali diberi kotak beserta namanya di
atas gambar kamera, dan kehadirannya dicatat sendiri sendiri, sehingga
beberapa siswa bisa absen pada bingkai yang sama. Wajah yang belum terdaftar
tetap diberi kotak dengan label "Tidak dikenal" dan tidak dicatat.

Bingkai dikirim tiap 1,5 detik, jadi wajah yang sama akan terlihat berkali kali.
Absennya hanya dicatat sekali: pengiriman ulang oleh orang yang sudah tercatat
dibalas dengan status "sudah absen" dan tidak menambah catatan baru. Satu foto
bukti absen dipakai bersama untuk semua orang pada bingkai itu.

Jangan mengandalkan kotak di layar sebagai bukti kehadiran. Yang menentukan
adalah catatan absen di aplikasi sekolah.

Presensi masuk atau pulang mengikuti jam presensi yang sudah diatur di halaman
Presensi Gerbang, sama seperti sensor sidik jari.

## Kontrak layanan (untuk menghubungkan alat lain)

- `GET /health` membalas `{"status":"ok","model":"dlib-resnet-v1","dimensions":"128"}`.
- `POST /encode` menerima berkas pada field bernama **`image`** (bukan `file`) dan
  membalas `{"status":...,"encoding":[128 angka],"face_count":...,"face_size":...,"model":...,"message":...}`.
- `face_size` adalah sisi terpendek kotak wajah dalam piksel. Aplikasi sekolah
  memakainya untuk menolak potret yang wajahnya terlalu kecil, sebab wajah 40
  piksel masih menghasilkan 128 angka yang terlihat wajar padahal angkanya sudah
  tidak layak dipakai memutuskan identitas.
- Jawaban `success` tetap menyertakan `face_count`, sehingga penolakan "foto
  memuat lebih dari satu wajah" tetap dikerjakan di aplikasi Laravel juga. Mesin
  wajah versi lama yang belum melaporkan `face_size` dan belum mengenal
  `require_single` tetap bisa dipakai.
- `POST /encode?require_single=1` menolak sendiri foto yang memuat lebih dari satu
  wajah, yaitu `{"status":"multiple_faces","encoding":null,"face_count":2,...}`,
  supaya alur absen tidak diam-diam memakai wajah terbesar. Tanpa parameter ini
  perilakunya sama seperti sebelumnya.
- `POST /encode?with_photo=1` menambahkan potret kecil bukti absen pada
  jawabannya, yaitu kunci `photo` (JPEG dalam base64), `photo_bytes`,
  `photo_width`, `photo_height`, dan `photo_quality`. Foto aslinya diperkecil
  lebih dulu lalu mutu JPEG-nya diturunkan sampai masuk batas, sehingga satu
  potret biasanya hanya belasan kilobita. Bila potretnya gagal dibuat, kunci
  itu dihilangkan dan jawabannya tetap `success`.
- `POST /detect` menerima berkas yang sama pada field **`image`** dan membalas
  seluruh wajah pada bingkai itu: `{"status":...,"face_count":...,"width":...,"height":...,"faces":[{"index":...,"bbox":{"top":...,"right":...,"bottom":...,"left":...},"face_size":...,"encoding":[...],"error":null}, ...]}`.
  Kotak `bbox` memakai koordinat piksel gambar asli yang dikirim pemanggil,
  sehingga bisa digambar apa adanya di atas bingkai kamera. Wajah yang angkanya
  gagal dihitung tetap dilaporkan dengan `encoding` bernilai null dan
  `error` bernilai `encoding_failed`, jadi satu wajah yang gagal tidak
  menggagalkan yang lain. Bila tidak ada wajah, `status` bernilai `no_face` dan
  `faces` berupa daftar kosong; daftar kosong itulah tanda bagi pemanggil untuk
  menghapus kotak yang lama. Parameter `with_photo=1` tetap menghasilkan SATU
  potret untuk seluruh bingkai, bukan satu per wajah.
- `FACE_DETECT_MAX_SIDE` (bawaan 1024) dan `FACE_MAX_FACES` (bawaan 8) mengatur
  batas pekerjaan `/detect`: gambar besar diperkecil dulu untuk deteksi lalu
  koordinatnya dikembalikan ke skala asli, dan jumlah wajah yang dihitung dibatasi
  supaya bingkai yang ramai tidak menghabiskan memori. Isi `FACE_MAX_FACES=0`
  untuk tidak membatasi.
- Layanan ini hanya membandingkan angka wajah. Ia tidak membedakan wajah asli
  dari foto wajah yang ditunjukkan ke kamera, dan tidak memeriksa kedipan mata.
  Pemeriksaan seperti itu belum ada di sini.
