import re
from typing import Tuple, Iterable
# -------------------------------------------------------------------
# Ultra-optimized Wake-word Detector (Class Version) - NO Levenshtein!
# -------------------------------------------------------------------

class WakeWordDetector:
    """
    Wake-word detector مُحسَّن للأداء (بدون Levenshtein).
    يدعم:
      - تطبيع عربي خفيف
      - التقاط النداء بالإنجليزية/العربية في بداية النص فقط
      - مجموعات قبول/رفض O(1) lookup
    """

    # تحيّات (ممكن تحتاجها خارجيًا — تركناها كـ class attrs)
    GREETING_AR = ["مرحبا", "اهلا", "أهلا", "السلام عليكم", "هلا", "اهلين", "صباح الخير", "مساء الخير"]
    GREETING_EN = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "howdy"]

    # -------- Arabic Diacritics (precompiled) --------
    _AR_DIACRITICS = re.compile(r'[\u0617-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]')

    def __init__(
        self,
        ar_wake_word: str = "زيكو",
        en_wake_exact: Iterable[str] = (
            "ziko", "zico", "zeeko", "zeeco",
            "zikko", "zeiko", "zyko", "zeko",
            "dziko", "dico", "zika", "nico", "niko", "echo"
             
        ),
        en_wake_deny: Iterable[str] = (
            #"zika", "nico", "nika", "nikaa",
           # "z", "d",  # حروف مفردة
        ),
    ):
        """
        :param ar_wake_word: كلمة النداء العربية (افتراضيًا: زيكو)
        :param en_wake_exact: قائمة القبول الدقيق للإنجليزي (frozenset O(1))
        """
        self.ar_wake_word = ar_wake_word
        self._EN_WAKE_EXACT = frozenset(x.lower() for x in en_wake_exact)
        self._EN_WAKE_DENY = frozenset(x.lower() for x in en_wake_deny)

        # -------- Regex تُبنى مرة واحدة --------
        # عربي: ^\s*(?:يا\s*)?{ar_wake}\b[\s،,:-]*
        ar_escaped = re.escape(self._normalize_ar(ar_wake_word))
        self._AR_WAKE_REGEX = re.compile(
            rf"^\s*(?:يا\s*)?{ar_escaped}\b[\s،,:-]*",
            re.IGNORECASE
        )

        # إنجليزي: نلتقط أول كلمة فقط كبادئة
        self._EN_WAKE_REGEX = re.compile(
            r"^\s*(?:hey|hi|hello\s+)?([a-z]+)[\s,،:.\-!?]*",
            re.IGNORECASE
        )

    # ---------------- Utilities ----------------
    @staticmethod
    def contains_any(text: str, words: list[str]) -> bool:
        """فحص سريع (O(n)) لوجود أي كلمة داخل النص (lowercase مرة واحدة)."""
        if not text:
            return False
        t = text.lower()
        return any((w and w.lower() in t) for w in words)

    # ---------------- Normalization (Arabic) ----------------
    def _normalize_ar(self, text: str) -> str:
        """تطبيع عربي خفيف وسريع."""
        if not text:
            return ""
        text = self._AR_DIACRITICS.sub('', text.strip().lower())
        text = text.translate(str.maketrans({
            'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',
            'ة': 'ه', 'ى': 'ي', 'ـ': ''
        }))
        return text

    # ---------------- English Wake Token Check ----------------
    def _is_english_wake_token(self, tok: str) -> bool:
        """
        فحص فائق السرعة للـ wake-token الإنجليزي:
          - رفض سريع O(1)
          - قبول دقيق O(1)
          - قواعد بسيطة بدون Levenshtein
        """
        if not tok or len(tok) < 2:
            return False

        t = tok.lower()

        # 1) رفض فوري
        if t in self._EN_WAKE_DENY:
            return False

        # 2) قبول دقيق
        if t in self._EN_WAKE_EXACT:
            return True

        # 3) شروط بسيطة (بدون Levenshtein):
        #    يبدأ بـ z أو d + يحتوي "iko"/"ico"
        if t[0] not in ('z', 'd'):
            return False

        if "iko" in t or "ico" in t:
            return True

        return False

    # ---------------- Main API ----------------
    def extract_after_wake(self, user_text: str) -> Tuple[bool, str, str]:
        """
        استخراج wake-word مع إرجاع: (has_wake, remainder, wake_form)
        - يتحقق أولًا من الإنجليزية (أسرع مسار)، ثم العربية.
        - remainder يُعاد من النص الأصلي (بدون lowercase).
        """
        text = (user_text or "").strip()
        if not text:
            return False, "", ""

        # ===== English Detection (Fast Path) =====
        text_lower = text.lower()
        m_en = self._EN_WAKE_REGEX.match(text_lower)

        if m_en:
            first_token = m_en.group(1)
            if self._is_english_wake_token(first_token):
                return True, text[m_en.end():].strip(), first_token

        # ===== Arabic Detection =====
        norm_ar = self._normalize_ar(text)
        m_ar = self._AR_WAKE_REGEX.match(norm_ar)

        if m_ar:
            # قص من النص الأصلي بمطابقة مكافئة
            # نعيد بناء نفس النمط لكن على النص الأصلي (غير مُطبَّع)
            orig_ar_regex = re.compile(
                rf"^\s*(?:يا\s*)?{re.escape(self.ar_wake_word)}\b[\s،,:-]*",
                re.IGNORECASE
            )
            m_orig = orig_ar_regex.match(text)
            if m_orig:
                return True, text[m_orig.end():].strip(), m_orig.group(0).strip()

            # fallback بسيط لو التعادل بين التطبيع/الأصل أخفق
            return True, text[len(self.ar_wake_word):].strip(), self.ar_wake_word

        return False, "", ""

