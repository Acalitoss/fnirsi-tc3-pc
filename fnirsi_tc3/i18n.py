"""Turkish/English UI strings. Measurements and device data are never translated."""
EN={
 'Ana menü':'Home','Osiloskop':'Oscilloscope','Ayarlar':'Settings','Geri':'Back','Kenar':'Edge','OK / Test':'OK / Test',
 'Mod ve tuş işlemleri cihazdan geri okunur.':'Mode and key operations are read back from the device.',
 'Bu bölümler için çoklu mod firmware v3 gerekiyor.':'These sections require multi-mode firmware v3.',
 'Önce USB bağlantısını başlatın.':'Connect USB first.',
 'Üst menüden bir cihaz bölümü seçin.':'Choose a device section above.',
 'Seçili mod ve değerler USB üzerinden cihazdan okunur.':'Current mode and values are read from the device over USB.',
 '▶ alan / basamak seçer · ◀ geri · ▲/▼ değeri değiştirir. Çıkış cihazdadır.':'▶ selects field / digit · ◀ goes back · ▲/▼ changes value. Output is on the device.',
 'Sensör bekleniyor':'Waiting for sensor','IR sinyali bekleniyor':'Waiting for IR signal',
 'Devamlılık sonucu cihazın sesinden izlenir.':'Monitor continuity using the device buzzer.',
 'Standart 1-2-3 girişi; 0–40 V girişine taşınmadı.':'Standard 1-2-3 input; not rerouted to the 0–40 V input.',
 'Kalibrasyon adımları için cihaz ekranını izleyin.':'Follow calibration steps on the device screen.',
 '▲/▼ araç seçer. Voltaj girişi: 0–40 V. Diğer testler cihazın standart girişlerini kullanır.':'▲/▼ selects tool. Voltage input: 0–40 V. Other tests use the standard device inputs.',
 'Ayrıntılı eleman değerleri cihaz ekranında.':'Detailed component values are on the device screen.',
 'Elemanı 1-2-3 soketine bağlayın. OK / Test ölçümü başlatır.':'Connect the component to the 1-2-3 socket. OK / Test starts measurement.',
 'Cihazın yön ve OK tuşlarını kullanın.':'Use the device direction and OK keys.',

 'Sıfırla':'Reset view','Dalgalanmayı ortala':'Centre ripple',
 'Tekerlek: X zoom · Shift: Y zoom · Sürükle: kaydır':'Wheel: X zoom · Shift: Y zoom · Drag: pan',
 'Başlat':'Connect','HOLD':'Pause PC','CSV kaydet':'Save CSV','Firmware kur':'Install firmware',
 'USB portu:':'USB port:','Prob':'Probe','Zaman/div':'Time/div','Bağlantı':'Coupling','Tetik':'Trigger',
 'Cihazdan henüz örnek alınmadı.':'No samples received from the device yet.',
 'Firmware v2 bekleniyor · Voltaj ölçümleri ve cihaz kontrolü henüz etkin değil.':'Patched firmware required · Voltage readings and device controls are not active yet.',
 'USB bekleniyor · Tek bir DSO-TC3 bağlayın.':'Waiting for USB · Connect one DSO-TC3.',
 'Cihazın hesapladığı voltajlar · Ayarlar cihazdan geri okunur · Güç kaynağını kontrol etmez.':'Device voltage readings · Settings are verified by readback · Does not control the power supply.',
 'Ayar cihazdan geri okunarak doğrulandı.':'Setting verified by device readback.',
 'HOLD · Son PC karesi donduruldu.':'PC paused · Last frame frozen.',
 'Bu kontrol için firmware v2 yüklenmeli.':'This control requires the patched firmware.',
 'Ayar cihaza gönderiliyor; geri okuma bekleniyor…':'Sending setting; waiting for device readback…',
 'Bu kontrol için cihazın firmware v2 ile açılması gerekiyor.':'This control requires the device to boot with the patched firmware.',
 'Kaydedilecek cihaz verisi yok.':'No device data to save.',
 'Cihaz verisi bekleniyor':'Waiting for device data','CİHAZ ÖLÇÜMÜ':'DEVICE READINGS','HAM GÖRÜNÜM':'RAW VIEW',
 'BEKLE':'WAIT','HATA':'ERROR',
 'Yükleme tamamlandı. Cihazı güç tuşuyla açıp osiloskop ekranına geçin.':'Upload complete. Power on the device and open the oscilloscope screen.',
 'Firmware yükleniyor':'Uploading firmware','DSO-TC3 V0.3 firmware kurulumu':'DSO-TC3 V0.3 firmware installation',
 'Yükleme tamamlanana kadar pencereyi ve USB bağlantısını açık bırakın.':'Keep this window and USB connection open until the upload finishes.',
 'Yalnızca desteklenen DSO-TC3 V0.3 içindir. Firmware değiştirmek cihazı çalışmaz hâle getirebilir.\n\nCihazı kapatıp ▼ + güç ile Bootloader OK ekranına geçin. Orijinal firmware yedeğinizi saklayın.\n\nBu cihaz için yüklemeyi başlatmak istiyor musunuz?':'Only for the supported DSO-TC3 V0.3. Modifying firmware can make the device unusable.\n\nPower off, then hold ▼ and press power to enter Bootloader OK. Keep the original firmware backup.\n\nStart uploading to this device?',
}
FRAGMENTS={
 'Cihaz firmware bağlantısı kontrol ediliyor…':'Checking device firmware connection…',
 'USB bağlı':'USB connected','örnek / kare':'samples / frame',
 'Bağlantı/okuma hatası: ':'Connection/read error: ','Ayar uygulanamadı: ':'Could not apply setting: ',
 'Yükleme durduruldu: ':'Upload stopped: ','Firmware yükleniyor: ':'Uploading firmware: ',
 'USB bağlantısını kesmeyin.':'Do not disconnect USB.',
 'Ham örnekler kaydedildi: ':'Sample words saved: ',
 'ham/div':'raw/div','örn/div':'samples/div',
 'Firmware bulunamadı. GitHub v1.0 Release paketini kullanın.':'Firmware missing. Use the GitHub v1.0 Release package.',
 'Firmware SHA-256 doğrulanamadı; yükleme iptal edildi.':'Firmware SHA-256 mismatch; upload cancelled.',
 'Tek bir DSO-TC3 USB aygıtı bağlı olmalı.':'Exactly one DSO-TC3 USB device must be connected.',
 'Cihaz onayı alınamadı':'Device acknowledgement not received','paket':'packet','yanıt':'response',
 'Onaylanan firmware paketi:':'Acknowledged firmware packets:',
}

def translate(text,language):
    if language!='en':return text
    if text in EN:return EN[text]
    for original,translated in FRAGMENTS.items():text=text.replace(original,translated)
    return text
