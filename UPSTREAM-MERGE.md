# armel (upstream) güncellemelerini `sat-track` dalına alma

Bu dosya, `sat-track` dalını armel'in ana deposuyla güncellerken izlenecek yolu
anlatır. Komutlar PowerShell (Windows) içindir; Bash karşılıkları aynıdır.
Amaç: her seferinde aynı hataları yapmadan, ABI'yi bozmadan merge etmek.

---

## 1. Depo topolojisi

| Remote | URL | Rol |
|---|---|---|
| `origin` | `3geETR/uv-k1-k5v3-firmware-custom` | Kendi forkun. Push buraya yapılır. |
| `upstream` | `armel/uv-k1-k5v3-firmware-custom` | Ana kaynak. Güncellemeler buradan gelir. |
| `gomes89` | `gomes89/uv-k1-k5v3-firmware-custom` | Reddedilen PR'ın sahibi. Sadece referans; push edilmez. |

Dallar:

- `main` — gomes89'un `main`'i, armel'in eski bir sürümünün aynası.
- `sat-track` — Sat Track özelliği + armel güncellemeleri. Çalışma dalı budur.

Doğrulama:

```powershell
git remote -v
git branch -vv          # sat-track -> origin/sat-track izlemeli
```

---

## 2. İlk kurulum (yeni bir klonda bir kez)

```powershell
git remote add upstream https://github.com/armel/uv-k1-k5v3-firmware-custom.git

# origin yanlışlıkla gomes89'u gösteriyorsa:
git remote rename origin gomes89
git remote add origin https://github.com/3geETR/uv-k1-k5v3-firmware-custom.git

git fetch origin
git fetch upstream --tags
git branch --set-upstream-to=origin/sat-track sat-track
```

---

## 3. Rutin güncelleme akışı

```powershell
git switch sat-track
git fetch upstream --tags

# Ne geliyor? (merge'den önce bak)
git log --oneline sat-track..upstream/main
git diff --stat sat-track...upstream/main

git merge upstream/main
```

- Çakışma yoksa doğrudan commit oluşur → 5. bölüme geç.
- Çakışma varsa 4. bölümdeki dosya bazlı kuralları uygula.

Deneme merge'i (dalı bozmadan önce görmek için):

```powershell
git worktree add ..\merge-test -b merge-test sat-track
cd ..\merge-test
git merge upstream/main
# incele; iş bitince:
cd ..
git worktree remove --force ..\merge-test
git branch -D merge-test
```

---

## 4. Çakışma çözüm kuralları

### 4.1 `App/apps/app_api.h` — **en kritik dosya**

`app_api_t` **append-only** bir ABI'dir. Uygulamalar firmware'den ayrı derlenir ve
servisleri sabit bayt ofsetleriyle çağırır. Bu yüzden:

1. **Alanların sırasını değiştirme, araya alan sokma, offset kaydırma.**
2. armel'in level tanımını ve struct'ını **aynen koru**.
3. Sat Track köprüsünü (`crc16`, `format`, `sat_*`) armel'in **son alanından
   sonra** ekle.
4. `APP_API_LEVEL` değerini armel'in seviyesinin **bir fazlası** yap.
5. `_Static_assert` offset'lerini güncelle.

> **Tuzak:** armel'in assert bloğu `sizeof(app_api_t) == 396u` ile biter. Sat
> bloğunu eklediğinde yapı 440 bayt olur; bu satırı **olduğu gibi bırakırsan
> derleme `action.c` içinde "static assertion failed" ile durur.** armel'in
> bloğunda yalnızca alan offset'lerini bırak, `sizeof` kontrolünü yeni level-4
> assert'ine taşı (aşağıdaki gibi).

Mevcut durum (v6.3.0 merge'i sonrası):

| Öğe | Değer |
|---|---|
| `APP_API_LEVEL` | `4u` |
| armel level-3 bloğunun boyu | 396 bayt |
| `offsetof(app_api_t, crc16)` | 396 |
| `offsetof(app_api_t, sat_read)` | 404 |
| `sizeof(app_api_t)` | 440 |
| `APP_CAP_SAT` | `0x00000080u` |

Sat bloğu 11 pointer'dır (`crc16`, `format`, `sat_read`, `sat_enter`, `sat_tune`,
`sat_rx`, `sat_tick`, `sat_ptt`, `sat_leave`, `sat_squelch`, `sat_power`) =
44 bayt. Yeni bir armel seviyesi gelirse:

```c
/* örnek: armel level 4 ekledi, sat level 5 olur */
#define APP_API_LEVEL  5u
...
    bool (*armel_yeni_servis)(...);   /* armel'in son alanı */
    /* sat bloğu buradan sonra */
    uint16_t (*crc16)(const void *buf, uint16_t len);
...
/* armel'in bloğunda sizeof(...) satırı KALMAZ, sadece alan offset'leri: */
_Static_assert(offsetof(app_api_t, handoff) == 356u &&
               ...
               offsetof(app_api_t, vfo_stage) == 392u,
               "level 3 prefix offsets must not move");

/* boyut kontrolü sat bloğunun sonunda: */
_Static_assert(offsetof(app_api_t, crc16) == 396u &&
               offsetof(app_api_t, sat_read) == 404u &&
               offsetof(app_api_t, sat_power) == 436u &&
               sizeof(app_api_t) == 440u,
               "the Sat Track bridge must stay after the level-3 layout");
```

