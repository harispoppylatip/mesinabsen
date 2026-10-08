"""Pendaftaran wajah massal dari folder foto per NIS.

Susunan folder yang dibaca
--------------------------
    images/
      25001/
        depan.jpg
        kiri.jpg
      25002/
        depan.jpg

Nama folder adalah nomor induk anggota (NIS), dan itulah identitas yang dipakai
aplikasi sekolah. Nama berkas foto bebas dan hanya dipakai sebagai catatan sudut
wajah.

Cara kerja
----------
Skrip ini mengirim setiap foto ke layanan wajah lokal yang sama dengan yang
dipakai absen, jadi cara menghitung angkanya tidak pernah berbeda antara
pendaftaran dan saat scan. Hasilnya dikirim ke aplikasi Laravel.

Contoh pemakaian
----------------
    python enroll_faces.py --dry-run
    python enroll_faces.py
    python enroll_faces.py --images "D:\\foto siswa" --url http://127.0.0.1:8000
    python enroll_faces.py --report

Catatan penting
---------------
- Foto dengan lebih dari satu wajah dilewati, karena folder ini disiapkan untuk
  satu orang per foto. Foto yang gagal dilaporkan beserta alasannya.
- Pendaftaran ulang bersifat mengganti, bukan menumpuk, supaya menjalankan
  skrip ini dua kali tidak menggandakan data.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import requests

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_SERVICE_URL = "http://127.0.0.1:5005"
DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_DEVICE_ID = "kamera-wajah"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Daftarkan wajah anggota dari folder foto per NIS.",
    )
    parser.add_argument("--images", default="images", help="Folder induk berisi satu folder per NIS.")
    parser.add_argument("--service", default=DEFAULT_SERVICE_URL, help="Alamat layanan wajah.")
    parser.add_argument("--url", default=DEFAULT_API_URL, help="Alamat aplikasi sekolah.")
    parser.add_argument("--device", default=DEFAULT_DEVICE_ID, help="ID perangkat pengirim data.")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Tambahkan foto baru tanpa menghapus wajah lama. Bawaan: ganti wajah lama.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hitung wajahnya saja, jangan simpan apa pun ke aplikasi.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Tampilkan daftar anggota yang sudah punya wajah, lalu berhenti.",
    )
    return parser.parse_args()


def encode_photo(service_url: str, path: Path) -> dict:
    """Minta layanan wajah menghitung angka pembanding dari satu foto."""

    with path.open("rb") as handle:
        response = requests.post(
            f"{service_url.rstrip('/')}/encode",
            files={"image": (path.name, handle, "image/jpeg")},
            timeout=120,
        )

    response.raise_for_status()

    return response.json()


def store_embedding(
    api_url: str,
    device_id: str,
    user_id: str,
    embedding: list[float],
    label: str,
    replace: bool,
) -> tuple[bool, str]:
    """Kirim satu angka wajah ke aplikasi sekolah."""

    response = requests.post(
        f"{api_url.rstrip('/')}/api/face/register",
        json={
            "device_id": device_id,
            "user_id": user_id,
            "embedding": embedding,
            "label": label[:50],
            "replace": replace,
        },
        headers={"Accept": "application/json"},
        timeout=60,
    )

    if response.status_code in (200, 201):
        payload = response.json()
        total = payload.get("data", {}).get("total", "?")
        return True, f"tersimpan, total {total} wajah"

    try:
        error = response.json()
        message = error.get("message") or "Penolakan dari aplikasi sekolah."
    except ValueError:
        message = f"Balasan tidak terbaca, kode {response.status_code}."

    return False, message


def show_report(api_url: str, device_id: str) -> int:
    """Tampilkan anggota yang sudah punya sidik wajah."""

    response = requests.get(
        f"{api_url.rstrip('/')}/api/face/embeddings",
        params={"device_id": device_id},
        headers={"Accept": "application/json"},
        timeout=60,
    )
    response.raise_for_status()

    rows = response.json().get("data", [])

    if not rows:
        print("Belum ada anggota yang punya wajah terdaftar.")
        return 0

    print(f"{len(rows)} anggota sudah punya wajah terdaftar:")
    for row in rows:
        print(f"  {row.get('user_id')}  {row.get('name')}  {row.get('photos')} foto")

    return 0


def member_folders(root: Path) -> list[Path]:
    return sorted(folder for folder in root.iterdir() if folder.is_dir())


def photo_files(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def main() -> int:
    arguments = parse_arguments()

    try:
        if arguments.report:
            return show_report(arguments.url, arguments.device)
    except requests.RequestException as error:
        print(f"Gagal menghubungi aplikasi sekolah: {error}")
        return 1

    root = Path(arguments.images)

    if not root.is_dir():
        print(f"Folder foto tidak ditemukan: {root.resolve()}")
        return 1

    folders = member_folders(root)

    if not folders:
        print(f"Belum ada folder NIS di dalam {root.resolve()}.")
        return 1

    total_saved = 0
    total_skipped = 0
    problems: list[str] = []

    for folder in folders:
        user_id = folder.name
        photos = photo_files(folder)

        if not photos:
            total_skipped += 1
            problems.append(f"{user_id}: folder tidak berisi foto.")
            continue

        print(f"\n{user_id} ({len(photos)} foto)")

        for index, path in enumerate(photos):
            try:
                result = encode_photo(arguments.service, path)
            except requests.RequestException as error:
                print(f"  {path.name}: layanan wajah tidak bisa dihubungi ({error}).")
                problems.append(f"{user_id}: layanan wajah tidak bisa dihubungi.")
                break

            if result.get("status") != "success":
                total_skipped += 1
                print(f"  {path.name}: dilewati, {result.get('message', 'wajah tidak terbaca')}")
                problems.append(f"{user_id}/{path.name}: {result.get('message', 'wajah tidak terbaca')}")
                continue

            if int(result.get("face_count", 1)) > 1:
                total_skipped += 1
                print(f"  {path.name}: dilewati, ada lebih dari satu wajah di foto")
                problems.append(f"{user_id}/{path.name}: foto berisi lebih dari satu wajah.")
                continue

            if arguments.dry_run:
                print(f"  {path.name}: wajah terbaca (uji coba, tidak disimpan)")
                continue

            # Foto pertama tiap anggota mengganti wajah lamanya, sisanya menambah
            # sudut baru. Jadi menjalankan skrip ini berulang kali tetap aman.
            replace = index == 0 and not arguments.append

            try:
                saved, message = store_embedding(
                    arguments.url,
                    arguments.device,
                    user_id,
                    result["encoding"],
                    path.stem,
                    replace,
                )
            except requests.RequestException as error:
                print(f"  {path.name}: gagal mengirim ke aplikasi sekolah ({error})")
                problems.append(f"{user_id}: gagal mengirim ke aplikasi sekolah.")
                break

            if saved:
                total_saved += 1
                print(f"  {path.name}: {message}")
            else:
                total_skipped += 1
                print(f"  {path.name}: gagal, {message}")
                problems.append(f"{user_id}/{path.name}: {message}")

    print("\nSelesai.")
    print(f"  Tersimpan: {total_saved}")
    print(f"  Dilewati:  {total_skipped}")

    if problems:
        print("\nYang perlu diperbaiki:")
        for problem in problems:
            print(f"  {problem}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
