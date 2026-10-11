"""Skrip sementara: uji endpoint /detect dengan gambar yang memuat beberapa wajah.

Dijalankan sekali, lalu dihapus.
"""

import io
import json
from pathlib import Path

import requests
from PIL import Image

BASE = Path(r"C:\Users\Pongo\Documents\face absen")
ALAMAT = "http://127.0.0.1:5005/detect"


def kirim(judul: str, payload: bytes, lebar: int, tinggi: int, with_photo: bool = False) -> None:
    url = f"{ALAMAT}?with_photo=1" if with_photo else ALAMAT
    jawaban = requests.post(url, files={"image": ("uji.jpg", payload, "image/jpeg")}, timeout=180)
    data = jawaban.json()

    print("=" * 78)
    print(f"{judul} ({lebar} x {tinggi}, {len(payload)} bita)")
    print(f"  status {jawaban.status_code} | status {data.get('status')} | wajah {data.get('face_count')}")
    print(f"  ukuran dilaporkan {data.get('width')} x {data.get('height')} | pesan: {data.get('message')}")

    for wajah in data.get("faces", []):
        bbox = wajah.get("bbox") or {}
        angka = wajah.get("encoding")
        print(
            f"  wajah {wajah.get('index')}: kotak atas {bbox.get('top')} kanan {bbox.get('right')} "
            f"bawah {bbox.get('bottom')} kiri {bbox.get('left')} | sisi {wajah.get('face_size')} px | "
            f"angka: {'ada ' + str(len(angka)) + ' nilai' if angka else 'TIDAK ADA'}"
            f"{' | galat ' + str(wajah.get('error')) if wajah.get('error') else ''}"
        )

        if bbox:
            luar = (
                bbox.get("top") < 0
                or bbox.get("left") < 0
                or bbox.get("right") > lebar
                or bbox.get("bottom") > tinggi
            )
            print(f"    kotak di luar bingkai: {'YA' if luar else 'tidak'}")

            # Wajah terbesar mestinya dilaporkan lebih dulu.
    if data.get("faces"):
        sisi = [w.get("face_size") or 0 for w in data["faces"]]
        print(f"  urutan sisi wajah: {sisi} | menurun: {'ya' if sisi == sorted(sisi, reverse=True) else 'TIDAK'}")

    for kunci in ("photo", "photo_bytes", "photo_width", "photo_height"):
        if kunci in data:
            print(f"  bukti {kunci}: {data[kunci] if kunci != 'photo' else 'ada ' + str(len(data[kunci])) + ' bita base64'}")

    print()


# 1. Satu orang.
satu = Image.open(BASE / "images" / "2005221" / "depan.jpg").convert("RGB")
satu.thumbnail((900, 900), Image.Resampling.LANCZOS)
buffer = io.BytesIO()
satu.save(buffer, format="JPEG", quality=88)
kirim("SATU WAJAH (Haris)", buffer.getvalue(), satu.width, satu.height, with_photo=True)

# 2. Dua orang berdampingan.
kiri = Image.open(BASE / "images" / "2005221" / "depan.jpg").convert("RGB")
kanan = Image.open(BASE / "images" / "20204081042" / "BING0753.jpg").convert("RGB")

tinggi = 1000
kiri = kiri.resize((round(kiri.width * tinggi / kiri.height), tinggi))
kanan = kanan.resize((round(kanan.width * tinggi / kanan.height), tinggi))

gabungan = Image.new("RGB", (kiri.width + kanan.width, tinggi), "white")
gabungan.paste(kiri, (0, 0))
gabungan.paste(kanan, (kiri.width, 0))

buffer = io.BytesIO()
gabungan.save(buffer, format="JPEG", quality=88)
kirim("DUA WAJAH BERDAMPINGAN", buffer.getvalue(), gabungan.width, gabungan.height)

# 3. Tiga orang: dua ujung + satu di tengah (menumpuk sebagian).
tiga = Image.new("RGB", (kiri.width + kanan.width + 400, tinggi), "white")
tiga.paste(kiri, (0, 0))
tiga.paste(kanan, (tiga.width - kanan.width, 0))
tengah = kiri.resize((round(kiri.width * 0.8), round(tinggi * 0.8)))
tiga.paste(tengah, ((tiga.width - tengah.width) // 2, 0))

buffer = io.BytesIO()
tiga.save(buffer, format="JPEG", quality=88)
kirim("TIGA WAJAH (sebagian bertumpuk)", buffer.getvalue(), tiga.width, tiga.height, with_photo=True)

# 4. Gambar tanpa wajah.
polos = Image.new("RGB", (800, 600), "white")
buffer = io.BytesIO()
polos.save(buffer, format="JPEG", quality=88)
kirim("TANPA WAJAH", buffer.getvalue(), 800, 600)

# 5. Gambar besar sekali, untuk memastikan koordinat tetap pada skala asli.
besar = gabungan.resize((gabungan.width * 2, gabungan.height * 2), Image.Resampling.LANCZOS)
buffer = io.BytesIO()
besar.save(buffer, format="JPEG", quality=85)
kirim("DUA WAJAH PADA GAMBAR SANGAT BESAR", buffer.getvalue(), besar.width, besar.height)