> `APP_ABI_MAJOR` yalnızca köklü/uyumsuz bir ABI değişikliğinde artırılır;
> normal eklemelerde `1u` kalır.

### 4.2 `App/apps/app_overlay.h` — yetenek bitleri

`APP_CAP_*` bitleri **benzersiz** olmalı. armel yeni bir bit aldığında sat bitini
boş bir bit'e taşı (şu an `APP_CAP_SERIAL = 0x40`, `APP_CAP_SAT = 0x80`).

```c
#define APP_CAP_SERIAL        0x00000040u
#define APP_CAP_SAT           0x00000080u
```

### 4.3 `App/apps/app_overlay.c`

İki yer:

1. `APP_AVAILABLE_CAPS` — iki `#ifdef` bloğu da dursun:
   ```c
   #ifdef APP_SERIAL
                          | APP_CAP_SERIAL
   #endif
   #ifdef ENABLE_FEAT_F4HWN_OVERLAY_SAT
                          | APP_CAP_SAT
   #endif
   ```
2. `app_api` tablosu — önce armel'in tüm alanları, **en sonda** sat alanları:
   ```c
   #ifdef ENABLE_FEAT_F4HWN_OVERLAY_BEAM
       .vfo_stage           = app_vfo_stage,
   #endif
       /* API level 4 */
       .crc16               = CRC_Calculate,
       .format              = snprintf_,
   #ifdef ENABLE_FEAT_F4HWN_OVERLAY_SAT
       .sat_read            = app_sat_read,
       ...
   #endif
   };
   ```
   `app_launch()` içindeki `app_sat_leave()` çağrısını ve armel'in eklediği
   temizlik çağrılarını (`app_af_capture_close()`, `app_serial_release()`) **ikisini
   de** koru.

### 4.4 `App/apps/pack_app.py`

`CAPABILITIES` sözlüğünde iki satır da bulunsun:

```python
"serial": cdefine("app_overlay.h", "APP_CAP_SERIAL"),
"sat":    cdefine("app_overlay.h", "APP_CAP_SAT"),
```

### 4.5 `README.md`

Uygulama listesi ve sayısı iki tarafta da değişir. armel'in listesini al, Sat
Track'i "radio tools" satırına ekle, sayacı armel'in sayısının bir fazlası yap.

### 4.6 `App/apps/sat/build.sh`

Sat Track, sat köprüsünü kullandığı için `APP_API_MIN` **daima** `APP_API_LEVEL`
ile aynı olmalı:

```bash
APP_API_MIN=4                       # sat_* bridge (API level 4)
```

### 4.7 Değişmemesi gerekenler

- `App/app/uart.c` içindeki `0x0740`–`0x0747` Sat Track komutları (pass store) ve
  `VCP_ReadIndex`'in `static` olmaması.
- `App/driver/mb_flash.h`'deki yerleşim: app slotları `0x102000`–`0x162000`,
  Sat Track store `0x162000`–`0x173000`, Sonic rezervi `0x1DE000`'den başlar.
- `App/apps/sat/sat_format.h` sabitleri (`SAT_STORE_BASE` vb.).
- `App/apps/sat/{sat_app.c,sat_format.h,app.ld,build.sh}` — çakışma çıkarsa
  genelde sat tarafı korunur, API alan adları değişmediği sürece.

---

## 5. Doğrulama

### 5.1 Hızlı kontroller (derleme gerektirmez)

```powershell
git status -sb
git grep -n "<<<<<<<"
git diff --check
python -m py_compile App/apps/pack_app.py
python -c "import json;json.load(open('CMakePresets.json'))"
```

`#if/#endif` dengesi bozulmuş mu (kaba kontrol):

```powershell
python -c "import re;f='App/app/uart.c';n=sum(1 for l in open(f) if re.match(r'\s*#\s*(if|ifdef|ifndef)\b',l));o=sum(1 for l in open(f) if re.match(r'\s*#\s*endif\b',l));print(f,n,o)"
```

