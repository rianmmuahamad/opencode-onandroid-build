# OpenCode Android — prototipe terminal mandiri

Tujuan: pasang APK, buka terminal dalam aplikasi, tunggu setup pertama,
lalu langsung menggunakan OpenCode. Pembukaan berikutnya memakai instalasi
yang sama. Tidak membutuhkan aplikasi Termux terpisah.

**Status: overlay runtime dan persiapan build sudah ditulis. APK belum dibangun
atau diuji pada perangkat Android.** Tes lokal menggunakan simulasi perintah;
hasilnya tidak membuktikan kompatibilitas OpenCode/PRoot pada HP.

## Alur yang dibuat

1. Bootstrap terminal berbasis Termux disertakan dalam APK.
2. Shell login interaktif memanggil `runtime/start.sh` otomatis.
3. Host memasang `proot-distro` dan pengunci sesi bila belum tersedia.
4. Installer membuat container Alpine khusus `opencode-android-alpine`.
5. Di Alpine, pasang Bash, curl, sertifikat, Git, ripgrep, dan library C++.
6. Unduh dan jalankan installer resmi `https://opencode.ai/install`.
7. Jalankan OpenCode di `/root/projects` dengan PTY terminal tetap tersambung.

`proot-distro login ubuntu` dari contoh awal diganti menjadi login ke Alpine
yang memang dipasang. `source ~/.bashrc` diganti dengan PATH eksplisit ke
`$HOME/.opencode/bin`, sehingga tidak bergantung pada isi berkas shell.
Endpoint installer tersebut saat diperiksa menyediakan OpenCode **1**.
OpenCode 2 tidak diganti otomatis ke dalam alur ini.

Installer hanya menandai setup selesai setelah `opencode --version` berhasil.
Kegagalan jaringan tidak menjalankan installer parsial. Membuka ulang aplikasi
mencoba tahap yang belum selesai; container/proyek tidak dihapus otomatis.
Saat sesi lama masih hidup, basis Termux mengelola sesi/PTY yang sama;
pengunci juga mencegah sesi terminal baru menjalankan agent kedua.
Setelah OpenCode keluar, pengguna mendapat shell pemulihan. Jalankan kembali
dengan `bash "$PREFIX/libexec/opencode-android/start.sh"` atau buat sesi baru.

## Batas identitas APK prototipe

Build awal memakai **application ID `com.termux`**, prefix dan paket upstream
Termux. Ini aplikasi yang memuat terminalnya sendiri, bukan APK peluncur.
Tetapi APK ini **tidak dapat hidup berdampingan dengan Termux resmi**.
Tanda tangan debug lokal juga berbeda dari Termux yang sudah terpasang.
Jangan memasangnya sebagai pengganti instalasi Termux yang berisi data kerja.
Gunakan perangkat/emulator uji yang tidak memiliki Termux.

Paket APK sendiri yang dapat hidup berdampingan membutuhkan bootstrap serta
repository paket host yang dibangun untuk prefix baru. Itu belum dikerjakan.
Jangan hanya mengganti application ID: paket upstream memiliki path terkompilasi.

## Build pada komputer dengan Android SDK dan jaringan

Kebutuhan: Linux, Git, Python 3, Java yang cocok dengan Gradle upstream,
Android SDK/NDK/CMake yang diminta oleh tag Termux `v0.118.3`, serta akses
GitHub, Maven dan server distribusi Gradle. Android Studio dapat memasang SDK
yang diminta saat membuka checkout hasil clone.

```bash
export ANDROID_HOME=/lokasi/Android/Sdk
bash tools/build-android.sh
```

Skrip mengambil tag `v0.118.3`, memeriksa commit lengkap
`5b657c6adf4304e5198951ce815fe0205dcac29c`, lalu meminta
Gradle upstream mengunduh serta memverifikasi bootstrap aslinya. Patcher
menambahkan runtime sendiri dan hook interaktif ke `etc/profile`, lalu
memperbarui checksum arsip lokal pada konfigurasi Gradle. Validasi checksum
tetap dijalankan pada build APK. Source upstream asli tidak ditimpa pada repo
pengembang lain: checkout build berada di `build/termux-app`.

Hasil, jika build berhasil: APK debug dan arsip corresponding source di `dist/`.
Build ulang memakai debug key yang sama agar pembaruan tetap cocok. APK debug
ini untuk pengujian; penandatanganan rilis belum dikonfigurasi.

Skrip tidak memasang SDK atau menyetujui lisensi SDK otomatis. Bila Gradle
menyebut komponen SDK belum tersedia, pasang komponen tersebut lalu ulangi.
Tidak ada klaim bahwa build end-to-end telah lolos.

## Pemeriksaan lokal

Alur build cloud juga disiapkan di `.github/workflows/build-apk.yml`. Workflow
dapat dijalankan melalui GitHub Actions setelah kode berada di repository yang
diizinkan pengguna. Ia memasang SDK/NDK sesuai properti tag upstream,
menjalankan tes, membangun APK, lalu menyimpan APK, source, dan checksum sebagai
artifact `opencode-android-apk`. Repository build publik:
https://github.com/rianmmuahamad/opencode-onandroid-build . Status build dapat
dilihat pada tab Actions; keberhasilan build tidak menggantikan pengujian HP.

```bash
python3 -m unittest discover -s tests -v
bash -n runtime/start.sh runtime/guest-run.sh tools/build-android.sh
sh -n runtime/guest-setup.sh runtime/profile-hook.sh
```

Tes mencakup setup sekali, kegagalan unduhan/binary, path dengan spasi,
argumen literal, API instalasi proot-distro lama/baru, penghentian saat gagal,
pengunci sesi, injeksi bootstrap berulang, dan penolakan checksum yang berubah.

## Batas sebelum rilis

- Sasaran uji awal ARM64; x86_64 disediakan untuk emulator. Sistem 32 bit
  ditolak skrip. Persyaratan Android mengikuti basis Termux dan harus diuji.
- Proot-distro modern memakai `alpine:3.23`; implementasi lama memakai plugin
  Alpine yang tersedia. Paket dan versi OpenCode belum dikunci, sehingga hasil
  instalasi antartanggal belum dijamin identik. Belum ada klaim semua Android.
- Belum diuji pada perangkat 16 KB, jaringan terputus, force-stop, rotasi,
  background, provider AI, Git dan eksekusi tool OpenCode pada HP.
- Tidak mengubah API key pengguna. Provider tetap dihubungkan lewat OpenCode.
- Belum ada benchmark RAM, CPU atau startup. Otomasi ini mempermudah setup;
  overhead PRoot tetap ada.
- Upgrade manual paket `termux-tools` bisa mengganti `etc/profile` dan
  menghapus hook autostart. Mekanisme hook yang bertahan saat upgrade belum
  dibuat; pembaruan runtime bukan fitur prototipe ini.
- APK memakai branding teks baru, tetapi ikon dan sebagian UI masih upstream.
- Pengemasan source/lisensi seluruh komponen untuk distribusi publik perlu
  diaudit sebelum rilis. Arsip corresponding source build mempertahankan source
  aplikasi dan file lisensi upstream; dependency yang diunduh terpisah perlu
  dicatat juga.

## Referensi

- [Termux app dan cara build/fork](https://github.com/termux/termux-app)
- [Rilis basis v0.118.3](https://github.com/termux/termux-app/releases/tag/v0.118.3)
- [Bootstrap dan prefix paket](https://github.com/termux/termux-packages/wiki/For-maintainers)
- [PRoot-Distro](https://github.com/termux/proot-distro)
- [Installer OpenCode yang diminta](https://opencode.ai/install)
