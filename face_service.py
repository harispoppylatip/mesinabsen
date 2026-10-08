"""Layanan wajah untuk absen wajah aplikasi sekolah.

Kenapa dipisah dari PHP
-----------------------
Memuat model wajah butuh beberapa detik dan memakan memori besar. Kalau
dijalankan dari PHP pada setiap scan, presensi jadi lambat. Karena itu modelnya
dimuat sekali di proses ini, lalu aplikasi sekolah cukup mengirim foto.

Layanan ini hanya mendengarkan di localhost, jadi foto wajah tidak pernah
keluar dari komputer server sekolah dan tidak pernah disimpan ke disk.

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
        {"status": "success", "encoding": [...128 angka...], "face_count": 1}
        {"status": "no_face", "encoding": null, "face_count": 0}

    GET /health
        {"status": "ok"}

Bila ada lebih dari satu wajah, yang dipakai adalah wajah terbesar, karena
biasanya itulah orang yang berdiri paling dekat dengan kamera. Jumlah wajah
tetap dilaporkan lewat `face_count` supaya program pendaftaran massal bisa
menolak foto yang isinya lebih dari satu orang.
"""

from __future__ import annotations

import io
import os

import face_recognition
import numpy as np
import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

# Alamat dan port layanan. Keduanya bisa diubah lewat variabel lingkungan
# FACE_HOST dan FACE_PORT tanpa menyunting berkas ini. Ubah juga
# FACE_SERVICE_URL di .env aplikasi Laravel bila alamatnya berubah.
#
# Bawaannya 127.0.0.1, artinya hanya menerima koneksi dari komputer yang sama.
# Di dalam Docker, docker-compose.yml mengisinya 0.0.0.0 supaya kontainer lain
# bisa menghubunginya, sedangkan siapa yang boleh masuk dari luar diatur oleh
# bagian "ports" pada berkas itu.
HOST = os.getenv("FACE_HOST", "127.0.0.1")
PORT = int(os.getenv("FACE_PORT", "5005"))

# Nama model yang ikut disimpan di database sebagai penanda asal angkanya.
MODEL_NAME = "dlib-resnet-v1"

# Panjang angka pembanding wajah. Nilai ini harus sama dengan
# FaceEmbedding::Dimensions di aplikasi Laravel.
DIMENSIONS = 128

app = FastAPI(title="Layanan Wajah Presensi Sekolah", version="1.0.0")


def largest_face(locations: list[tuple[int, int, int, int]]) -> int | None:
    """Pilih wajah terbesar dari beberapa wajah yang terdeteksi.

    `locations` berisi (atas, kanan, bawah, kiri). Wajah terbesar dianggap
    wajah yang paling dekat dengan kamera.
    """

    if not locations:
        return None

    def area(location: tuple[int, int, int, int]) -> int:
        top, right, bottom, left = location
        return max(0, bottom - top) * max(0, right - left)

    return max(range(len(locations)), key=lambda index: area(locations[index]))


def no_face_response(message: str, face_count: int = 0) -> JSONResponse:
    return JSONResponse(
        {
            "status": "no_face",
            "encoding": None,
            "face_count": face_count,
            "model": MODEL_NAME,
            "message": message,
        }
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Penanda layanan hidup. Dipakai aplikasi sekolah sebelum memakai wajah."""

    return {"status": "ok", "model": MODEL_NAME, "dimensions": str(DIMENSIONS)}


@app.post("/encode")
async def encode(image: UploadFile = File(...)) -> JSONResponse:
    """Hitung angka pembanding wajah dari satu foto."""

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

    index = largest_face(locations)
    encodings = face_recognition.face_encodings(picture, [locations[index]])

    if not encodings:
        return no_face_response("Wajah terlihat tetapi tidak bisa dibaca.", len(locations))

    encoding = np.asarray(encodings[0], dtype=float).ravel()

    if encoding.size != DIMENSIONS:
        return no_face_response("Bentuk angka wajah tidak sesuai.", len(locations))

    return JSONResponse(
        {
            "status": "success",
            "encoding": [round(float(value), 6) for value in encoding],
            "face_count": len(locations),
            "model": MODEL_NAME,
            "message": "Wajah terbaca." if len(locations) == 1 else "Wajah terbaca, ada lebih dari satu wajah di foto.",
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
