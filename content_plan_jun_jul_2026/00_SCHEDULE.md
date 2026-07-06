# Jadwal Konten — Akhir Juni - Juli 2026

Cadence: Minggu + Rabu, 07:00 WIB (20:00 ET). Lanjutan langsung setelah Poseidon (Rabu, 24 Juni).

**Update 2026-06-19:** cadence dinaikkan ke 3x/minggu (Minggu + Rabu + **Jumat baru**), lihat `PUBLISH_WEEKDAYS` di `agents/upload_agent.py`. Tabel tanggal di bawah ini disusun sebelum perubahan ini — `_next_publish_time()` di kode otomatis menyesuaikan slot Jumat baru saat scheduler jalan, jadi tanggal-tanggal di tabel akan bergeser lebih cepat dari yang tertulis.

| Tanggal | Topik | Catatan |
|---|---|---|
| Minggu, 28 Jun | Demeter | urutan normal |
| Rabu, 1 Jul | Hermes | urutan normal |
| Minggu, 5 Jul | Athena | tokoh populer |
| Rabu, 8 Jul | Apollo | tokoh populer |
| Minggu, 12 Jul | Aphrodite | tokoh populer, sebelum gelombang Odyssey |
| **Rabu, 15 Jul** | **Odysseus** | 2 hari sebelum film "The Odyssey" (Nolan) rilis 17 Jul — tangkap antisipasi |
| **Minggu, 19 Jul** | **Penelope** *(topik baru)* | 2 hari setelah rilis — tangkap lonjakan pencarian, terhubung ke karakter Anne Hathaway |
| Rabu, 22 Jul | Hades | tokoh populer |
| Minggu, 26 Jul | Persephone | pasangan naratif Hades |
| Rabu, 29 Jul | Hephaestus | pengisi |

File per topik ada di folder ini, nama `01_demeter.txt` dst — isinya: prompt gambar isi-video (Flow) + prompt thumbnail + teks overlay.

**Update 2026-06-23 — struktur judul & overlay baru (copy dari kompetitor "THEY VANISHED" style):**
- TITLE (YouTube): sekarang format curiosity-question — "Why [Character] [Konflik Spesifik] for Sleep | [Mythology] Bedtime Story" (lihat `agents/metadata_agent.py` TITLE rules). Tetap wajib "for Sleep" + tipe mitologi di 48 char pertama.
- HOOK (baru): field terpisah, 2-4 kata ALL CAPS, satu-satunya teks topik yang dirender di thumbnail (ganti subtitle panjang versi lama yang dulu pakai full title). Auto-generated oleh `metadata_agent.py`, dipakai otomatis oleh `scheduler.py` → `create_thumbnail()`. Font/size/style render tetap sama, cuma teksnya yang lebih pendek & punchy.
- Brand headline "Ancient Mythology for Sleep" tetap fixed, tidak berubah.
- Thumbnail prompt untuk topik yang belum diproduksi (Apollo, Aphrodite, Odysseus, Penelope, Hades, Persephone, Hephaestus) sudah direvisi: painterly tetap, tapi semua elemen dark/night/cool-tone diganti warm/daylight/golden — termasuk Hades & Persephone yang awalnya underworld gelap, sekarang warm amber-gold glow.

Playlist: semua otomatis masuk "Greek Mythology Sleep Stories" (playlist_ids.json sudah benar, gak perlu diubah).
