import pyphen
import re
import threading
from pathlib import Path

import fugashi
from num2words import num2words


# ========== 工具模块：Pyphen 缓存 ==========

class PyphenCache:
    _instance = None
    _cache = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_dictionary(self, lang_code):
        if lang_code not in self._cache:
            self._cache[lang_code] = pyphen.Pyphen(lang=lang_code)
        return self._cache[lang_code]


_pyphen_cache = PyphenCache()


def _pyphen_syllable_count(word, pyphen_lang):
    """使用 pyphen 计算音节数（带缓存，规范化处理）"""
    # 规范化：去除尾部标点和连字符
    clean_word = word.rstrip(".,;:!?()[]{}\"\'-")
    normalized = clean_word.replace("-", "")  # 避免连字符被算作音节分隔

    # 检查西语词典
    if pyphen_lang == 'es_ES' and normalized.lower() in _SPANISH_SYLLABLES:
        return _SPANISH_SYLLABLES[normalized.lower()]

    try:
        dic = _pyphen_cache.get_dictionary(pyphen_lang)
        hyphenated = dic.inserted(normalized)
        return hyphenated.count("-") + 1
    except Exception:
        return _fallback_syllable_count(normalized)

def _fallback_syllable_count(word):
    word = word.lower()
    if len(word) <= 3:
        return 1

    count = 0
    vowels = "aeiouy"

    if word[0] in vowels:
        count += 1

    for i in range(1, len(word)):
        if word[i] in vowels and word[i - 1] not in vowels:
            count += 1

    if word.endswith('e'):
        count -= 1
    if word.endswith('le') and len(word) > 2 and word[-3] not in vowels:
        count += 1

    return max(1, count)


# ========== 混合内容解析器 ==========

_SCRIPT_RANGES = [
    (re.compile(r'[一-鿿㐀-䶿]'), 'han'),
    (re.compile(r'[぀-ゟ゠-ヿ]'), 'kana'),
    (re.compile(r'[ء-يٱ-ۓە-ۿ'
                r'ݐ-ݿࢠ-ࣿ'
                r'ﭐ-﷿ﹰ-﻿]'), 'arabic'),
    (re.compile(r'[ً-ٰٟٓ]'), 'arabic_diacritic'),
    (re.compile(r'[a-zA-ZÀ-ÿŒœ]'), 'latin'),  # 包含扩展拉丁字母（包括 Œ/œ）
    (re.compile(r'[0-9٠-٩０-９]'), 'number'),  # ASCII、阿拉伯语、全角数字
]


def _detect_script(char):
    for pattern, script in _SCRIPT_RANGES:
        if pattern.match(char):
            return script
    return 'other'


def _parse_mixed_content(text):
    if not text:
        return []

    segments = []
    current_segment = ""
    current_type = None

    i = 0
    while i < len(text):
        char = text[i]
        char_type = _detect_script(char)

        # 处理数字相关的特殊格式
        if char_type == 'number' or (char_type == 'other' and char in '.-/$'):
            # 尝试匹配完整的数字格式（包括电话号码、小数、货币等）
            number_match = re.match(r'[\d.,\-/$]+', text[i:])
            if number_match:
                number_str = number_match.group()
                # 检查是否包含数字
                if re.search(r'\d', number_str):
                    # 检查是否是 COVID-19 这类字母+连字符+数字
                    # 如果前面紧邻字母且以连字符开头，这是连字符词的一部分
                    if number_str.startswith('-') and i > 0 and text[i-1].isalpha():
                        # 这是连字符词的一部分，不单独处理
                        if current_type:
                            current_segment += char
                        else:
                            current_segment = char
                            current_type = 'other'
                        i += 1
                        continue

                    # 检查是否有序数后缀（st, nd, rd, th）
                    ordinal_suffix = ''
                    next_pos = i + len(number_str)
                    if next_pos + 2 <= len(text):
                        potential_suffix = text[next_pos:next_pos+2]
                        if potential_suffix.lower() in ('st', 'nd', 'rd', 'th'):
                            ordinal_suffix = potential_suffix

                    if current_segment and current_type:
                        segments.append((current_segment.strip(), current_type))

                    # 如果有序数后缀，合并到数字中
                    if ordinal_suffix:
                        segments.append((number_str + ordinal_suffix, 'number'))
                        i += len(number_str) + len(ordinal_suffix)
                    else:
                        segments.append((number_str, 'number'))
                        i += len(number_str)

                    current_segment = ""
                    current_type = None
                    continue

        if char_type == 'other':
            if char.isspace():
                if current_type == 'latin':
                    current_segment += char
                    i += 1
                    continue
                elif current_segment:
                    segments.append((current_segment.strip(), current_type))
                    current_segment = ""
                    current_type = None
                i += 1
                continue
            if current_type:
                current_segment += char
            i += 1
            continue

        # arabic diacritics 归入 arabic
        if char_type == 'arabic_diacritic':
            char_type = 'arabic'

        if char_type == current_type:
            current_segment += char
        else:
            if current_segment:
                segments.append((current_segment.strip(), current_type))
            current_segment = char
            current_type = char_type

        i += 1

    if current_segment and current_segment.strip():
        segments.append((current_segment.strip(), current_type))

    return segments


# ========== 数字展开模块 ==========

# num2words 语言代码映射
_NUM2WORDS_LANG_MAP = {
    'en': 'en',
    'zh': 'zh',
    'ja': 'ja',
    'de': 'de',
    'fr': 'fr',
    'es': 'es',
    'ar': 'ar',
}