`app_api.h` sentaks kontrolü (Windows'ta WSL + gcc ile):

```powershell
wsl -e bash tools/check-api-header.sh
```

> Bu script önce `-m32` ile derlemeyi dener: başarılıysa `app_api.h` içindeki
> `_Static_assert` offset/boyut kontrolleri **gerçekten** çalışır. `-m32` yoksa
> yalnızca sentaks kontrolü yapar ve uyarır; o durumda offset doğrulaması için
> gerçek ARM derlemesi (Docker/CI) şarttır.

### 5.2 Gerçek derleme

Makinede `arm-none-eabi-gcc`, `cmake`, `ninja`, `docker` yoksa:

- GitHub → **Actions → Build Firmware → Run workflow** (workflow `sat-track`
  push'unda otomatik tetiklenmez, manuel çalıştırılmalı).

Docker varsa:

```bash
./compile-firmware.sh All
./compile-app.sh All
```

Beklenenler:

- `f4hwn.labs` presetinde `ENABLE_FEAT_F4HWN_OVERLAY_SAT=ON`.
- `SatTrack.app` 4 KiB sınırını aşmamalı.
- Uygulama menüsünde Sat Track görünmeli; `pack_app.py` `--require sat` kabul
  etmeli (`APP_CAP_SAT` okunabilir olmalı).

---

## 6. Push

```powershell
git push origin sat-track
```

`origin` = kendi forkun. `sat-track` için upstream izlemesi `origin/sat-track`
olmalı (`git branch -vv` ile doğrula).

---

## 7. Geri alma

| Durum | Komut |
|---|---|
| Merge sürüyor, vazgeç | `git merge --abort` |
| Merge commit'lendi, push edilmedi | `git reset --hard ORIG_HEAD` |
| Push edildi | `git revert -m 1 <merge-commit>` |
| Deneme worktree'si kaldı | `git worktree remove --force ..\merge-test` |

`ORIG_HEAD`, merge'den hemen önceki ucu gösterir. Emin değilsen önce
`git reflog` ile kontrol et.

---

## 8. Kayıt defteri

| Tarih | upstream ucu | Gelen | Sonuç | Merge commit |
|---|---|---|---|---|
| 2026-10-23 | `631eb5c6` (v6.3.0 + 1) | 92 commit | API level 4, `APP_CAP_SAT=0x80`, `APP_API_MIN=4` | `04ff048f` |

Yeni bir merge yaptığında bu tabloya bir satır ekle.

---

## 9. Sorun giderme: "NO PASSES" ama PC 16 pass görüyor

Bu, **radyo boş değil** demektir: `sattrack.py radio` pass'leri okuyabiliyorsa
store ve UART yolu sağlam. Neredeyse her zaman sebep, radyoya **merge öncesi
derlenmiş eski `SatTrack.app`** kurulmuş olmasıdır:

| | Eski app (API level 3) | Yeni firmware (v6.3.0) |
|---|---|---|
| ofset 328 | `crc16` | `append_i32` |
| ofset 336 | `sat_read` | `af_capture_sample` |
| ofset 364 | `sat_squelch` | `tx_prepare` |
| ofset 404 | — | `sat_read` (doğru yer) |

Eski app `sat_read` yerine `af_capture_sample` çağırır; tampon hiç dolmaz,
indeksin `magic` alanı sıfır kalır ve uygulama "NO PASSES" çizer. Firmware bunu
yakalayamaz: eski app'in `required_caps` değeri `0x40` (eski `APP_CAP_SAT`),
yeni firmware'de bu bit artık `APP_CAP_SERIAL`'dır.

Çözüm:

```powershell
./compile-app.sh sat            # veya CI'da "Build Firmware" -> Run workflow
uv run tools/sattrack/sattrack.py install build/Apps/SatTrack.app
```

Kurulan dosyanın yeni olduğunu doğrula (`api_min` 4, sat yeteneği 0x80):

```powershell
$b=[IO.File]::ReadAllBytes('build/Apps/SatTrack.app')
"api_min=$($b[7])  sat_cap=$((($b[56] -band 0x80) -ne 0))"
```

`api_min=4` ve `sat_cap=True` değilse yanlış/eski blob kuruluyor demektir.
Menüdeki **8 Install the app on the radio** da varsayılan olarak
`build/Apps/SatTrack.app` dosyasını kullanır.

Yeni app, uyumsuz bir firmware'de çalıştırılırsa artık "NO PASSES" yerine
**UPDATE APP / REINSTALL** gösterip EXIT bekler (`app_main` başındaki
`api_size`/`api_level` kontrolü). Yine de eski app'i firmware tarafında ayırt
etmenin güvenilir bir yolu yoktur; doğru app'i yeniden kurmak gerekir.

---

## 10. Sık yapılan hatalar

- **`app_api.h`'de "ours/theirs" ile dosyayı komple almak.** Alanlar kayar,
  uygulama yanlış adresi çağırır; genelde reset/çökme olarak görünür.
- **`APP_CAP_SAT` ile armel'in yeni bitini çakıştırmak.** Loader uygulamayı
  `APP_ERR_CAP` ile reddeder ya da yanlış yetenek verir.
- **`APP_API_LEVEL`'ı artırmayı unutmak.** Eski seviyeyle paketlenen Sat Track,
  yeni alanları çağırdığı için yanlış ofsete gider.
- **`sat/build.sh` içindeki `APP_API_MIN`'i güncellememek.** Loader
  `APP_ERR_ABI` verir.
- **`main`'e push edip CI beklemek.** Workflow yalnızca `main` push'unda ve
  manuel tetiklemede çalışır.
- **CRLF.** `build.sh` dosyaları Bash ile çalışır; `.gitattributes` ayarlarını
  bozmamak gerekir.