# ================= Demo / Quick Test =================
if __name__ == "__main__":
    import time

    detector = WakeWordDetector()

    print("=" * 70)
    print("🚀 ULTRA-FAST Wake-word Detection (Class Version)")
    print("=" * 70)
    print()

    test_cases = [
        # Expected to WAKE ✅
        ("Ziko play some music", True, "play some music"),
        ("hey zico open mail", True, "open mail"),
        ("Dico what's the weather", True, "what's the weather"),
        ("Dziko, read my latest email", True, "read my latest email"),
        ("hello ziko, what's up?", True, "what's up?"),
        ("ZEeCo, open settings", True, "open settings"),
        ("زيكو: ابحث عن الأخبار", True, "ابحث عن الأخبار"),
        ("يا زيكو افتح البريد", True, "افتح البريد"),
        ("ziko", True, ""),

        # Expected to IGNORE ❌
        ("Nico open calendar", False, ""),
        ("Zika is a virus", False, ""),
        ("Z.", False, ""),
        ("Z", False, ""),
        ("sorry, ziko open mail", False, ""),  # ليس في البداية
        ("play some music", False, ""),
    ]

    print("📋 Functional Tests:")
    print("-" * 70)

    passed = 0
    total_time = 0

    for text, expected_wake, expected_cmd in test_cases:
        start = time.perf_counter()
        has_wake, remainder, wake_form = detector.extract_after_wake(text)
        elapsed = time.perf_counter() - start
        total_time += elapsed

        success = (has_wake == expected_wake)
        if success and expected_wake:
            success = (remainder == expected_cmd)

        status = "✅" if success else "❌"
        passed += 1 if success else 0

        print(f"{status} '{text[:40]}'")
        if has_wake:
            print(f"   Wake: '{wake_form}' → Command: '{remainder}'")
        print(f"   Time: {elapsed*1000:.4f}ms")
        print()

    print("=" * 70)
    print(f"Results: {passed}/{len(test_cases)} passed ({'✅' if passed == len(test_cases) else '❌'})")
    print(f"Average time: {(total_time/len(test_cases))*1000:.4f}ms")
    print()

    # ===== Performance Stress Test =====
    print("⚡ Performance Stress Test:")
    print("-" * 70)

    test_texts = [
        "زيكو افتح البريد الإلكتروني",
        "Ziko play some music",
        "hey zico what's the weather",
        "not a wake word at all"
    ]

    for test_text in test_texts:
        iterations = 5000
        start = time.perf_counter()

        for _ in range(iterations):
            detector.extract_after_wake(test_text)

        elapsed = time.perf_counter() - start
        avg_us = (elapsed / iterations) * 1_000_000  # microseconds

        print(f"Text: '{test_text[:35]}'")
        print(f"  {iterations} iterations: {elapsed*1000:.2f}ms")
        print(f"  Average: {avg_us:.2f}μs per call")
        print(f"  Throughput: {iterations/elapsed:.0f} calls/sec")
        print()

    print("=" * 70)
    print("✨ Optimization: NO Levenshtein, O(1) lookups only!")
    print("🎯 Perfect for Raspberry Pi Zero with minimal CPU usage")
    print("=" * 70)