# 英语字母发音音节数 (A=1, B=1, C=1, D=1, E=1, F=1, G=1, H=1, I=1,
# J=1, K=1, L=1, M=1, N=1, O=1, P=1, Q=1, R=1, S=1, T=1, U=1,
# V=1, W=3, X=1, Y=1, Z=1)
_LETTER_SYLLABLES_EN = {
    'A': 1, 'B': 1, 'C': 1, 'D': 1, 'E': 1, 'F': 1, 'G': 1, 'H': 1,
    'I': 1, 'J': 1, 'K': 1, 'L': 1, 'M': 1, 'N': 1, 'O': 1, 'P': 1,
    'Q': 1, 'R': 1, 'S': 1, 'T': 1, 'U': 1, 'V': 1, 'W': 3, 'X': 1,
    'Y': 1, 'Z': 1,
}


def _is_year_like(num_str):
    """判断数字是否可能是年份（1000-2099）"""
    # 如果包含逗号，不是年份（是带千分位的数字）
    if ',' in num_str:
        return False
    try:
        n = int(num_str)
        return 1000 <= n <= 2099 and len(num_str) == 4
    except ValueError:
        return False


def _expand_year_en(year_str):
    """英语年份特殊读法：2024 → twenty twenty-four"""
    n = int(year_str)
    if 2000 <= n <= 2009:
        return num2words(n, lang='en')
    if 2010 <= n <= 2099:
        first = n // 100
        second = n % 100
        first_word = num2words(first, lang='en')
        second_word = num2words(second, lang='en')
        return f"{first_word} {second_word}"
    # 1900-1999: nineteen ninety-nine
    if 1000 <= n <= 1999:
        first = n // 100
        second = n % 100
        first_word = num2words(first, lang='en')
        if second == 0:
            return f"{first_word} hundred"
        second_word = num2words(second, lang='en')
        return f"{first_word} {second_word}"
    return num2words(n, lang='en')


def _expand_number(num_str, lang):
    """将数字字符串展开为对应语言的文字"""
    # 处理特殊格式

    # 处理英文序数后缀
    ordinal_suffix = ''
    if lang == 'en' and len(num_str) > 2:
        last_two = num_str[-2:].lower()
        if last_two in ('st', 'nd', 'rd', 'th'):
            ordinal_suffix = last_two
            num_str = num_str[:-2]

    # 去除货币符号
    num_str = num_str.lstrip('$¥€£')

    # 处理千位分隔符和小数点（根据语言）
    if lang in ('es', 'fr', 'de'):
        # 欧洲大陆：逗号是小数点，点是千位分隔符
        # 先去除千位分隔符（点）
        num_str_temp = num_str.replace('.', '')
        # 将逗号替换为点（标准化为英语格式）
        num_str_clean = num_str_temp.replace(',', '.')
    else:
        # 英语/中文/阿拉伯语：点是小数点，逗号是千位分隔符
        # 去除千位分隔符（逗号）
        num_str_clean = num_str.replace(',', '')

    # 处理小数
    if '.' in num_str_clean:
        parts = num_str_clean.split('.')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            try:
                n2w_lang = _NUM2WORDS_LANG_MAP.get(lang, 'en')
                # 整数部分
                result = num2words(int(parts[0]), lang=n2w_lang)
                # 小数点的表达（根据语言）
                if lang == 'zh':
                    result += '点'
                elif lang == 'es':
                    result += ' coma'
                elif lang == 'fr':
                    result += ' virgule'
                elif lang == 'de':
                    result += ' Komma'
                elif lang == 'ar':
                    result += ' فاصلة'
                else:
                    result += ' point'
                # 小数部分逐位读
                for digit in parts[1]:
                    if lang == 'zh':
                        _ZH_DIGITS = '零一二三四五六七八九'
                        result += _ZH_DIGITS[int(digit)]
                    else:
                        result += ' ' + num2words(int(digit), lang=n2w_lang)
                return result
            except Exception:
                pass

    # 处理日期（三段斜杠数字）
    if '/' in num_str_clean:
        parts = num_str_clean.split('/')
        # 检查是否是日期格式（三段数字）
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            try:
                n2w_lang = _NUM2WORDS_LANG_MAP.get(lang, 'en')
                result_parts = []
                for part in parts:
                    result_parts.append(num2words(int(part), lang=n2w_lang))
                return ' '.join(result_parts)
            except Exception:
                pass

    # 处理分数
    if '/' in num_str_clean:
        parts = num_str_clean.split('/')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            try:
                n2w_lang = _NUM2WORDS_LANG_MAP.get(lang, 'en')
                numerator_int = int(parts[0])
                denominator_int = int(parts[1])

                # 特殊处理常见分数
                if lang == 'en':
                    if numerator_int == 1 and denominator_int == 2:
                        return "one half"
                    elif numerator_int == 1 and denominator_int == 4:
                        return "one quarter"
                    elif numerator_int == 3 and denominator_int == 4:
                        return "three quarters"

                # 通用处理
                numerator = num2words(numerator_int, lang=n2w_lang)
                # 分母用序数
                denominator = num2words(denominator_int, lang=n2w_lang, to='ordinal')
                return f"{numerator} {denominator}"
            except Exception:
                pass

    # 处理电话号码（连字符分隔的数字）
    if '-' in num_str_clean and all(p.isdigit() for p in num_str_clean.split('-')):
        # 电话号码逐位读
        digits = num_str_clean.replace('-', '')
        try:
            n2w_lang = _NUM2WORDS_LANG_MAP.get(lang, 'en')
            if lang == 'zh':
                _ZH_DIGITS = '零一二三四五六七八九'
                return ''.join(_ZH_DIGITS[int(d)] for d in digits)
            else:
                result = []
                for digit in digits:
                    result.append(num2words(int(digit), lang=n2w_lang))
                return ' '.join(result)
        except Exception:
            pass

    # 处理纯整数
    try:
        n = int(num_str_clean)
    except ValueError:
        return num_str

    # 检查是否是年份（使用原始字符串，包含逗号信息）
    if lang == 'en' and _is_year_like(num_str):
        return _expand_year_en(num_str_clean)

    n2w_lang = _NUM2WORDS_LANG_MAP.get(lang, 'en')

    # 序数（2nd、22nd）：按序数读法展开，否则 2nd 会被读成 "two"
    if ordinal_suffix:
        try:
            return num2words(n, lang=n2w_lang, to='ordinal')
        except Exception:
            return num2words(n, lang='en', to='ordinal')

    # 中文：逐位读数字（如电话号码、年份等场景更常见）
    if lang == 'zh':
        _ZH_DIGITS = '零一二三四五六七八九'
        return ''.join(_ZH_DIGITS[int(d)] for d in num_str_clean)

    try:
        try:
            return num2words(n, lang=n2w_lang)
        except Exception:
            return num2words(n, lang='en')
    except Exception:
        # 两种语言都展开失败时退回原数字串，不能把异常抛给调用方
        return num_str_clean


