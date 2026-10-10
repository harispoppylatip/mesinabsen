import cv2
import face_recognition
import os
import numpy as np

class SimpleFacerec:
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []

        # Mengubah ukuran frame untuk mempercepat proses deteksi
        self.frame_resizing = 0.25

    def load_encoding_images(self, images_path):
        """
        Load foto-foto dari folder untuk di-encode.

        Mendukung dua struktur sekaligus:
        1) Subfolder per orang : images/haris/01.jpg, images/haris/02.jpg
           -> nama orang = nama subfolder ("haris")
        2) File langsung        : images/haris.jpg
           -> nama orang = nama file ("haris")

        Semua foto milik satu orang disimpan sebagai beberapa encoding,
        sehingga pengenalan lebih akurat untuk berbagai sudut wajah.
        Foto tanpa wajah / gagal dibaca akan dilewati dengan peringatan.
        """
        # Reset supaya aman kalau dipanggil lebih dari sekali
        self.known_face_encodings = []
        self.known_face_names = []

        if not os.path.isdir(images_path):
            print(f"Folder '{images_path}' tidak ditemukan. Buat folder itu dan isi fotonya.")
            return

        valid_ext = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
        total_foto = 0
        total_orang = 0
        dilewati = []

        for entry in sorted(os.listdir(images_path)):
            entry_path = os.path.join(images_path, entry)

            if os.path.isdir(entry_path):
                # Struktur subfolder -> nama orang = nama folder
                nama_orang = entry
                foto_list = [
                    os.path.join(entry_path, f)
                    for f in sorted(os.listdir(entry_path))
                    if f.lower().endswith(valid_ext)
                ]
            else:
                # Struktur file langsung -> nama orang = nama file
                if not entry.lower().endswith(valid_ext):
                    continue
                nama_orang = os.path.splitext(entry)[0]
                foto_list = [entry_path]

            foto_valid = 0
            for img_path in foto_list:
                img = cv2.imread(img_path)
                if img is None:
                    dilewati.append((img_path, "gagal dibaca"))
                    continue

                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                # Cari lokasi wajah dulu, lalu encode
                locations = face_recognition.face_locations(rgb_img)
                if len(locations) == 0:
                    dilewati.append((img_path, "wajah tidak terdeteksi"))
                    continue

                encodings = face_recognition.face_encodings(rgb_img, locations)

                # Kalau ada >1 wajah, ambil wajah terbesar (paling depan)
                if len(locations) > 1:
                    areas = [
                        (bottom - top) * (right - left)
                        for (top, right, bottom, left) in locations
                    ]
                    idx = int(np.argmax(areas))
                    dilewati.append(
                        (img_path, f"ada {len(locations)} wajah, dipakai yang terbesar")
                    )
                else:
                    idx = 0

                self.known_face_encodings.append(encodings[idx])
                self.known_face_names.append(nama_orang)
                foto_valid += 1
                total_foto += 1

            if foto_valid > 0:
                total_orang += 1
                print(f"  - {nama_orang}: {foto_valid} foto ter-encode")
            elif foto_list:
                print(f"  - {nama_orang}: TIDAK ada foto valid (dilewati)")

        print(f"{total_foto} foto dari {total_orang} orang selesai di-encode.")
        if dilewati:
            print("Catatan foto yang dilewati:")
            for path, alasan in dilewati:
                print(f"  - {os.path.relpath(path, images_path)} ({alasan})")

    def detect_known_faces(self, frame):
        small_frame = cv2.resize(frame, (0, 0), fx=self.frame_resizing, fy=self.frame_resizing)
        
        # Konversi warna dari BGR (OpenCV) ke RGB (face_recognition)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        face_names = []
        for face_encoding in face_encodings:
            # Cek kecocokan wajah
            matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding)
            name = "Unknown"

            # Gunakan jarak wajah terdekat untuk akurasi lebih baik
            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
            if len(face_distances) > 0:
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    name = self.known_face_names[best_match_index]

            face_names.append(name)

        # Kembalikan koordinat wajah ke ukuran asli frame
        face_locations = np.array(face_locations)
        face_locations = face_locations / self.frame_resizing
        return face_locations.astype(int), face_names