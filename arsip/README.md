# Berkas contoh yang sudah tidak dipakai

Isi folder ini adalah sisa dari bentuk awal folder `face absen`, waktu isinya
masih berupa program uji coba di kamera laptop. Sejak folder ini menjadi layanan
wajah untuk aplikasi sekolah (Laravel), dua berkas di sini tidak lagi ikut
dipakai.

| Berkas               | Keterangan                                                        |
| -------------------- | ----------------------------------------------------------------- |
| `main.py`            | Program contoh: membuka kamera laptop, mengenali wajah, lalu menggambar kotak dan nama di atas wajah. |
| `simple_facerec.py`  | Kelas `SimpleFacerec` yang dipakai `main.py` untuk memuat dan membandingkan wajah. |

## Alasan tidak dipakai

- Layanan yang dipanggil aplikasi sekolah hanya `face_service.py`, dengan dua
  alamat `GET /health` dan `POST /encode`.
- Pendaftaran wajah dikerjakan `enroll_faces.py` dari folder `images/<NIS>/`,
  atau lewat halaman `/wajah` di aplikasi sekolah.
- `Dockerfile` hanya menyalin `face_service.py` dan `enroll_faces.py` ke dalam
  image, jadi dua berkas di folder ini memang tidak pernah ikut ke layanan.
- `simple_facerec.py` membutuhkan `cv2` (opencv), sedangkan paket itu tidak ada
  di `requirements.txt`.
- Halaman Kamera Absen Wajah di aplikasi sekolah sudah mengambil alih fungsi
  contoh ini, dan hasilnya langsung tercatat sebagai presensi.

## Kalau ingin menjalankannya lagi

Pasang opencv dulu, lalu jalankan dari folder induk supaya folder `images/`
tetap terbaca. Python otomatis menambahkan folder `arsip` ke jalur pencarian
modul, jadi `from simple_facerec import SimpleFacerec` tetap bekerja.

```
.\.venv\Scripts\python.exe -m pip install opencv-python
.\.venv\Scripts\python.exe arsip\main.py
```

Tekan tombol ESC untuk menutup jendela video.