def _expand_decimal(text, lang):
    """处理小数"""
    n2w_lang = _NUM2WORDS_LANG_MAP.get(lang, 'en')
    try:
        n = float(text)
        return num2words(n, lang=n2w_lang)
    except Exception:
        return text


# ========== 缩写识别模块 ==========

# 全大写文本里"普通词"与"缩写串"无法靠形态区分（FREE NEW ITEMS
# 对比 USA UK），要靠词表：命中词表的按普通词读，未命中的按
# initialism 逐字母读。词表是 SCOWL 的 2-6 字母小写词（数据文件，
# 首次使用时加载；读不到文件时退化为全部逐字母读）。
_EN_COMMON_WORDS_PATH = Path(__file__).with_name("en_common_words.txt")
_en_common_words_cache = None


def _common_english_words():
    """Lowercase English word list used to disambiguate all-caps text."""
    global _en_common_words_cache
    if _en_common_words_cache is None:
        try:
            lines = _EN_COMMON_WORDS_PATH.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        _en_common_words_cache = frozenset(
            word for line in lines
            if (word := line.strip()) and not word.startswith("#")
        )
    return _en_common_words_cache


_APOSTROPHE_VARIANTS = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u02bc": "'", "\u02b9": "'",
    "\uff07": "'", "\u05f3": "'",
})


def _normalize_apostrophes(text):
    """把各种排版撇号归一化为 ASCII '，便于查词表。"""
    return text.translate(_APOSTROPHE_VARIANTS)


# 作为完整单词发音的缩写（不逐字母读）及其音节数
_WORD_ACRONYMS = {
    'NASA': 2, 'NATO': 2, 'ASAP': 4, 'IKEA': 3, 'OPEC': 2,
    'FIFA': 2, 'UNESCO': 3, 'UNICEF': 3, 'NAFTA': 2, 'SARS': 1,
    'AIDS': 1, 'RADAR': 2, 'LASER': 2, 'SCUBA': 2,
    'PIN': 1, 'SIM': 1, 'RAM': 1, 'ROM': 1,
    'LAN': 1, 'WAN': 1, 'JPEG': 2, 'GIF': 1,
    'COVID': 2, 'COV': 1,  # COVID-19, SARS-CoV-2
}

# 已知缩写/品牌名的音节数
_KNOWN_ABBREVIATIONS = {
    # 品牌名
    'iPhone': 2, 'iPad': 2, 'iPod': 2, 'iMac': 2,
    'macOS': 3, 'iOS': 3, 'YouTube': 2, 'WiFi': 2,
    'WhatsApp': 2, 'LinkedIn': 2, 'GitHub': 2, 'GitLab': 2,
    'JavaScript': 3, 'TypeScript': 2, 'PowerPoint': 3,
    'eBay': 2, 'PayPal': 2, 'FedEx': 2,

    # 学位/职称缩写
    'PhD': 3, 'Ph.D.': 3, 'Ph.D': 3,
    'Dr': 2, 'Dr.': 2,  # Doctor
    'Mr': 2, 'Mr.': 2,  # Mister
    'Mrs': 2, 'Mrs.': 2,  # Missus
    'Ms': 2, 'Ms.': 2,
    'Prof': 2, 'Prof.': 2,  # Professor

    # 技术缩写
    'LaTeX': 2, 'MySQL': 3, 'PostgreSQL': 4,
}


def _is_spelled_out_acronym(word):
    """判断是否是逐字母拼读的缩写"""
    # 检查是否在作为单词发音的缩写列表中
    if word.upper() in _WORD_ACRONYMS:
        return False

    clean = word.replace('.', '')
    if len(clean) < 2:
        return False

    # 全大写缩写：USA, FBI, MIT
    if clean.isupper() and 2 <= len(clean) <= 6:
        return True

    # 带点的缩写：U.S.A., Ph.D., Dr.
    if '.' in word and all(c.isupper() or c == '.' for c in word):
        return True

    # Mixed-case 缩写识别
    # 规则：至少2个大写字母，且大写字母占比 >= 50%
    upper_count = sum(1 for c in clean if c.isupper())
    alpha_count = sum(1 for c in clean if c.isalpha())

    if alpha_count >= 2 and upper_count >= 2:
        # PhD, eBay, iOS, macOS 等
        upper_ratio = upper_count / alpha_count
        if upper_ratio >= 0.5:
            return True

    return False