class StopCommandDetector:
    """
    Detects stop commands in both Arabic and English, with support for normalization
    and optional wake words (e.g., 'Ziko stop', 'زيكو وقف').
    """

    # ------------------- Arabic normalization -------------------
    # Regex to remove Arabic diacritics and elongations.
    _AR_DIACRITICS = re.compile(r'[\u0617-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]')

    # Stop tokens that indicate interruption or stopping the assistant.
    STOP_TOKENS = [
        # English
        "stop", "end", "cancel", "enough", "quit", "exit", "abort", "halt",
        # Arabic (common forms)
        "قف", "توقف", "وقف", "بس", "خلص", "خلاص", "كفايه", "كفاية",
        "ستوب", "وقف التشغيل", "اسكت", "كفا", "خلصنا", "خلاص كده",
    ]

    # Pattern: match stop token at beginning, followed by whitespace, punctuation, or end of string.
    _BOUNDARY = r'(?:\s|$|[^\w\u0600-\u06FF])'

    def __init__(self, extract_after_wake_func=None):
        """
        :param extract_after_wake_func: Optional callable for detecting and extracting
                                        text after a wake word (e.g., 'Ziko stop').
        """
        self.extract_after_wake_func = extract_after_wake_func

        # Build regex once during initialization for better performance
        pattern = r'^\s*(?:' + '|'.join(map(re.escape, self.STOP_TOKENS)) + r')' + self._BOUNDARY
        self._stop_re = re.compile(pattern, re.IGNORECASE)

    # -----------------------------------------------------------------
    #                     Arabic Normalization
    # -----------------------------------------------------------------
    def _normalize_ar(self, text: str) -> str:
        """
        Normalize Arabic text:
        - Lowercase and strip whitespace
        - Remove diacritics and elongations
        - Convert letter variants (أإآٱ → ا, ة → ه, ى → ي)
        """
        if not text:
            return ""
        text = text.strip().lower()
        text = self._AR_DIACRITICS.sub('', text)
        text = text.replace('ـ', '')  # remove kashida
        for src in 'أإآٱ':
            text = text.replace(src, 'ا')
        text = text.replace('ة', 'ه')
        text = text.replace('ى', 'ي')
        return text

    # -----------------------------------------------------------------
    #                     Core Detection Logic
    # -----------------------------------------------------------------
    def is_stop_command(self, text: str) -> bool:
        """
        Returns True if the text begins with a recognized stop command
        in Arabic or English.
        """
        if not text:
            return False

        normalized = self._normalize_ar(text)
        return bool(self._stop_re.search(text) or self._stop_re.search(normalized))

    def is_stop_with_optional_wake(self, text: str) -> bool:
        """
        Returns True if:
        - The text is a stop command directly (e.g., "stop", "وقف")
        - OR after a wake word (e.g., "Ziko stop", "زيكو وقف")
        """
        if not text:
            return False

        candidate = text
        if self.extract_after_wake_func:
            try:
                has_wake, remainder, _wake = self.extract_after_wake_func(text)
                candidate = remainder if has_wake else text
            except Exception:
                pass

        return self.is_stop_command(candidate)



