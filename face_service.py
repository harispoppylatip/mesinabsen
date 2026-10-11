"""Layanan wajah untuk absen wajah aplikasi sekolah.

Kenapa dipisah dari PHP
-----------------------
Memuat model wajah butuh beberapa detik dan memakan memori besar. Kalau
dijalankan dari PHP pada setiap scan, presensi jadi lambat. Karena itu modelnya
dimuat sekali di proses ini, lalu aplikasi sekolah cukup mengirim foto.

Layanan ini hanya mendengarkan di localhost, jadi foto wajah tidak pernah
keluar dari komputer server sekolah. Foto yang masuk hanya dipakai untuk
menghitung angka wajah lalu dilepas dari memori. Satu-satunya foto yang
dikirim balik adalah foto bukti absen yang sudah diperkecil, dan itu pun
hanya bila pemanggil memintanya lewat `with_photo`.

Menjalankan
-----------
    python face_service.py

Di dalam Docker, berkas ini dijalankan oleh docker-compose.yml dengan
FACE_HOST bernilai 0.0.0.0 supaya bisa dihubungi dari luar kontainer.

Alamat bawaan http://127.0.0.1:5005, sama dengan `FACE_SERVICE_URL` di
`.env` aplikasi Laravel.

Kontrak balasan
---------------
    POST /encode   multipart, nama field "image"
        Parameter alamat, opsional:
            with_photo=1      ikutkan foto bukti absen dalam balasan
            require_single=1  tolak foto yang memuat lebih dari satu wajah

        {"status": "success", "encoding": [...128 angka...], "face_count": 1,
         "face_size": 412}
        {"status": "no_face", "encoding": null, "face_count": 0, "face_size": 0}
        {"status": "multiple_faces", "encoding": null, "face_count": 2,
         "face_size": 512}

        `face_size` adalah sisi terpendek kotak wajah dalam piksel. Angka ini
        dilaporkan supaya aplikasi sekolah bisa menolak potret yang wajahnya
        terlalu kecil, sebab potret seperti itu tetap menghasilkan 128 angka
        yang terlihat wajar padahal tidak layak dipakai memutuskan identitas.

        Bila with_photo=1, balasan sukses bertambah:
            "photo"        foto seluruh bingkai dalam JPEG, dikodekan base64
            "photo_bytes"  ukuran berkas JPEG hasil perkecilan
            "photo_width"  lebar sesudah diperkecil
            "photo_height" tinggi sesudah diperkecil
            "photo_quality" kualitas JPEG yang akhirnya dipakai

        Tanpa with_photo, balasannya sama persis seperti sebelumnya, jadi
        program pendaftaran wajah dan alat lama tidak perlu diubah.

    GET /health
        {"status": "ok"}

Bila ada lebih dari satu wajah, yang dipakai adalah wajah terbesar, karena
biasanya itulah orang yang berdiri paling dekat dengan kamera. Jumlah wajah
tetap dilaporkan lewat `face_count` supaya program pendaftaran massal bisa
menolak foto yang isinya lebih dari satu orang.

Untuk absen, pemanggil sebaiknya mengirim require_single=1 supaya foto yang
memuat lebih dari satu orang ditolak di sini, bukan diam-diam dipilihkan wajah
terbesar. Perilaku lama tetap dipakai bila parameter itu tidak dikirim.
"""

from __future__ import annotations

import base64
import io
import logging
import os

import face_recognition
import numpy as np
import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

logger = logging.getLogger("layanan-wajah")

# Alamat dan port layanan. Keduanya bisa diubah lewat variabel lingkungan
# FACE_HOST dan FACE_PORT tanpa menyunting berkas ini. Ubah juga
# FACE_SERVICE_URL di .env aplikasi Laravel bila alamatnya berubah.
#
# Bawaannya 127.0.0.1, artinya hanya menerima koneksi dari komputer yang sama.
# Layanan ini tidak punya kata sandi sama sekali, jadi membukanya ke jaringan
# harus selalu menjadi keputusan sadar: jalankan dengan FACE_HOST diisi
# 0.0.0.0 hanya bila mesin wajahnya memang dipisah dari aplikasi sekolah, lalu
# batasi dengan firewall. Di dalam Docker, Dockerfile dan docker-compose.yml
# mengisinya 0.0.0.0 supaya kontainer lain bisa menghubunginya, sedangkan siapa
# yang boleh masuk dari komputer lain diatur oleh bagian "ports" berkas itu
# (bawaannya FACE_PUBLISH_HOST 127.0.0.1).
HOST = os.getenv("FACE_HOST", "127.0.0.1")
PORT = int(os.getenv("FACE_PORT", "5005"))

