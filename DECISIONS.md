# Architecture Decision Records (ADR)

Kısa, mülakatta savunulabilir kararlar. Her biri: **karar → neden → alternatif → trade-off.**

---

## ADR-001 — Girdi olarak `.tf` (HCL) değil, `terraform plan` JSON

**Karar:** Aracın girdisi `terraform show -json plan.tfplan` çıktısıdır.

**Neden:** `.tf` dosyası bir *niyet tarifi*dir; içindeki `var.*`, `count = ... ? :`, `data` blokları çalışma anında çözülür. Güvenlik incelemesi *çözülmüş, somut* sonucu ister — plan JSON tam olarak bunu verir (`resource_changes[].change.after`).

**Alternatifler:** (a) HCL parse → değerler çözülmemiş, riski göremeyiz. (b) plan'ın metin çıktısı → format garantisi yok, string parse kırılgan.

**Trade-off:** Kullanıcı önce `plan` çalıştırmalı (ön koşul). Ama CI'da bu zaten yapılıyor; karşılığında kesin veri alıyoruz. Yarısı çözülmemiş veriyle "risk yok" demek = false negative.

---

## ADR-002 — Parser çıktısı düz dict değil, `dataclass`

**Karar:** `parse_plan` her kaynağı `ResourceChange` dataclass'ına döker; sadece `create/update/delete` tutulur (`no-op`/`read` atılır).

**Neden:** Veriye **sözleşme** koyar (type safety). Yanlış alan adı anında yakalanır, sessizce `None` dönmez. Gürültü ayıklama hem maliyet (token) hem sinyal/gürültü oranını iyileştirir.

**Alternatif:** Ham dict listesi — kolay ama kırılgan; yanlış anahtar çökene kadar fark edilmez.

**Trade-off:** Birkaç satır fazladan tanım kodu; karşılığında güvenlik ve okunabilirlik. `replace` (`["delete","create"]`) liste-filtresi sayesinde ek kod olmadan doğru ele alınır.

---

## ADR-003 — LLM'den yapılı çıktı: structured output (JSON parse değil)

**Karar:** LLM cevabı bir Pydantic şemasına (`ReviewResult`) zorlanır; SDK doğrular/gerekirse tekrar dener.

**Neden:** Serbest metni `json.loads` ile ayrıştırmak kırılgandır; bozuk çıktı programı çökertir → sessiz false negative. Structured output bu riski SDK'ya devreder. Boş `findings` = "temiz" (geçerli sonuç), exception = "bakamadım" — ikisi kesin ayrı.

**Alternatifler:** (a) düz metin + `json.loads` → kırılgan. (c) tool-calling → bize gereksiz; biz eylem değil rapor istiyoruz.

**Trade-off:** Şema tanımı yazma maliyeti; karşılığında güvenilir, makine-okunur sonuç ve `severity` gibi kapalı-küme alanlar (renk/dallanma için).

---

## ADR-004 — Sağlayıcı bağımsızlığı: `llm.py` seam'i

**Karar:** Tüm sağlayıcı bilgisi tek dosyada (`llm.py`) izole; `reviewer.py` sadece `complete_structured(...)` çağırır ve sağlayıcıyı bilmez.

**Neden:** Vendor lock-in'den kaçınmak. Sağlayıcı değişince `reviewer.py`'ye dokunulmaz — sadece seam'in içi değişir (inversion of dependency).

**Alternatif:** Sağlayıcıyı doğrudan `reviewer` içinde çağırmak — basit ama kilitleyici. Ya da baştan tam soyutlama katmanı — premature abstraction (YAGNI).

**Trade-off:** Küçük bir dolaylılık; karşılığında hızlı sağlayıcı değişimi. Tek dispatch şubesi (`provider="github"`) var, gerektiğinde genişler.

---

## ADR-005 — Varsayılan sağlayıcı: GitHub Models (OpenAI-uyumlu)

**Karar:** Varsayılan olarak GitHub Models endpoint'i (`https://models.github.ai/inference`), `openai` SDK ile.

**Neden:** GitHub ekosisteminden çıkmadan kalmak; deneme için erişilebilir; OpenAI-uyumlu lehçe = endüstri ortak paydası, sağlayıcı değişimini kolaylaştırır. İleride ölçek gerekirse ödemeli sağlayıcıya seam ile geçilir.

