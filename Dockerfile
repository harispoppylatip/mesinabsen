# Layanan wajah untuk absen wajah aplikasi sekolah.
#
# Dibangun di atas python:3.12-slim karena versi Python itulah yang sudah
# teruji di mesin pengembang. Modul dlib dipasang dari roda siap pakai
# (dlib-bin) supaya tidak perlu mengompilasi dlib dari sumber, yang bisa
# makan belasan menit dan menuntut cmake beserta perkakas build.
#
# Penjelasan keputusan ini ada di README bagian "Kenapa memakai dlib-bin".

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libgomp1 dan libstdc++6 dibutuhkan roda dlib saat dijalankan.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt ./

# Pemasangan dipecah dua langkah, dan langkah kedua sengaja memakai --no-deps.
#
# Paket face-recognition menuliskan "dlib>=19.7" sebagai syarat, padahal
# distribusi dlib di PyPI hanya tersedia sebagai berkas sumber. Tanpa
# --no-deps, pip akan mengunduh dlib dari sumber dan mengompilasinya, padahal
# modul dlib sudah disediakan oleh dlib-bin pada langkah pertama.
#
# Karena dependensi paket itu tidak ikut terpasang, seluruh kebutuhan lainnya
# (numpy, pillow, click, face-recognition-models) sudah didaftarkan di
# requirements.txt.
ARG FACE_RECOGNITION_VERSION=1.3.0
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps "face-recognition==${FACE_RECOGNITION_VERSION}" \
    && python -c "import dlib, face_recognition, face_recognition_models; print('modul wajah siap dipakai')"

COPY face_service.py enroll_faces.py ./

# Dijalankan sebagai pengguna biasa, bukan root, supaya berkas yang mungkin
# ditulis skrip pendaftaran tidak menjadi milik root di komputer ini.
RUN useradd --create-home --uid 10001 layanan \
    && mkdir -p /srv/images \
    && chown -R layanan:layanan /srv

USER layanan

# 0.0.0.0 wajib di dalam kontainer supaya layanan bisa dihubungi dari luar
# kontainer. Siapa saja di luar yang boleh masuk diatur oleh bagian "ports"
# di docker-compose.yml, bukan oleh nilai ini.
ENV FACE_HOST=0.0.0.0 \
    FACE_PORT=5005

EXPOSE 5005

CMD ["python", "face_service.py"]
