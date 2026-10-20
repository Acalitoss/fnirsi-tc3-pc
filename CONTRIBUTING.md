# Katkıda bulunma

Hata raporunda işletim sistemi, Python sürümü, cihazın tam modeli, orijinal firmware sürümü, yama sürümü ve sorunu yeniden üretme adımlarını belirtin. Cihaza bağlı test sonuçlarını emülatör sonuçlarından ayrı yazın.

Üretici firmware dosyalarını, güncelleme EXE dosyalarını, özel ölçüm kayıtlarını veya kimlik bilgilerini commit etmeyin. Örnek veri paylaşılacaksa kaynağını ve sentetik olup olmadığını açıkça belirtin.

Protokol değişikliklerinde paket testlerini; firmware değişikliklerinde orijinal dosya hash kontrolünü, ARM emülasyon testlerini ve sınır kontrollerini güncelleyin. Emülatörün başarılı olması gerçek donanım doğrulamasının yerine geçmez.

Python testleri: `python -m unittest discover -s tests -v`.