# Nama model yang ikut disimpan di database sebagai penanda asal angkanya.
MODEL_NAME = "dlib-resnet-v1"

# Panjang angka pembanding wajah. Nilai ini harus sama dengan
# FaceEmbedding::Dimensions di aplikasi Laravel.
DIMENSIONS = 128

# Foto bukti absen. Seluruh bingkai foto dikirim balik dalam ukuran kecil
# supaya aplikasi sekolah bisa menyimpannya sebagai bukti siapa yang absen.
# Sisi terpanjang 480 piksel masih cukup untuk mengenali orang beserta latar
# ruangannya, sedangkan kualitas JPEG diturunkan bertahap sampai ukurannya muat
# di bawah batas bita. Ketiganya bisa diubah lewat variabel lingkungan tanpa
# menyunting berkas ini.
PROOF_MAX_SIDE = int(os.getenv("FACE_PROOF_MAX_SIDE", "480"))
PROOF_QUALITY = int(os.getenv("FACE_PROOF_QUALITY", "72"))
PROOF_MAX_KB = int(os.getenv("FACE_PROOF_MAX_KB", "48"))
PROOF_MAX_BYTES = PROOF_MAX_KB * 1024

# Kualitas yang dicoba berurutan. Yang pertama biasanya sudah muat, sisanya
# cadangan untuk foto yang ramai dan penuh warna.
PROOF_QUALITIES = tuple(max(30, PROOF_QUALITY - step * 8) for step in range(5))

app = FastAPI(title="Layanan Wajah Presensi Sekolah", version="1.0.0")


def largest_face(locations: list[tuple[int, int, int, int]]) -> int | None:
    """Pilih wajah terbesar dari beberapa wajah yang terdeteksi.

    `locations` berisi (atas, kanan, bawah, kiri). Wajah terbesar dianggap
    wajah yang paling dekat dengan kamera.

    Pemilihan ini hanya dipakai bila pemanggil tidak meminta `require_single`,
    karena untuk absen foto yang memuat lebih dari satu orang sebaiknya ditolak.
    """

    if not locations:
        return None

    def area(location: tuple[int, int, int, int]) -> int:
        top, right, bottom, left = location
        return max(0, bottom - top) * max(0, right - left)

    return max(range(len(locations)), key=lambda index: area(locations[index]))


def face_side(location: tuple[int, int, int, int]) -> int:
    """Sisi terpendek kotak wajah dalam piksel.

    Dipakai aplikasi sekolah untuk menolak potret yang wajahnya terlalu kecil.
    Angka 40 piksel misalnya masih menghasilkan 128 angka yang terlihat wajar,
    tetapi angka itu tidak layak dipakai memutuskan identitas siapa pun.
    """

    top, right, bottom, left = location

    return max(0, min(bottom - top, right - left))


def proof_photo(picture: object) -> dict[str, object] | None:
    """Perkecil seluruh bingkai foto menjadi JPEG kecil sebagai bukti absen.

    Sisi terpanjang dipotong ke PROOF_MAX_SIDE dan tidak pernah diperbesar,
    lalu kualitas JPEG diturunkan bertahap sampai ukurannya muat di bawah
    PROOF_MAX_BYTES. Yang dikirim adalah seluruh bingkai, bukan potongan
    wajah, supaya petugas masih bisa melihat latar ruangan saat memeriksa
    riwayat absen.
    """

    frame = Image.fromarray(np.asarray(picture, dtype="uint8")).convert("RGB")
    frame.thumbnail((PROOF_MAX_SIDE, PROOF_MAX_SIDE), Image.Resampling.LANCZOS)

    payload = b""
    quality = PROOF_QUALITIES[-1]

    for attempt in PROOF_QUALITIES:
        buffer = io.BytesIO()
        frame.save(
            buffer,
            format="JPEG",
            quality=attempt,
            optimize=True,
            progressive=True,
            subsampling="4:2:0",
        )

        payload = buffer.getvalue()
        quality = attempt

        if len(payload) <= PROOF_MAX_BYTES:
            break

    if not payload:
        return None

    return {
        "photo": base64.b64encode(payload).decode("ascii"),
        "photo_bytes": len(payload),
        "photo_width": frame.width,
        "photo_height": frame.height,
        "photo_quality": quality,
    }


