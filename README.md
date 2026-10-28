# Meeting Room Booking

Aplikasi Flask untuk mencatat booking dua ruang meeting kantor. Semua jam memakai WIB (Asia/Jakarta).

## Menjalankan di server Linux

Dari folder proyek:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/gunicorn --bind 127.0.0.1:8000 app:app
```

Lalu buka http://127.0.0.1:8000 di komputer server. Server berhenti kalau terminalnya ditutup. Untuk jalan terus, pasang sebagai service (systemd atau sejenisnya) dan tambahkan reverse proxy sendiri.

Variabel lingkungan yang bisa diatur:

- `SECRET_KEY`: kunci sesi Flask. Isi dengan nilai acak yang tetap di server.
- `DATABASE_URL`: alamat database SQLAlchemy. Default-nya `sqlite:///meeting_room.db`, yang tersimpan di `instance/meeting_room.db`.
- `FLASK_DEBUG=1`: menyalakan mode debug saat menjalankan `python app.py`. Pakai hanya untuk pengembangan.

## Cara pakai

Halaman Jadwal membuka tanggal hari ini sebagai papan dengan satu kolom per ruangan. Bagian atas tiap kolom menunjukkan apakah ruangan sedang dipakai dan sampai jam berapa. Di bawahnya ada booking hari itu, diselingi jam kosong. Klik jam kosong untuk membuka form dengan ruangan dan jam yang sudah terisi, atau klik booking untuk melihat detail, mengubah, atau membatalkannya. Pindah hari dengan tombol panah atau pemilih tanggal. Tombol Tabel menampilkan booking hari itu sebagai tabel.

Halaman Semua booking berisi booking dari semua tanggal, 20 per halaman, dengan filter per ruangan. Kolom pencarian di bagian atas setiap halaman mencari nama pemesan atau supplier di semua tanggal.

Booking yang bersambung (misalnya 09:00–10:00 lalu 10:00–11:00) boleh. Booking yang jamnya bertabrakan di ruangan yang sama ditolak, dan pesan errornya menyebut siapa yang sudah memakai ruangan itu. Jam selesai harus setelah jam mulai di hari yang sama.

## Tes

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/js/app.js
```

Tes memakai database sementara, jadi data di `instance/meeting_room.db` tidak tersentuh.
