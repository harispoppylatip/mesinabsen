import cv2
from simple_facerec import SimpleFacerec

# Inisialisasi dan load foto dari folder "images/"
# Struktur yang didukung:
#   images/haris/01.jpg, images/haris/02.jpg  -> satu folder per orang (banyak foto, lebih akurat)
#   images/haris.jpg                          -> file langsung (nama file = nama orang)
sfr = SimpleFacerec()
sfr.load_encoding_images("images/")

# Load Kamera (Gunakan 0 untuk webcam bawaan laptop, atau 1/2 jika menggunakan kamera eksternal/kamera HP)
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Deteksi Wajah
    face_locations, face_names = sfr.detect_known_faces(frame)
    
    for face_loc, name in zip(face_locations, face_names):
        y1, x1, y2, x2 = face_loc[0], face_loc[1], face_loc[2], face_loc[3]

        # Tampilkan nama di atas kotak wajah
        cv2.putText(frame, name, (x1, y1 - 10), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 0, 200), 2)
        # Gambar kotak di sekeliling wajah
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 200), 4)

    # Tampilkan jendela video
    cv2.imshow("Face Recognition - Live", frame)

    # Tekan tombol 'ESC' (kode 27) untuk keluar dari program
    key = cv2.waitKey(1)
    if key == 27:
        break

cap.release()
cv2.destroyAllWindows()