def _abbreviation_syllable_count(word, lang='en', context_has_lowercase=True):
    """计算缩写/品牌名的音节数

    context_has_lowercase=False 表示整段文本里没有一个普通小写词（如
    "FREE NEW ITEMS"）。全大写在这一上下文里更可能是排版风格而不是缩写，
    但只有查得到英语词表的普通词才按词读；'USA UK'、'API URL' 这类
    initialism 即使没有小写上下文也逐字母读。
    """
    # 规范化：去除尾部标点
    clean = word.rstrip('.,;:!?()[]{}"\'-')

    # 先检查已知缩写词典（使用规范化后的 token）
    if clean in _KNOWN_ABBREVIATIONS:
        return _KNOWN_ABBREVIATIONS[clean]

    # 作为单词发音的缩写（使用规范化后的 token）
    upper = clean.upper()
    if upper in _WORD_ACRONYMS:
        return _WORD_ACRONYMS[upper]

    # 全大写词只在有小写上下文时才逐字母拼读；没有小写上下文时，仅词表
    # 命中的普通词按词读，其余仍按 initialism 逐字母读。撇号形（DON'T /
    # IT'S / WOULDN'T）不可能是逐字母缩写，任何上下文都按词表判定。
    # The lookup normalizes typographic apostrophes so DON'T / IT'S match
    # the list's ASCII entries.
    if clean.isupper():
        normalized = _normalize_apostrophes(clean.lower())
        if "'" in normalized:
            if lang != 'en' or normalized in _common_english_words():
                return None
        elif 2 <= len(clean) <= 6 and not context_has_lowercase:
            if lang != 'en' or normalized in _common_english_words():
                return None

    # 逐字母拼读的缩写（使用规范化后的 token）
    if _is_spelled_out_acronym(clean):
        letters = [c for c in clean if c.isalpha()]
        if lang == 'en':
            return sum(_LETTER_SYLLABLES_EN.get(c.upper(), 1) for c in letters)
        return len(letters)

    return None


# ========== 阿拉伯语音节计数（从原版保留并改进） ==========

_AR_FATHA = 'َ'
_AR_DAMMA = 'ُ'
_AR_KASRA = 'ِ'
_AR_SHORT_VOWELS = {_AR_FATHA, _AR_DAMMA, _AR_KASRA}

_AR_FATHATAN = 'ً'
_AR_DAMMATAN = 'ٌ'
_AR_KASRATAN = 'ٍ'
_AR_TANWEEN = {_AR_FATHATAN, _AR_DAMMATAN, _AR_KASRATAN}

_AR_SUKUN = 'ْ'
_AR_SHADDA = 'ّ'
_AR_SUPERSCRIPT_ALEF = 'ٰ'

_AR_DIACRITICS_RE = re.compile(r'[ً-ٰٟٓ]')

_AR_ALEF = 'ا'
_AR_WAW = 'و'
_AR_YAA = 'ي'
_AR_ALEF_MAQSURA = 'ى'

_AR_ALEF_MADDA = 'آ'
_AR_TAA_MARBUTA = 'ة'
_AR_TATWEEL = 'ـ'

_AR_LETTER_RE = re.compile(
    r'[ء-غف-ي'
    r'ً-ٰٟ'
    r'ٱ-ۓە-ۿ'
    r'ݐ-ݿࢠ-ࣿ'
    r'ﭐ-﷿ﹰ-﻿]+'
)


def _ar_is_letter(ch):
    cp = ord(ch)
    return ((0x0621 <= cp <= 0x063A)
            or (0x0641 <= cp <= 0x064A)
            or (0x0671 <= cp <= 0x06D3)
            or (0x06D5 <= cp <= 0x06FF))


def _ar_is_fully_vocalized(word):
    consonant_count = 0
    vocalized_count = 0
    chars = list(word)
    n = len(chars)

    for i, ch in enumerate(chars):
        if (_ar_is_letter(ch)
                and ch not in (_AR_ALEF, _AR_WAW, _AR_YAA, _AR_ALEF_MAQSURA,
                               _AR_ALEF_MADDA, _AR_TAA_MARBUTA)):
            consonant_count += 1
            if i + 1 < n and _AR_DIACRITICS_RE.match(chars[i + 1]):
                vocalized_count += 1

    if consonant_count == 0:
        return False
    return vocalized_count / consonant_count > 0.5


def _ar_vocalized_syllables(word):
    syllables = 0
    covered = False

    for i, ch in enumerate(word):
        if ch in _AR_SHORT_VOWELS:
            syllables += 1
            covered = True
        elif ch in _AR_TANWEEN:
            syllables += 1
            covered = True
        elif ch == _AR_SUPERSCRIPT_ALEF:
            if not covered:
                syllables += 1
            covered = False
        elif ch == _AR_ALEF_MADDA:
            syllables += 1
            covered = False
        elif ch in (_AR_ALEF, _AR_ALEF_MAQSURA):
            if i > 0 and not covered:
                syllables += 1
            covered = False
        elif _ar_is_letter(ch):
            covered = False

    return max(1, syllables)


