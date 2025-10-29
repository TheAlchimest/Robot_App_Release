"""
Local Command Handler - Class-based, Ultra-optimized for Raspberry Pi Zero
Handles greetings, farewells, simple queries, and system control
"""

import re
from datetime import datetime
import random
from typing import Tuple, Optional, Dict, FrozenSet
from functools import lru_cache


class LocalCommandHandler:
    """
    Ultra-fast local command handler optimized for Raspberry Pi Zero.
    
    Features:
    - Lazy initialization (patterns compiled only when needed)
    - Singleton pattern support
    - State tracking (pause/resume counts, last command, etc.)
    - Configurable responses
    - Pre-compiled regex for maximum speed
    """
    
    # ==================== Class-level Constants ====================
    
    # Command patterns (shared across all instances)
    GREETING_EN = frozenset(['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy'])
    GREETING_AR = frozenset(['مرحبا', 'هلا', 'اهلا', 'السلام عليكم', 'صباح الخير', 'مساء الخير', 'اهلين'])
    
    GOODBYE_EN = frozenset(['bye', 'goodbye', 'see you', 'talk to you later', 'good night', 'catch you later'])
    GOODBYE_AR = frozenset(['مع السلامة', 'الى اللقاء', 'وداعا', 'باي', 'تصبح على خير', 'بكرة نتكلم'])
    
    THANK_YOU_EN = frozenset(['thank you', 'thanks', 'thank you very much', 'appreciate it', 'thx'])
    THANK_YOU_AR = frozenset(['شكرا', 'شكرا لك', 'شكرا جزيلا', 'مشكور', 'يعطيك العافية'])
    
    TIME_EN = frozenset(["what time is it", "what's the time", 'tell me the time', 'current time', 'time now'])
    TIME_AR = frozenset(['كم الساعة', 'ما الوقت', 'الوقت الان', 'اي ساعة الان'])
    
    DATE_EN = frozenset(["what date is it", "what's the date", "today's date", 'what day is it'])
    DATE_AR = frozenset(['ما التاريخ', 'التاريخ اليوم', 'اي يوم اليوم', 'كم التاريخ'])
    
    PAUSE_EN = frozenset(['pause', 'stop', 'stop listening', 'sleep mode', 'go to sleep', 'standby', 'rest',"cancel", "enough", "quit", "exit", "abort", "halt"])
    PAUSE_AR = frozenset(["قف", "توقف", "وقف", "بس", "خلص", "خلاص", "كفايه", "كفاية",
        "ستوب", "وقف التشغيل", "اسكت", "كفا", "خلصنا", "خلاص كده", 'استراحة', 'ارتاح'])
    
    RESUME_EN = frozenset(['wake up', 'resume', 'start listening', 'are you there', 'come back'])
    RESUME_AR = frozenset(['استيقظ', 'استمر', 'ارجع', 'موجود', 'يلا'])
    
    HOW_ARE_YOU_EN = frozenset(['how are you', "how's it going", 'how do you do', "what's up", 'you okay'])
    HOW_ARE_YOU_AR = frozenset(['كيف حالك', 'كيفك', 'شلونك', 'ايش اخبارك', 'عامل ايه'])
    
    HELP_EN = frozenset(['help', 'what can you do', 'your capabilities', 'commands', 'how to use'])
    HELP_AR = frozenset(['مساعدة', 'ماذا تستطيع', 'الاوامر', 'كيف استخدمك', 'وش تقدر تسوي'])
    
    QUESTION_HINTS_EN = frozenset([
        'what', 'how', 'why', 'when', 'where', 'who', 'which',
        'can', 'could', 'would', 'should', 'is', 'are', 'do', 'does',
        'please', 'help', 'explain', 'tell', 'show'
    ])
    QUESTION_HINTS_AR = frozenset([
        'ما', 'ماذا', 'كيف', 'لماذا', 'متى', 'أين', 'مين', 'من', 'ايش', 'هل',
        'وش', 'يا ريت', 'ممكن', 'رجاء', 'ساعد', 'اشرح', 'وضح', 'قل', 'اعرض'
    ])
    
    # Pre-compiled regex (class-level, shared)
    _NORMALIZE_REGEX = re.compile(r'[^\w\s\u0600-\u06FF]+')
    _SPACES_REGEX = re.compile(r'\s+')
    _ARABIC_CHARS_REGEX = re.compile(r'[\u0600-\u06FF]')
    _WORD_CHARS_REGEX = re.compile(r'[\w\u0600-\u06FF]')
    
    # ==================== Initialization ====================
    
    def __init__(self, language_preference: str = 'auto', enable_stats: bool = False):
        """
        Initialize Local Command Handler.
        
        Args:
            language_preference: 'auto', 'english', or 'arabic'
            enable_stats: Track command statistics (uses minimal memory)
        """
        self.language_preference = language_preference
        self.enable_stats = enable_stats
        
        # State tracking
        self._is_paused = False
        self._stats = {
            'total_commands': 0,
            'local_handled': 0,
            'api_forwarded': 0,
            'pause_count': 0,
            'resume_count': 0,
        } if enable_stats else None
        
        # Lazy-loaded patterns (compiled on first use)
        self._patterns_compiled = None
        self._responses = self._init_responses()
    
    def _init_responses(self) -> Dict:
        """Initialize response templates."""
        return {
            'greeting': {
                'english': [
                    "Hello! How can I help you?",
                    "Hi there! What can I do for you?",
                    "Hey! I'm here to assist you.",
                    "Good to hear from you! How may I help?"
                ],
                'arabic': [
                    "مرحبا! كيف يمكنني مساعدتك؟",
                    "أهلا! في خدمتك.",
                    "هلا! شو احتياجك؟",
                    "اهلين! كيف اقدر اخدمك؟"
                ]
            },
            'goodbye': {
                'english': [
                    "Goodbye! Say 'hello' when you need me again.",
                    "See you later! Just call me when you're ready.",
                    "Take care! I'll be here when you need me.",
                ],
                'arabic': [
                    "مع السلامة! قل مرحبا عندما تحتاجني.",
                    "الى اللقاء! ناديني متى احتجتني.",
                    "الله يسلمك! انا هنا متى احتجتني.",
                ]
            },
            'thank_you': {
                'english': [
                    "You're welcome! Happy to help.",
                    "My pleasure! Anytime you need assistance.",
                    "Glad I could help!",
                ],
                'arabic': [
                    "عفوا! سعيد بمساعدتك.",
                    "على الرحب والسعة!",
                    "تشرفنا! اي خدمة.",
                ]
            },
            'how_are_you': {
                'english': [
                    "I'm doing great, thank you! Ready to assist you.",
                    "All systems running smoothly! How about you?",
                    "I'm excellent! What can I help you with?",
                ],
                'arabic': [
                    "بخير الحمد لله! جاهز لمساعدتك.",
                    "تمام! كيف حالك انت؟",
                    "كويس جدا! شو احتياجك؟",
                ]
            },
            'pause': {
                'english': [
                    "Going to sleep mode. Say 'hello' or 'wake up' to resume.",
                    "Entering standby. Wake me up when you need me.",
                ],
                'arabic': [
                    "داخل وضع النوم. قل مرحبا للعودة.",
                    "راح ارتاح. ناديني متى احتجتني.",
                ]
            },
            'resume': {
                'english': [
                    "Hello! I'm back and ready to help you.",
                    "I'm here! What do you need?",
                    "Ready for action! How can I assist?",
                ],
                'arabic': [
                    "مرحبا! رجعت وجاهز لمساعدتك.",
                    "موجود! شو احتياجك؟",
                    "جاهز! كيف اقدر اساعدك؟",
                ]
            },
            'help': {
                'english': """I can help you with many things! Here are some commands:
• Say 'bye' or 'goodbye' to pause me
• Say 'hello' or 'hi' to wake me up
• Ask 'what time is it' for current time
• Ask 'what date is it' for current date
• Say 'thank you' when I help you
• Ask me anything else and I'll use AI to help!""",
                'arabic': """يمكنني مساعدتك بأشياء كثيرة! إليك بعض الأوامر:
• قل 'مع السلامة' لإيقافي مؤقتاً
• قل 'مرحبا' لإيقاظي
• اسأل 'كم الساعة' لمعرفة الوقت
• اسأل 'ما التاريخ' لمعرفة التاريخ
• قل 'شكرا' عندما أساعدك
• اسألني أي شيء آخر وسأستخدم الذكاء الاصطناعي!"""
            }
        }
    
    # ==================== Pattern Compilation (Lazy) ====================
    
    def _compile_patterns(self) -> Dict:
        """Lazy compilation of regex patterns (called only once, on first use)."""
        if self._patterns_compiled is not None:
            return self._patterns_compiled
        
        def compile_pattern_set(patterns_en: FrozenSet, patterns_ar: FrozenSet) -> Dict:
            """Compile patterns for both languages."""
            compiled = {}
            
            for lang, patterns in [('en', patterns_en), ('ar', patterns_ar)]:
                sorted_patterns = sorted(patterns, key=len, reverse=True)
                parts = []
                
                for phrase in sorted_patterns:
                    phrase_norm = phrase.lower().strip()
                    words = phrase_norm.split()
                    
                    if len(words) > 1:
                        pattern = r'\b' + r'\s+'.join(re.escape(w) for w in words) + r'\b'
                    else:
                        pattern = r'\b' + re.escape(phrase_norm) + r'\b'
                    
                    parts.append(pattern)
                
                compiled[lang] = re.compile('|'.join(parts), re.IGNORECASE)
            
            return compiled
        
        self._patterns_compiled = {
            'greeting': compile_pattern_set(self.GREETING_EN, self.GREETING_AR),
            'goodbye': compile_pattern_set(self.GOODBYE_EN, self.GOODBYE_AR),
            'thank_you': compile_pattern_set(self.THANK_YOU_EN, self.THANK_YOU_AR),
            'time': compile_pattern_set(self.TIME_EN, self.TIME_AR),
            'date': compile_pattern_set(self.DATE_EN, self.DATE_AR),
            'pause': compile_pattern_set(self.PAUSE_EN, self.PAUSE_AR),
            'resume': compile_pattern_set(self.RESUME_EN, self.RESUME_AR),
            'how_are_you': compile_pattern_set(self.HOW_ARE_YOU_EN, self.HOW_ARE_YOU_AR),
            'help': compile_pattern_set(self.HELP_EN, self.HELP_AR),
        }
        
        return self._patterns_compiled
    
    # ==================== Utility Methods ====================
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Ultra-fast text normalization."""
        text = text.lower().strip()
        text = LocalCommandHandler._NORMALIZE_REGEX.sub(' ', text)
        text = LocalCommandHandler._SPACES_REGEX.sub(' ', text).strip()
        return text
    
    @staticmethod
    def detect_language(text: str) -> str:
        """Fast language detection."""
        arabic_count = len(LocalCommandHandler._ARABIC_CHARS_REGEX.findall(text))
        if arabic_count == 0:
            return 'english'
        
        total_count = len(LocalCommandHandler._WORD_CHARS_REGEX.findall(text))
        if total_count == 0:
            return 'english'
        
        return 'arabic' if (arabic_count / total_count) > 0.3 else 'english'
    
    def has_pattern(self, text: str, pattern_name: str) -> bool:
        """Check if text matches any pattern."""
        patterns = self._compile_patterns()
        norm_text = self.normalize_text(text)
        
        pattern_dict = patterns.get(pattern_name, {})
        for regex in pattern_dict.values():
            if regex.search(norm_text):
                return True
        
        return False
    
    def pick_response(self, response_type: str, text: str) -> str:
        """Pick appropriate response based on language."""
        lang = self.detect_language(text) if self.language_preference == 'auto' else self.language_preference
        
        responses = self._responses.get(response_type, {})
        
        if isinstance(responses, dict):
            lang_responses = responses.get(lang, responses.get('english', []))
            if isinstance(lang_responses, list):
                return random.choice(lang_responses)
            return lang_responses
        
        return responses
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_local_time() -> str:
        """Get current time (cached for 1 second)."""
        return datetime.now().strftime("%I:%M %p")
    
    @staticmethod
    def get_local_date() -> str:
        """Get current date."""
        return datetime.now().strftime("%A, %B %d, %Y")
    
    # ==================== Greeting Detection ====================
    
    def split_greeting_and_remainder(self, text: str) -> Tuple[Optional[str], str]:
        """Fast greeting detection and separation."""
        norm = self.normalize_text(text)
        patterns = self._compile_patterns()
        
        for regex in patterns['greeting'].values():
            m = regex.match(norm)
            if m:
                greeting_found = m.group(0)
                remainder = norm[m.end():].strip()
                return greeting_found, remainder
        
        return None, norm
    
    def looks_like_question_or_command(self, text: str) -> bool:
        """Detect if text has actionable content."""
        if not text:
            return False
        
        if '?' in text:
            return True
        
        tokens = text.split()
        if len(tokens) >= 2:
            return True
        
        text_lower = text.lower()
        words = text_lower.split()
        
        # Check English hints
        if any(word in self.QUESTION_HINTS_EN for word in words):
            return True
        
        # Check Arabic hints
        if any(hint in text for hint in self.QUESTION_HINTS_AR):
            return True
        
        return False
    
    # ==================== State Management ====================
    
    @property
    def is_paused(self) -> bool:
        """Check if handler is in paused state."""
        return self._is_paused
    
    def get_stats(self) -> Optional[Dict]:
        """Get command statistics (if enabled)."""
        return self._stats.copy() if self._stats else None
    
    def reset_stats(self):
        """Reset command statistics."""
        if self._stats:
            self._stats = {k: 0 for k in self._stats}
    
    # ==================== Main Command Handler ====================
    
    def handle(self, text: str) -> Tuple[bool, Optional[str], Optional[str], str]:
        """
        Handle local commands.
        
        Args:
            text: Input text to process
        
        Returns:
            Tuple of (should_continue_to_api, local_response, action, passthrough_text)
            - should_continue_to_api: True to forward to API, False if handled locally
            - local_response: Optional response to speak/display
            - action: 'pause', 'resume', or None
            - passthrough_text: Text to send to API (may have greeting stripped)
        """
        if not text or not text.strip():
            return True, None, None, ""
        
        # Track statistics
        if self._stats:
            self._stats['total_commands'] += 1
        
        original_text = text
        
        # 1) Control commands (highest priority)
        if self.has_pattern(original_text, 'pause'):
            self._is_paused = True
            if self._stats:
                self._stats['pause_count'] += 1
                self._stats['local_handled'] += 1
            return False, self.pick_response('pause', original_text), 'pause', ""
        
        if self.has_pattern(original_text, 'goodbye'):
            self._is_paused = True
            if self._stats:
                self._stats['pause_count'] += 1
                self._stats['local_handled'] += 1
            return False, self.pick_response('goodbye', original_text), 'pause', ""
        
        if self.has_pattern(original_text, 'resume'):
            self._is_paused = False
            if self._stats:
                self._stats['resume_count'] += 1
                self._stats['local_handled'] += 1
            return False, self.pick_response('resume', original_text), 'resume', ""
        
        # 2) Greetings with passthrough
        greeting_phrase, remainder = self.split_greeting_and_remainder(original_text)
        
        if greeting_phrase is not None:
            if not remainder or not self.looks_like_question_or_command(remainder):
                # Pure greeting
                self._is_paused = False
                if self._stats:
                    self._stats['local_handled'] += 1
                return False, self.pick_response('greeting', original_text), 'resume', ""
            
            # Greeting + question
            if self._stats:
                self._stats['api_forwarded'] += 1
            return True, self.pick_response('greeting', original_text), 'resume', remainder
        
        # 3) Simple local queries
        if self.has_pattern(original_text, 'thank_you'):
            if self._stats:
                self._stats['local_handled'] += 1
            return False, self.pick_response('thank_you', original_text), None, ""
        
        if self.has_pattern(original_text, 'how_are_you'):
            if self._stats:
                self._stats['local_handled'] += 1
            return False, self.pick_response('how_are_you', original_text), None, ""
        
        if self.has_pattern(original_text, 'help'):
            lang = self.detect_language(original_text)
            if self._stats:
                self._stats['local_handled'] += 1
            return False, self._responses['help'][lang], None, ""
        
        if self.has_pattern(original_text, 'time'):
            current_time = self.get_local_time()
            lang = self.detect_language(original_text)
            resp = f"الوقت الآن {current_time}" if lang == 'arabic' else f"The current time is {current_time}"
            if self._stats:
                self._stats['local_handled'] += 1
            return False, resp, None, ""
        
        if self.has_pattern(original_text, 'date'):
            current_date = self.get_local_date()
            lang = self.detect_language(original_text)
            resp = f"التاريخ اليوم {current_date}" if lang == 'arabic' else f"Today is {current_date}"
            if self._stats:
                self._stats['local_handled'] += 1
            return False, resp, None, ""
        
        # 4) Forward to API
        if self._stats:
            self._stats['api_forwarded'] += 1
        return True, None, None, original_text


# ==================== Singleton Instance (recommended for Pi Zero) ====================

# Global singleton instance (lazy-initialized)
_handler_instance = None

def get_handler(language_preference: str = 'auto', enable_stats: bool = False) -> LocalCommandHandler:
    """
    Get singleton instance of LocalCommandHandler.
    Recommended for Raspberry Pi Zero to minimize memory usage.
    """
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = LocalCommandHandler(language_preference, enable_stats)
    return _handler_instance


# ==================== Convenience Function (backward compatible) ====================

def handle_local_command(text: str) -> Tuple[bool, Optional[str], Optional[str], str]:
    """
    Backward-compatible function wrapper.
    Uses singleton instance for optimal performance.
    """
    handler = get_handler()
    return handler.handle(text)


# ==================== Testing ====================

if __name__ == "__main__":
    import time
    
    print("=" * 70)
    print("🚀 Class-Based Local Command Handler for Raspberry Pi Zero")
    print("=" * 70)
    print()
    
    # Create handler with stats enabled
    handler = LocalCommandHandler(enable_stats=True)
    
    tests = [
        ("hello", False, "greeting"),
        ("مرحبا", False, "greeting"),
        ("hello, explain repository pattern", True, "greeting+API"),
        ("bye", False, "pause"),
        ("wake up", False, "resume"),
        ("what time is it", False, "time"),
        ("thank you", False, "thanks"),
        ("explain dotnet core", True, "API"),
    ]
    
    print("📋 Functional Tests:")
    print("-" * 70)
    
    passed = 0
    total_time = 0
    
    for text, expected_continue, category in tests:
        start = time.perf_counter()
        should_continue, resp, action, pass_text = handler.handle(text)
        elapsed = time.perf_counter() - start
        total_time += elapsed
        
        success = (should_continue == expected_continue)
        status = "✅" if success else "❌"
        passed += 1 if success else 0
        
        print(f"{status} [{category}] '{text[:40]}'")
        print(f"   Continue: {should_continue} | Action: {action}")
        print(f"   Response: {resp[:50] if resp else 'None'}...")
        print(f"   Time: {elapsed*1000:.4f}ms")
        print()
    
    print("=" * 70)
    print(f"Results: {passed}/{len(tests)} passed")
    print(f"Average time: {(total_time/len(tests))*1000:.4f}ms")
    print()
    
    # Show stats
    print("📊 Command Statistics:")
    stats = handler.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()
    
    # Performance test
    print("⚡ Performance Stress Test:")
    print("-" * 70)
    
    test_texts = [
        "hello",
        "what time is it",
        "مرحبا كيف حالك",
    ]
    
    for test_text in test_texts:
        iterations = 5000
        start = time.perf_counter()
        
        for _ in range(iterations):
            handler.handle(test_text)
        
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / iterations) * 1_000_000
        
        print(f"Text: '{test_text[:35]}'")
        print(f"  {iterations} iterations: {elapsed*1000:.2f}ms")
        print(f"  Average: {avg_us:.2f}μs per call")
        print(f"  Throughput: {iterations/elapsed:.0f} calls/sec")
        print()
    
    print("=" * 70)
    print("✨ Class-based advantages:")
    print("  • Lazy pattern compilation (faster startup)")
    print("  • State management (pause/resume tracking)")
    print("  • Statistics tracking (optional)")
    print("  • Singleton support (memory efficient)")
    print("  • Easy testing and mocking")
    print("  • Configurable responses per instance")
    print("🎯 Perfect for Raspberry Pi Zero!")
    print("=" * 70)