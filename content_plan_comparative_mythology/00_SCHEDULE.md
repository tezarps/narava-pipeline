# Jadwal Konten — Comparative Mythology (test track)

Status: BELUM dijadwalkan ke cadence reguler. Ini adalah satu episode percobaan untuk
menguji arah konten baru — perbandingan mitos lintas budaya/agama, disajikan sebagai
mitologi komparatif yang netral (bukan klaim kebenaran satu agama tertentu, bukan
preachy, bukan bikin anxious — ini tetap konten sleep, kontroversinya harus terasa
sebagai keingintahuan intelektual yang tenang, bukan stres).

Kategori baru: `comparative`
Alasan nama: pendek, lowercase, satu kata — konsisten dengan kunci kategori existing
(`greek`, `norse`, `egyptian`, `japanese`, `aztec`, `celtic`). "Comparative" dipilih
daripada "crossmyth" karena lebih jelas mendeskripsikan isi (mitologi yang dibandingkan)
dan lebih natural dipakai di hashtag (`#ComparativeMythology`) serta judul playlist.

Playlist (BELUM dibuat — perlu approval manusia, jangan jalankan setup_playlists.py):
- Title: "Mythology Compared — Sleep Stories"
- Description (gaya konsisten dengan PLAYLISTS di setup_playlists.py — tenang, deskriptif,
  bukan clickbait):
  "The same ancient stories, remembered differently across the world. Slow, comparative
  myths — flood, fire, creation — told side by side without judgment. New episode when
  inspiration strikes."
- Key yang akan dipakai di playlist_ids.json setelah playlist asli dibuat: `comparative`
  (jangan tambahkan key ini ke playlist_ids.json sekarang — itu tindakan live/eksternal,
  biar pemilik channel yang approve dan jalankan sendiri).

| Tanggal | Topik | Catatan |
|---|---|---|
| TBD (standalone test) | The Great Flood | Episode pertama kategori `comparative`. Bukan bagian dari cadence Minggu/Rabu greek-pantheon. Tonton performanya dulu sebelum menentukan apakah kategori ini lanjut jadi seri reguler. |

## Frame device (ringkasan — detail lengkap di 01_great_flood.txt)

Device 2nd-person lama ("kamu melayani dewa X") tidak langsung bisa dipakai karena cerita
ini melintasi 5 budaya berbeda, bukan satu pantheon. Solusi: kamu adalah **Penjaga Arsip
Ingatan** — sosok abadi yang merawat perpustakaan di luar waktu, berisi malam-malam yang
diingat manusia. Malam ini lima rak menyala bersamaan, semuanya menyimpan ingatan tentang
malam banjir besar yang sama. Kamu berpindah dari rak ke rak, mengalami sekilas tiap
ingatan sebagai dirimu sendiri (tetap 2nd person, present tense, sensorik — sesuai brand),
lalu kembali ke keheningan arsip sebagai jangkar di antara segmen.

Urutan 5 tradisi: Mesopotamia (Utnapishtim/Gilgamesh) → Ibrahimik (Nuh/Noah) → Hindu
(Manu & ikan Matsya) → Yunani (Deukalion & Pyrrha) → Tiongkok (Gun-Yu, penanganan
banjir lintas generasi). Throughline sensorik: suara air gemericik, aroma kayu/resin,
dan tekstur berbeda di tangan si Penjaga Arsip (tanah liat, kulit, sutra, marmer, bambu)
di tiap rak — ini jadi jangkar "kamu" yang konsisten meski latar berubah total tiap
segmen. Dibuka dengan rak-rak menyala sendiri tanpa disentuh (penasaran, bukan horor);
ditutup dengan kelima rak meredup bersamaan dan si Penjaga Arsip akhirnya beristirahat.

## Catatan implementasi script_agent.py (jika lanjut ke produksi nyata)

`_DRAFT_PART1` dan `_DRAFT_PART2` saat ini mengasumsikan satu "Category: {category}
mythology" dan satu dewa/peran tunggal sepanjang skrip. Untuk format komparatif, perlu
salah satu dari:
1. Tetap satu call ke generator per part, tapi `angle` diperkaya jadi full frame-device
   outline (seperti di atas) supaya model tahu harus membagi jadi 5 segmen + arsip — risiko:
   kurang kontrol granular per segmen, kualitas tergantung kemampuan model mengikuti
   instruksi panjang.
2. (Disarankan) Tambah mode baru di script_agent.py — generate per-segmen (1 call per
   tradisi + call pembuka/penutup arsip), lalu digabung. Butuh sedikit refactor: parameter
   `segments` berisi list {tradisi, detail_singkat}, loop generate, lalu stitch dengan
   transisi "kamu meredupkan rak ini... rak berikutnya menyala..." Ini belum dikerjakan di
   task ini — baru dicatat sebagai kebutuhan teknis.

Playlist: kategori `comparative` BELUM ada di playlist_ids.json — perlu dibuat manual via
setup_playlists.py (dengan PLAYLISTS list ditambah entry baru) oleh pemilik channel,
bukan oleh agent ini.