def no_face_response(message: str, face_count: int = 0, face_size_pixels: int = 0) -> JSONResponse:
    return refusal_response("no_face", message, face_count, face_size_pixels)


def refusal_response(
    status: str,
    message: str,
    face_count: int = 0,
    face_size_pixels: int = 0,
) -> JSONResponse:
    """Balasan penolakan dengan bentuk yang sama seperti balasan sukses.

    Bentuknya sengaja dibuat seragam supaya aplikasi sekolah cukup membaca satu
    cara saja, dan supaya balasan tuduhan yang lama tetap tidak berubah.
    """

    return JSONResponse(
        {
            "status": status,
            "encoding": None,
            "face_count": face_count,
            "face_size": face_size_pixels,
            "model": MODEL_NAME,
            "message": message,
        }
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Penanda layanan hidup. Dipakai aplikasi sekolah sebelum memakai wajah."""

    return {"status": "ok", "model": MODEL_NAME, "dimensions": str(DIMENSIONS)}


@app.post("/encode")
async def encode(
    image: UploadFile = File(...),
    with_photo: bool = False,
    require_single: bool = False,
) -> JSONResponse:
    """Hitung angka pembanding wajah dari satu foto.

    Parameter `with_photo` diisi 1 oleh aplikasi sekolah saat foto itu dipakai
    untuk absen, supaya balasannya ikut memuat foto bukti yang sudah
    diperkecil. Pendaftaran wajah tidak memakai parameter ini karena foto
    pendaftaran tidak perlu disimpan.

    Parameter `require_single` diisi 1 oleh alur absen, supaya foto yang memuat
    lebih dari satu orang ditolak di sini dan bukan diam-diam dipilihkan wajah
    terbesar. Tanpa parameter ini perilakunya sama seperti sebelumnya.
    """

    payload = await image.read()

    if not payload:
        return JSONResponse(
            {
                "status": "error",
                "encoding": None,
                "face_count": 0,
                "message": "Foto kosong.",
            },
            status_code=400,
        )

    try:
        picture = face_recognition.load_image_file(io.BytesIO(payload))
    except Exception:
        return JSONResponse(
            {
                "status": "error",
                "encoding": None,
                "face_count": 0,
                "message": "Foto tidak bisa dibaca.",
            },
            status_code=400,
        )

    # Pilih model deteksi yang ringan supaya balasan tetap cepat di server
    # sekolah yang tidak punya kartu grafis.
    locations = face_recognition.face_locations(picture, model="hog")

    if not locations:
        return no_face_response("Wajah tidak terlihat.")

    terbesar = max(face_side(location) for location in locations)

    # Absen hanya untuk satu orang. Kalau pemanggilnya memang meminta satu
    # wajah, foto yang memuat lebih dari satu orang ditolak di sini.
    if require_single and len(locations) > 1:
        return refusal_response(
            "multiple_faces",
            "Ada lebih dari satu wajah di foto.",
            len(locations),
            terbesar,
        )

    index = largest_face(locations)
    encodings = face_recognition.face_encodings(picture, [locations[index]])

    if not encodings:
        return no_face_response("Wajah terlihat tetapi tidak bisa dibaca.", len(locations))

    encoding = np.asarray(encodings[0], dtype=float).ravel()

    if encoding.size != DIMENSIONS:
        return no_face_response("Bentuk angka wajah tidak sesuai.", len(locations))

    # Foto bukti tidak boleh menggagalkan absen. Bila perkecilannya gagal,
    # absennya tetap dicatat, hanya buktinya yang tidak ada.
    proof: dict[str, object] = {}

    if with_photo:
        try:
            proof = proof_photo(picture) or {}
        except Exception:
            logger.exception("Gagal menyiapkan foto bukti absen.")
            proof = {}

    return JSONResponse(
        {
            "status": "success",
            "encoding": [round(float(value), 6) for value in encoding],
            "face_count": len(locations),
            "face_size": face_side(locations[index]),
            "model": MODEL_NAME,
            "message": "Wajah terbaca."
            if len(locations) == 1
            else "Wajah terbaca, ada lebih dari satu wajah di foto.",
            **proof,
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