def _ar_unvocalized_syllables(word):
    clean = _AR_DIACRITICS_RE.sub('', word)
    clean = clean.replace(_AR_TATWEEL, '')
    if not clean:
        return 0

    letters = list(clean)
    n = len(letters)

    if n == 0:
        return 0
    if n <= 2:
        return 1

    skeleton = []
    for i, ch in enumerate(letters):
        is_first = (i == 0)

        if ch == _AR_ALEF_MAQSURA:
            skeleton.append('V')
        elif ch == _AR_ALEF_MADDA:
            skeleton.append('V')
        elif ch == _AR_ALEF:
            skeleton.append('C' if is_first else 'V')
        elif ch == _AR_TAA_MARBUTA:
            skeleton.append('V')
        elif ch in (_AR_WAW, _AR_YAA):
            if (ch == _AR_YAA
                    and i == n - 2
                    and i + 1 < n
                    and letters[i + 1] == _AR_TAA_MARBUTA):
                skeleton.append('C')
            elif (ch == _AR_WAW
                    and i == n - 2
                    and i + 1 < n
                    and letters[i + 1] == _AR_TAA_MARBUTA):
                skeleton.append('C')
            elif is_first:
                skeleton.append('C')
            elif skeleton and skeleton[-1] == 'C':
                skeleton.append('V')
            else:
                skeleton.append('C')
        else:
            skeleton.append('C')

    v_positions = [i for i, x in enumerate(skeleton) if x == 'V']

    if not v_positions:
        return max(1, (len(skeleton) + 1) // 2)

    syllables = len(v_positions)
    syllables += v_positions[0] // 2

    for k in range(1, len(v_positions)):
        gap = v_positions[k] - v_positions[k - 1] - 1
        syllables += gap // 2

    post_c = len(skeleton) - v_positions[-1] - 1
    if (post_c == 1
            and len(v_positions) == 1
            and v_positions[0] == 1
            and len(skeleton) == 3):
        syllables += 1
    else:
        syllables += post_c // 2

    return max(1, syllables)


def _arabic_word_syllables(word):
    if not word:
        return 0
    if _AR_DIACRITICS_RE.search(word):
        if _ar_is_fully_vocalized(word):
            return _ar_vocalized_syllables(word)
    return _ar_unvocalized_syllables(word)


# ========== 日语音节计数（从原版保留并改进） ==========

_DIGIT_TO_KANA = {
    '0': 'ゼロ', '1': 'いち', '2': 'に', '3': 'さん', '4': 'よん',
    '5': 'ご', '6': 'ろく', '7': 'なな', '8': 'はち', '9': 'きゅう'
}

# One Tagger per thread. MeCab keeps parse state on the Tagger, so sharing a
# single instance across the evaluator's thread pool corrupts Japanese mora
# counts nondeterministically -- only syllable_order reads them, so the symptom
# was zh->ja instances flipping between runs at the default concurrency.
_thread_state = threading.local()


def _get_tagger():
    tagger = getattr(_thread_state, "tagger", None)
    if tagger is None:
        tagger = fugashi.Tagger()
        _thread_state.tagger = tagger
    return tagger


def _count_japanese_mora(token):
    has_kana = any('぀' <= c <= 'ゟ' or '゠' <= c <= 'ヿ' for c in token)
    if not has_kana:
        return len(token)

    mora_count = 0
    i = 0
    length = len(token)

    while i < length:
        char = token[i]
        if i + 1 < length and token[i + 1] in 'ゃゅょャュョ':
            mora_count += 1
            i += 2
        elif char in 'っッんンー':
            mora_count += 1
            i += 1
        elif '぀' <= char <= 'ゟ' or '゠' <= char <= 'ヿ':
            mora_count += 1
            i += 1
        else:
            i += 1

    return mora_count


def _japanese_syllable_count(text):
    total_mora = 0
    parsed_nodes = _get_tagger()(text)
    for word in parsed_nodes:
        reading = getattr(word.feature, 'kana', None)
        if reading is None:
            reading = getattr(word.feature, 'pronBase', None)
        if reading is None:
            reading = word.surface

        word_mora = _count_japanese_mora(reading)
        total_mora += word_mora

    return total_mora


# ========== 各语言计算器 ==========


# 西语常见词音节词典（pyphen 不准确的词）
_SPANISH_SYLLABLES = {
    'país': 2,      # pa-ís
    'río': 2,       # rí-o
    'pingüino': 3,  # pin-güi-no
    'día': 2,       # dí-a
    'maría': 3,     # Ma-rí-a
    'había': 3,     # ha-bí-a
    'tenía': 3,     # te-ní-a
    'podía': 3,     # po-dí-a
    'decía': 3,     # de-cí-a
    'hacía': 3,     # ha-cí-a
    'raíz': 2,      # ra-íz
    'maíz': 2,      # ma-íz
    'baúl': 2,      # ba-úl
    'raúl': 2,      # Ra-úl
}

_PYPHEN_LANG_MAP = {
    'en': 'en_US',
    'de': 'de_DE',
    'fr': 'fr_FR',
    'es': 'es_ES',
}


def _ordinary_caps_context(text):
    """整段都是全大写词（标题、口号）时为真：此时全大写 token 按普通词计数，
    否则仍按缩写逐字母读（USA = 3）。_count_european 与 cal_syllable_details
    共用同一判定，保证 total 与逐词 breakdown 口径一致。"""
    segments = _parse_mixed_content(text)
    latin_words = [w for seg, kind in segments if kind == 'latin' for w in seg.split()]
    alpha_words = [w for w in latin_words if any(c.isalpha() for c in w)]
    return len(alpha_words) >= 2 and all(
        w.rstrip('.,;:!?()[]{}"\'-').isupper() for w in alpha_words
    )


def _count_european(text, lang):
    """英、德、法、西等欧洲语言的音节计数"""
    pyphen_lang = _PYPHEN_LANG_MAP.get(lang, 'en_US')

    segments = _parse_mixed_content(text)
    total = 0

    # 整段都是全大写词（标题、口号）时按普通词计数；只要出现一个小写词，
    # 全大写 token 仍按缩写逐字母读（USA = 3）。
    _ordinary_caps = _ordinary_caps_context(text)

    for segment, script_type in segments:
        if script_type == 'number':
            expanded = _expand_number(segment, lang)
            # 按空格和连字符分割
            words = re.split(r'[\s\-]+', expanded)
            for w in words:
                clean_w = w.strip(',-')
                if clean_w and clean_w.isalpha():
                    total += _pyphen_syllable_count(clean_w, pyphen_lang)
        elif script_type == 'latin':
            words = segment.split()
            for w in words:
                abbr_count = _abbreviation_syllable_count(
                    w, lang, context_has_lowercase=not _ordinary_caps)
                if abbr_count is not None:
                    total += abbr_count
                elif w.isupper():
                    # 全大写普通词按小写查连字符词典（词典只有小写形式）
                    total += _pyphen_syllable_count(w.lower(), pyphen_lang)
                else:
                    total += _pyphen_syllable_count(w, pyphen_lang)
        elif script_type == 'han':
            # 只计算汉字，不包括标点；范围与 _SCRIPT_RANGES 的 han 一致
            han_chars = re.findall(r'[一-鿿㐀-䶿]', segment)
            total += len(han_chars)
        elif script_type == 'arabic':
            # 混合内容中的阿拉伯语
            ar_words = _AR_LETTER_RE.findall(segment)
            for w in ar_words:
                total += _arabic_word_syllables(w)
        elif script_type == 'kana':
            # 混合内容中的日语假名
            total += _japanese_syllable_count(segment)

    return total




def _expand_and_count_chinese(num_str):
    """展开数字并计算中文音节数"""
    # 处理小数
    if '.' in num_str:
        parts = num_str.split('.')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            count = 0
            # 整数部分逐位读
            for digit in parts[0]:
                count += 1
            # 小数点："点"
            count += 1
            # 小数部分逐位读
            for digit in parts[1]:
                count += 1
            return count

    # 其他数字格式：逐位读
    digits = re.findall(r'\d', num_str)
    return len(digits)


def _count_chinese(text, lang='zh'):
    """中文音节计数（改进版：处理数字和混合内容）"""
    segments = _parse_mixed_content(text)
    total = 0

    for segment, script_type in segments:
        if script_type == 'han':
            # 只计算汉字，不包括标点
            han_chars = re.findall(r'[一-鿿]', segment)
            total += len(han_chars)
        elif script_type == 'number':
            # 统一使用 _expand_and_count_chinese 处理
            total += _expand_and_count_chinese(segment)
        elif script_type == 'latin':
            words = segment.split()
            for w in words:
                abbr_count = _abbreviation_syllable_count(w, 'en')
                if abbr_count is not None:
                    total += abbr_count
                else:
                    total += _pyphen_syllable_count(w, 'en_US')
        elif script_type == 'kana':
            # 混合内容中的日语假名
            total += _japanese_syllable_count(segment)
        elif script_type == 'arabic':
            # 混合内容中的阿拉伯语
            ar_words = _AR_LETTER_RE.findall(segment)
            for w in ar_words:
                total += _arabic_word_syllables(w)

    return total


def _count_arabic(text, lang='ar'):
    """阿拉伯语音节计数（改进版：处理混合内容）"""
    segments = _parse_mixed_content(text)
    total = 0

    for segment, script_type in segments:
        if script_type == 'arabic':
            words = _AR_LETTER_RE.findall(segment)
            for w in words:
                total += _arabic_word_syllables(w)
        elif script_type == 'number':
            expanded = _expand_number(segment, 'ar')
            ar_words = _AR_LETTER_RE.findall(expanded)
            if ar_words:
                for w in ar_words:
                    total += _arabic_word_syllables(w)
            else:
                # num2words 可能返回拉丁字母，用英语计算
                for w in expanded.split():
                    if w.isalpha():
                        total += _pyphen_syllable_count(w, 'en_US')
        elif script_type == 'latin':
            words = segment.split()
            for w in words:
                abbr_count = _abbreviation_syllable_count(w, 'en')
                if abbr_count is not None:
                    total += abbr_count
                else:
                    total += _pyphen_syllable_count(w, 'en_US')
        elif script_type == 'han':
            # 混合内容中的汉字
            han_chars = re.findall(r'[一-鿿]', segment)
            total += len(han_chars)
        elif script_type == 'kana':
            # 混合内容中的日语假名
            total += _japanese_syllable_count(segment)

    return total


def _count_japanese_v2(text, lang='ja'):
    """日语音节计数（改进版：处理混合内容）"""
    segments = _parse_mixed_content(text)

    # 合并连续的 han 和 kana 段落，让 fugashi 整体处理
    merged_segments = []
    i = 0
    while i < len(segments):
        segment, script_type = segments[i]

        if script_type in ('han', 'kana'):
            # 收集连续的 han/kana 段落
            japanese_text = segment
            j = i + 1
            while j < len(segments) and segments[j][1] in ('han', 'kana'):
                japanese_text += segments[j][0]
                j += 1
            merged_segments.append((japanese_text, 'japanese'))
            i = j
        else:
            merged_segments.append((segment, script_type))
            i += 1

    # 计算音节
    total = 0
    for segment, script_type in merged_segments:
        if script_type == 'japanese':
            total += _japanese_syllable_count(segment)
        elif script_type == 'number':
            # 日语中数字通过 fugashi 处理更准确
            total += _japanese_syllable_count(segment)
        elif script_type == 'latin':
            words = segment.split()
            for w in words:
                abbr_count = _abbreviation_syllable_count(w, 'en')
                if abbr_count is not None:
                    total += abbr_count
                else:
                    total += _pyphen_syllable_count(w, 'en_US')

    return total


# ========== 公共 API ==========

def cal_syllable_count(text, lang='en'):
    if not text or not text.strip():
        return 0

    text = text.strip()

    if lang.lower() == 'zh':
        return _count_chinese(text)
    elif lang.lower() == 'ja':
        return _count_japanese_v2(text)
    elif lang.lower() == 'ar':
        return _count_arabic(text)
    else:
        return _count_european(text, lang.lower())


def cal_syllable_details(text, lang='en'):
    """返回详细的音节分解信息"""
    if not text or not text.strip():
        return {
            'total_syllables': 0,
            'word_count': 0,
            'syllables_per_word': 0,
            'syllable_breakdown': []
        }

    text = text.strip()
    total_syllables = cal_syllable_count(text, lang)

    # 逐词 breakdown 与 total 共用同一套全大写上下文判定，避免口径不一。
    context_has_lowercase = not _ordinary_caps_context(text)

    # 根据语言使用不同的分解策略
    breakdown = []

    if lang.lower() == 'zh':
        # 中文：按混合内容分段
        segments = _parse_mixed_content(text)
        for segment, script_type in segments:
            if script_type == 'han':
                # 汉字逐个计数（只计算汉字，不包括标点）
                han_chars = re.findall(r'[一-鿿]', segment)
                for char in han_chars:
                    breakdown.append({'word': char, 'syllables': 1})
            elif script_type == 'number':
                # 使用统一的计数逻辑
                syllables = _expand_and_count_chinese(segment)
                breakdown.append({
                    'word': segment,
                    'syllables': syllables,
                })
            elif script_type == 'latin':
                words = segment.split()
                for w in words:
                    abbr_count = _abbreviation_syllable_count(w, 'en', context_has_lowercase=context_has_lowercase)
                    if abbr_count is not None:
                        syllables = abbr_count
                    else:
                        syllables = _pyphen_syllable_count(w, 'en_US')
                    breakdown.append({'word': w, 'syllables': syllables})
            elif script_type == 'kana':
                # 混合内容中的日语假名
                syllables = _japanese_syllable_count(segment)
                breakdown.append({'word': segment, 'syllables': syllables})
            elif script_type == 'arabic':
                # 混合内容中的阿拉伯语
                ar_words = _AR_LETTER_RE.findall(segment)
                for w in ar_words:
                    syllables = _arabic_word_syllables(w)
                    breakdown.append({'word': w, 'syllables': syllables})

    elif lang.lower() == 'ja':
        # 日语：使用 fugashi 分词
        segments = _parse_mixed_content(text)

        # 合并连续的 han 和 kana 段落
        merged_segments = []
        i = 0
        while i < len(segments):
            segment, script_type = segments[i]
            if script_type in ('han', 'kana'):
                japanese_text = segment
                j = i + 1
                while j < len(segments) and segments[j][1] in ('han', 'kana'):
                    japanese_text += segments[j][0]
                    j += 1
                merged_segments.append((japanese_text, 'japanese'))
                i = j
            else:
                merged_segments.append((segment, script_type))
                i += 1

        # 对每个段落计算音节
        for segment, script_type in merged_segments:
            if script_type == 'japanese':
                syllables = _japanese_syllable_count(segment)
                breakdown.append({'word': segment, 'syllables': syllables})
            elif script_type == 'number':
                syllables = _japanese_syllable_count(segment)
                breakdown.append({'word': segment, 'syllables': syllables})
            elif script_type == 'latin':
                words = segment.split()
                for w in words:
                    abbr_count = _abbreviation_syllable_count(w, 'en', context_has_lowercase=context_has_lowercase)
                    if abbr_count is not None:
                        syllables = abbr_count
                    else:
                        syllables = _pyphen_syllable_count(w, 'en_US')
                    breakdown.append({'word': w, 'syllables': syllables})
            elif script_type == 'han':
                # 混合内容中的汉字
                han_chars = re.findall(r'[一-鿿]', segment)
                for char in han_chars:
                    breakdown.append({'word': char, 'syllables': 1})
            elif script_type == 'kana':
                # 混合内容中的日语假名
                syllables = _japanese_syllable_count(segment)
                breakdown.append({'word': segment, 'syllables': syllables})

    elif lang.lower() == 'ar':
        # 阿拉伯语
        segments = _parse_mixed_content(text)
        for segment, script_type in segments:
            if script_type == 'arabic':
                words = _AR_LETTER_RE.findall(segment)
                for w in words:
                    syllables = _arabic_word_syllables(w)
                    breakdown.append({'word': w, 'syllables': syllables})
            elif script_type == 'number':
                expanded = _expand_number(segment, 'ar')
                ar_words = _AR_LETTER_RE.findall(expanded)
                if ar_words:
                    syllables = sum(_arabic_word_syllables(w) for w in ar_words)
                else:
                    # 英语展开
                    syllables = sum(_pyphen_syllable_count(w, 'en_US') for w in expanded.split() if w.isalpha())
                breakdown.append({
                    'word': segment,
                    'expanded': expanded,
                    'syllables': syllables,
                })
            elif script_type == 'latin':
                words = segment.split()
                for w in words:
                    abbr_count = _abbreviation_syllable_count(w, 'en', context_has_lowercase=context_has_lowercase)
                    if abbr_count is not None:
                        syllables = abbr_count
                    else:
                        syllables = _pyphen_syllable_count(w, 'en_US')
                    breakdown.append({'word': w, 'syllables': syllables})
            elif script_type == 'han':
                # 混合内容中的汉字
                han_chars = re.findall(r'[一-鿿]', segment)
                for char in han_chars:
                    breakdown.append({'word': char, 'syllables': 1})
            elif script_type == 'kana':
                # 混合内容中的日语假名
                syllables = _japanese_syllable_count(segment)
                breakdown.append({'word': segment, 'syllables': syllables})

    else:
        # 欧洲语言（英、德、法、西等）
        pyphen_lang = _PYPHEN_LANG_MAP.get(lang.lower(), 'en_US')
        segments = _parse_mixed_content(text)

        for segment, script_type in segments:
            if script_type == 'number':
                expanded = _expand_number(segment, lang)
                words = re.split(r'[\s\-]+', expanded)
                syllables = 0
                for w in words:
                    clean_w = w.strip(',-')
                    if clean_w and clean_w.isalpha():
                        syllables += _pyphen_syllable_count(clean_w, pyphen_lang)
                breakdown.append({
                    'word': segment,
                    'expanded': expanded,
                    'syllables': syllables,
                })
            elif script_type == 'latin':
                words = segment.split()
                for w in words:
                    abbr_count = _abbreviation_syllable_count(w, lang, context_has_lowercase=context_has_lowercase)
                    if abbr_count is not None:
                        syllables = abbr_count
                    else:
                        syllables = _pyphen_syllable_count(w, pyphen_lang)
                    breakdown.append({'word': w, 'syllables': syllables})
            elif script_type == 'han':
                # 混合内容中的汉字
                han_chars = re.findall(r'[一-鿿]', segment)
                for char in han_chars:
                    breakdown.append({'word': char, 'syllables': 1})
            elif script_type == 'arabic':
                # 混合内容中的阿拉伯语
                ar_words = _AR_LETTER_RE.findall(segment)
                for w in ar_words:
                    syllables = _arabic_word_syllables(w)
                    breakdown.append({'word': w, 'syllables': syllables})
            elif script_type == 'kana':
                # 混合内容中的日语假名
                syllables = _japanese_syllable_count(segment)
                breakdown.append({'word': segment, 'syllables': syllables})

    word_count = len(breakdown)
    avg_syllables = round(total_syllables / word_count, 2) if word_count > 0 else 0

    return {
        'total_syllables': total_syllables,
        'word_count': word_count,
        'syllables_per_word': avg_syllables,
        'syllable_breakdown': breakdown,
    }


# ========== 测试入口 ==========

if __name__ == "__main__":
    # 基础测试用例（和原版一致）
    test_cases = [
        ("你好世界 Hello World", "zh"),
        ("Hello World", "en"),
        ("The quick brown fox jumps over the lazy dog", "en"),
        ("Der schnelle braune Fuchs springt über den faulen Hund", "de"),
        ("Le renard brun rapide saute par-dessus le chien paresseux", "fr"),
        ("مرحبا بك في العالم", "ar"),
    ]

    # 数字展开测试
    number_test_cases = [
        ("2024", "en"),
        ("100", "en"),
        ("I have 3 cats", "en"),
        ("2024年", "zh"),
        ("我有100个苹果", "zh"),
        ("123 مرحبا", "ar"),
    ]

    # 缩写测试
    abbreviation_test_cases = [
        ("USA", "en"),
        ("BMW", "en"),
        ("NASA", "en"),
        ("iPhone", "en"),
        ("The CEO of IBM", "en"),
    ]

    # 混合内容测试
    mixed_test_cases = [
        ("Hello世界2024年", "zh"),
        ("iPhone 15 Pro Max", "en"),
        ("مرحبا Hello 2024", "ar"),
    ]

    # 日语测试
    japanese_test_cases = [
        ("こんにちは", "ja"),
        ("きょう", "ja"),
        ("きっと", "ja"),
        ("お母さん", "ja"),
        ("コーヒー", "ja"),
        ("東京", "ja"),
        ("123", "ja"),
        ("Hello世界", "ja"),
    ]

    print("=" * 70)
    print("音节计数 V2 测试结果")
    print("=" * 70)

    for text, lang in test_cases:
        count = cal_syllable_count(text, lang)
        print(f"[{lang}] '{text}' → {count} 音节")

    print("\n" + "=" * 70)
    print("数字展开测试")
    print("=" * 70)

    for text, lang in number_test_cases:
        count = cal_syllable_count(text, lang)
        print(f"[{lang}] '{text}' → {count} 音节")

    print("\n" + "=" * 70)
    print("缩写识别测试")
    print("=" * 70)

    for text, lang in abbreviation_test_cases:
        count = cal_syllable_count(text, lang)
        print(f"[{lang}] '{text}' → {count} 音节")

    print("\n" + "=" * 70)
    print("混合内容测试")
    print("=" * 70)

    for text, lang in mixed_test_cases:
        count = cal_syllable_count(text, lang)
        details = cal_syllable_details(text, lang)
        print(f"[{lang}] '{text}' → {count} 音节")
        for item in details['syllable_breakdown']:
            extra = f" (展开: {item['expanded']})" if 'expanded' in item else ""
            print(f"    '{item['word']}': {item['syllables']} 音节{extra}")

    print("\n" + "=" * 70)
    print("日语测试")
    print("=" * 70)

    for text, lang in japanese_test_cases:
        count = cal_syllable_count(text, lang)
        print(f"[{lang}] '{text}' → {count} 音拍")

    print("\n" + "=" * 70)
