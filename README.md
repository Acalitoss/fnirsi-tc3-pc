<p align="center">
  <img src="assets/retro-saver-logo.png" alt="Retro Saver" width="520">
</p>

# FNIRSI DSO-TC3 PC

DSO-TC3 V0.3 için deneysel PC osiloskop arayüzü ve USB firmware yaması. Python/Tkinter arayüzü cihazın ekran düzenini izler; ölçüm değerlerini doğrudan cihazdan okur ve ayar değişikliklerini cihazdan geri okuyarak doğrular.

**Durum: erken deneysel sürüm.** Bir Windows bilgisayar ve bir DSO-TC3 V0.3 üzerinde test edildi. FNIRSI'nin resmî yazılımı değildir. Firmware değiştirmek cihazı çalışmaz hâle getirebilir. Voltaj ölçümleri bağımsız bir ölçüm cihazına göre kalibre edilmiş değildir.

## Özellikler

- USB üzerinden 600 imzalı örnek sözcüğünü okuma; cihazın tetik konumuna göre 300 noktalı görünüm.
- Cihazın Vmax, Vmin, Vavg, Vrms, Vpp, frekans, görev oranı ve periyot alanlarını görüntüleme.
- V/div, prob, zaman tabanı, AC/DC ve tetik ayarları için PC kontrolleri.
- Cihaz RUN/HOLD kontrolü ve CSV dışa aktarma.
- Orijinal üretici dosyasından yeniden üretilebilen firmware yaması; depoda üretici firmware'i bulunmaz.

Gerçek cihazda doğrulanan kontroller: **V/div, zaman tabanı ve RUN/HOLD**. Diğer kontroller uygulanmıştır ancak aynı kapsamda fiziksel doğrulamadan geçmemiştir.

## PC uygulamasını kurma

Python 3.10 veya üstü ve Tkinter gerekir. Windows Python kurulumunda Tcl/Tk bileşenini seçin. Depo klasöründe:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m fnirsi_tc3 --connect
```

Alternatif: `fnirsi-tc3 --connect`. Arayüzde doğru seri portu seçin; örnek cihaz COM7 olarak tanındı. Uygulama arayüzü Türkçedir.

**Stok V0.3 firmware canlı ölçüm ve PC kontrolünü desteklemez.** Bu işlevler aşağıdaki deneysel yamanın cihaza yüklenmesini gerektirir. Uygulama stok cihazdan yalnızca mevcut yapılandırma sorgusunu okuyabilir.

## Firmware yamasını oluşturma

1. Üreticinin [indirme sayfasından](https://www.fnirsi.com/pages/manuals-firmwares) DSO-TC3 Firmware V0.3 paketini indirin ve çıkarın.
2. Bağımlılıkları yükleyin ve `.s19` dosyasını girdi olarak verin:

```powershell
python -m pip install -e ".[firmware]"
python scripts/build_patch.py --firmware "vendor/DSO-TC3_V0.3.s19"
```

Oluşturucu yalnızca SHA-256 değeri `9a97d5bb1a5864af6484b92f115ae827e16e3972f5ec8828362c358ba2430b61` olan dosyayı kabul eder. Başka sürüm veya donanım revizyonuna zorlamayın. Çıktılar `build/` içinde oluşur ve Git tarafından dışlanır.

Oluşturulan dosya SHA-256: `97c601b5c02b2169e51275a6b5e7328f2919d3101c6a53bbdf8807274eb5c5ac`.

## Yükleme

Önce orijinal V0.3 dosyasını saklayın. PC görüntüleyicisini kapatın. Cihazı kapatıp **▼ + güç** ile `Bootloader OK` ekranına geçin. Depo kökünde:

```powershell
python scripts/flash.py --image build/DSO-TC3_V0.3_USB_EXPERIMENTAL.s19
```

Yükleyici USB kimliği `19F5:5740` olan tek cihazı seçer. Gerekirse `--port COM7` belirtin. Stok yapılandırma yanıtını bootloader yanıtı olarak kabul etmez. Tüm paketler onaylansa bile açılış ve ölçüm doğrulaması ayrıca gereklidir.

Yüklemeden sonra güç tuşuyla açıp osiloskop ekranına geçin. Ardından PC uygulamasını başlatın. Kurtarma için bootloader açılabiliyorsa aynı yükleyiciye orijinal üretici `.s19` dosyası verilebilir.

## Kullanım ve sınırlar

Alt ölçek kutularına tıklayın veya seçim listelerinden ayar değiştirin. PC, cihazın tuş olayını işlemesini bekler ve ayarı geri okur; yalnızca komut onayını başarı saymaz. PC duraklatma düğmesi yalnızca görüntüleyiciyi durdurur; alt RUN/HOLD kutusu cihazın durumunu değiştirir.

- Gerilim rakamları DSO-TC3'ün hesapladığı değerlerdir; laboratuvar güç kaynağının ayarı değildir. Güç kaynağı bu uygulamaya bağlı veya uygulama tarafından kontrol ediliyor değildir.
- Örnek sözcükleri ham ADC kodu değil, firmware'in hesapladığı ekran düşey yer değiştirme değerleridir. CSV bunları `display_displacement` olarak saklar.
- Sayfalar ardışık okunur; atomik kare aktarımı yoktur. Tutarlı durağan kayıt için cihaz HOLD kullanılabilir.
- Yüksek frekanslı AC doğruluğu, frekans/görev ölçümleri ve gecikme sınırları bağımsız olarak doğrulanmadı.
- Firmware paketinin dış doğrulama alanları tamamen çözülemedi; orijinal başlık korunur. Yama bu tek cihazda başarıyla yüklenip çalıştırıldı.

## Geliştirme ve test

```powershell
python -m unittest discover -s tests -v
```

Donanım gerektirmeyen testler paket ayrıştırmasını, işaretli örnekleri, ölçüm ofsetlerini ve aktarım çerçevelerini kontrol eder. GitHub Actions bu testleri Windows ve Linux'ta çalıştırır; bu, Linux üzerinde gerçek cihaz desteğinin doğrulandığı anlamına gelmez.

Firmware testleri için üretici dosyası ve ek bağımlılıklar gerekir:

```powershell
$env:TC3_STOCK_FIRMWARE = (Resolve-Path 'vendor/DSO-TC3_V0.3.s19').Path
python -m unittest discover -s tests -v
```

[Protokol ve bellek haritası](docs/PROTOCOL.md) · [Katkı yönergeleri](CONTRIBUTING.md) · [Lisans](LICENSE)

MIT lisansı yalnızca bu projedeki koda uygulanır. FNIRSI firmware'i, güncelleme programı, marka ve ürün adları kendi hak sahiplerine aittir.