**Alternatifler:** Anthropic native (`messages.parse`) — en temiz structured output ama tek satıcıya bağlar. GitHub Copilot API — kodlama asistanı, genel çıkarım için değil.

**Trade-off:** Rate limit'ler ve model kataloğu değişkenliği (üretimde gerçek sağlayıcı gerekebilir). Structured output GitHub'ta `json_schema` yoluyla; native `messages.parse`'tan farklı ama seam bunu gizler.

---

## ADR-006 — Hibrit inceleme: deterministik kurallar + LLM (defense in depth)

**Karar:** İnceleme iki katmanlı: `rules.py` (deterministik, saf fonksiyonlar) + LLM. Kurallar önce ve bağımsız çalışır (garantili taban); bulguları LLM'e sadece "bunlar zaten bulundu, tekrarlama, ek risk bul" bağlamı olarak verilir; sonra iki liste birleştirilir (`analysis.analyze`).

**Neden:** LLM olasılıksal ve tekrarlanamaz — bilinen bariz riskler (0.0.0.0/0, şifresiz disk) onun keyfine bırakılamaz. Kurallar bu bariz riskleri her seferinde garanti yakalar (floor); LLM bağlamsal/kombinasyon/maliyet risklerini bulur (ceiling). Kurallar LLM'den bağımsız fire ettiği için, LLM hata verse bile taban tutar.

**Alternatifler:** (a) Sadece LLM → tekrarlanamaz, false negative riski. (b) Sadece kurallar → yeni/bağlamsal riskleri kaçırır. (c) Kuralları LLM'e ipucu verip raporlamayı LLM'e bırakmak → yine LLM'e bağımlı (reddedildi).

**Trade-off:** Kural bakımı (yeni desen = yeni fonksiyon) ve iki katmanın birleştirme/dupe yönetimi. Dupe'yi LLM'i haberdar ederek azaltıyoruz; kusursuz değil, ileride adres+konu bazlı dedup eklenebilir.

---

## ADR-007 — Graceful degradation: LLM hatası deterministik tabanı düşürmez

**Karar:** LLM çağrısı `analyze()` içinde `try/except` ile izole edilir. LLM patlarsa (network / auth / rate-limit / şema) program çökmez: kural bulgularıyla devam eder, `ReviewResult.llm_available=False` işaretlenir ve yoruma **görünür** bir "AI review çalışmadı, bu kısmi bir inceleme" uyarısı basılır. LLM'in şeması (`LLMReview`) nihai domain tipinden (`ReviewResult`) ayrıldı ki orkestrasyon bayrağı modelin şemasına sızmasın.

**Neden:** ADR-006 "taban tutar" diye *iddia* ediyordu ama implementasyon bunu tutmuyordu — LLM exception'ı yukarı kabarıp bütün review'ı çökertiyor, hesaplanmış kural bulguları da çöpe gidiyordu. Tasarım niyeti ≠ kod. `try/except` bu boşluğu kapatır: deterministik taban artık LLM tavanının çökmesinden gerçekten izole. Kritik ikinci parça: hata **sessizce yutulmaz** — sessiz bozulma (silent degradation), "hepsi temiz" gibi görünüp aslında yarısı incelenmemiş bir sonuç doğurur = false sense of security.

**Alternatifler:** (a) Hatayı yakalamamak → bir sağlayıcı arızası tüm CI'ı kırar, bariz riskler bile raporlanmaz (reddedildi). (b) Yakala ama sessiz geç → daha da tehlikeli; kullanıcı kısmi review'a tam güvenir. (c) Dar `except` (sadece bilinen tipler) → LLM çok farklı şekilde patlar, biri kaçarsa yine çöker; bu yüzden geniş `except` + görünür sinyal tercih edildi.

**Trade-off:** Geniş `except Exception` gerçek programlama hatalarını da yutabilir — bunu, hatayı kullanıcıya görünür kılarak dengeliyoruz (sessiz değil). Ayrıca **exception metni** yoruma yazılmaz, yalnızca "çalışmadı" bilgisi — çünkü hata mesajı token/URL sızdırabilir ve PR'lar herkese açıktır (güvenlik).
