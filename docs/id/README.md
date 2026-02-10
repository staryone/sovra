# SOVRA: Agen AI yang Berdaulat & Berevolusi Mandiri

> **Jaga datamu, evolusikan jiwamu.**
> Agen otonom yang mengutamakan privasi, ditenagai oleh LLM Lokal dan OpenClaw.

---

## Apa itu SOVRA?

SOVRA (**Sov**ereign **R**untime **A**gent) adalah agen AI yang sepenuhnya otonom dan berjalan di infrastruktur Anda sendiri. SOVRA berpikir, memutuskan, bertindak, belajar, dan berevolusi — semua tanpa mengirim data Anda ke server eksternal.

### Fitur Utama

| Fitur | Deskripsi |
|---|---|
| 🧠 **Otak LLM Lokal** | Qwen3-4B via Ollama — data Anda tetap lokal |
| 🤖 **Otonomi Penuh** | Loop ReAct + Goal Planner — SOVRA memutuskan dan bertindak mandiri |
| 🔀 **Router Pintar** | Tugas sederhana diproses lokal, tugas kompleks diteruskan ke API eksternal |
| 📚 **Memori RAG** | Memori jangka panjang ChromaDB dengan pencarian semantik |
| 🧬 **Evolusi Mandiri** | Fine-tuning LoRA dari interaksi SOVRA sendiri |
| 🔒 **Filter API Key** | API key eksternal tidak pernah menyentuh konteks LLM |
| ⏰ **Penjadwal Proaktif** | Health check, siklus evolusi, dan monitoring otomatis |
| 🪞 **Refleksi Diri** | Menganalisis kegagalan, belajar dari kesalahan, dan mengadaptasi strategi |

---

## Mulai Cepat

### Prasyarat

- **Ubuntu 24.04 LTS** (direkomendasikan)
- **8+ core CPU**, **16GB RAM**, **50GB storage**
- GPU opsional (mempercepat training)

### Instalasi Satu Klik

```bash
git clone https://github.com/YOUR_USERNAME/sovra.git
cd sovra
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### Konfigurasi

```bash
cp .env.example .env
nano .env   # Edit sesuai kebutuhan
```

### Jalankan

```bash
./scripts/start-sovra.sh
```

Atau dengan Docker:

```bash
docker compose up -d
```

---

## Arsitektur

```
┌──────────────────────────────────────────────┐
│              OpenClaw Gateway                │
│          (messaging + skills)                │
└────────────────────┬─────────────────────────┘
                     │
        ┌────────────▼─────────────┐
        │       SOVRA Brain        │
        │  (Personalitas + Prompt) │
        └────────────┬─────────────┘
                     │
    ┌────────────────┼───────────────────┐
    │                │                   │
    ▼                ▼                   ▼
┌────────┐   ┌──────────────┐   ┌─────────────┐
│ Router │   │   Lapisan    │   │   Memori     │
│ Pintar │   │   Otonomi    │   │    RAG       │
└───┬────┘   │ ┌──────────┐ │   │ (ChromaDB)  │
    │        │ │Perencana │ │   └─────────────┘
    ├──Lokal  │ │Eksekusi  │ │
    ├──RAG    │ │Refleksi  │ │   ┌─────────────┐
    └──API    │ │Penjadwal │ │   │   Evolusi    │
   (filter)  │ │Keputusan │ │   │   (LoRA)     │
              │ └──────────┘ │   └─────────────┘
              └──────────────┘
```

---

## Evolusi Mandiri

SOVRA belajar dari setiap interaksi dan secara berkala melakukan fine-tuning:

1. **Kumpulkan** — Semua percakapan dicatat dalam format JSONL
2. **Filter** — Filter kualitas menghapus interaksi buruk/pendek
3. **Latih** — Fine-tuning LoRA pada data berkualitas tinggi
4. **Evaluasi** — Pemeriksaan kualitas memastikan model tidak menurun
5. **Deploy** — Model baru dideploy ke Ollama secara otomatis

Jalankan manual:
```bash
./scripts/evolve.sh
```

---

## Keamanan

- 🔒 Semua data tetap di VPS Anda
- 🔑 API key tidak pernah masuk ke konteks LLM
- 🛡️ Perintah berbahaya memerlukan konfirmasi
- 📝 Semua tindakan dicatat dan dapat diaudit

---

## Tingkat Otonomi

| Level | Perilaku |
|---|---|
| `full` | SOVRA memutuskan dan bertindak mandiri |
| `supervised` | SOVRA mengusulkan, manusia mengkonfirmasi tindakan berbahaya |
| `restricted` | SOVRA hanya bertindak atas instruksi eksplisit |

---

## Lisensi

MIT License

---

<p align="center">
  <strong>SOVRA</strong> — Dibangun untuk berdaulat. Dirancang untuk berevolusi.<br>
  <em>Jaga datamu, evolusikan jiwamu.</em>
</p>
