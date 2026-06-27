"""
Dreamina Auto Register - 随机数据生成器
"""
import random
import string
import re
from datetime import date, timedelta
from typing import Optional
from app.core.config import settings


class RandomGenerator:
    """随机数据生成器"""
    
    # 安全的特殊字符（避免可能导致问题的字符）
    SAFE_SPECIAL_CHARS = "!@#$%&*"
    
    @staticmethod
    def generate_random_string(length: int, chars: str = None) -> str:
        """生成随机字符串"""
        if chars is None:
            chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    @classmethod
    def generate_email_local_part(cls, pattern: str = "reg_{random6}") -> str:
        """
        根据模式生成邮箱本地部分
        
        支持的占位符:
        - {random6}: 6 位随机字母数字
        - {random8}: 8 位随机字母数字
        - {timestamp}: 时间戳后 6 位
        """
        result = pattern
        
        # 替换 {randomN} 占位符 (Letters + Digits)
        random_pattern = re.compile(r'\{random(\d+)\}')
        while True:
            match = random_pattern.search(result)
            if not match:
                break
            length = int(match.group(1))
            random_str = cls.generate_random_string(length).lower()
            result = result.replace(match.group(0), random_str, 1)

        # 替换 {letterN} 占位符 (Letters only)
        letter_pattern = re.compile(r'\{letter(\d+)\}')
        while True:
            match = letter_pattern.search(result)
            if not match:
                break
            length = int(match.group(1))
            random_str = cls.generate_random_string(length, string.ascii_lowercase)
            result = result.replace(match.group(0), random_str, 1)

        # 替换 {digitN} 占位符 (Digits only)
        digit_pattern = re.compile(r'\{digit(\d+)\}')
        while True:
            match = digit_pattern.search(result)
            if not match:
                break
            length = int(match.group(1))
            random_str = cls.generate_random_string(length, string.digits)
            result = result.replace(match.group(0), random_str, 1)
        
        # 替换 {timestamp} 占位符
        if "{timestamp}" in result:
            import time
            ts = str(int(time.time()))[-6:]
            result = result.replace("{timestamp}", ts)
        
        return result
    
    @classmethod
    def generate_email(cls, domain: str, pattern: str = "reg_{random6}") -> str:
        """生成完整邮箱地址"""
        local_part = cls.generate_email_local_part(pattern)
        return f"{local_part}@{domain}"
    
    @classmethod
    def generate_password(cls, length: int = None, include_special: bool = None) -> str:
        """
        生成符合 Dreamina 要求的密码
        
        要求：
        - 至少包含大写字母
        - 至少包含小写字母
        - 至少包含数字
        - 可选包含特殊字符
        """
        if length is None:
            length = settings.password_length
        if include_special is None:
            include_special = settings.password_include_special
        
        # 确保至少包含每种类型各一个
        password_chars = [
            random.choice(string.ascii_uppercase),  # 大写
            random.choice(string.ascii_lowercase),  # 小写
            random.choice(string.digits),           # 数字
        ]
        
        if include_special:
            password_chars.append(random.choice(cls.SAFE_SPECIAL_CHARS))
        
        # 填充剩余长度
        remaining_length = length - len(password_chars)
        all_chars = string.ascii_letters + string.digits
        if include_special:
            all_chars += cls.SAFE_SPECIAL_CHARS
        
        password_chars.extend(random.choice(all_chars) for _ in range(remaining_length))
        
        # 打乱顺序
        random.shuffle(password_chars)
        
        return ''.join(password_chars)
    
    @staticmethod
    def generate_birth_date(min_age: int = 18, max_age: int = 45) -> date:
        """
        生成随机出生日期
        
        Args:
            min_age: 最小年龄（默认 18）
            max_age: 最大年龄（默认 45）
        
        Returns:
            出生日期
        """
        today = date.today()
        
        # 计算年龄范围对应的日期
        min_birth_date = date(today.year - max_age, 1, 1)
        max_birth_date = date(today.year - min_age, 12, 31)
        
        # 随机天数
        delta = (max_birth_date - min_birth_date).days
        random_days = random.randint(0, delta)
        
        birth_date = min_birth_date + timedelta(days=random_days)
        
        # 确保日期有效（处理闰年等边界情况）
        # 如果是 2 月 29 日但不是闰年，调整为 2 月 28 日
        if birth_date.month == 2 and birth_date.day == 29:
            try:
                date(birth_date.year, 2, 29)
            except ValueError:
                birth_date = date(birth_date.year, 2, 28)
        
        return birth_date
    
    @staticmethod
    def generate_birth_date_parts(min_age: int = 18, max_age: int = 45) -> dict:
        """
        生成出生日期的年月日部分
        
        Returns:
            {"year": "1990", "month": "06", "day": "15"}
        """
        bd = RandomGenerator.generate_birth_date(min_age, max_age)
        return {
            "year": str(bd.year),
            "month": str(bd.month).zfill(2),
            "day": str(bd.day).zfill(2)
        }


# 便捷函数
random_generator = RandomGenerator()

def generate_email(domain: str, pattern: str = "reg_{random6}") -> str:
    return random_generator.generate_email(domain, pattern)

def generate_email_prefix(pattern: str = "reg_{random6}") -> str:
    """生成邮箱前缀（本地部分）"""
    return random_generator.generate_email_local_part(pattern)

def generate_password() -> str:
    return random_generator.generate_password()

def generate_birth_date() -> date:
    return random_generator.generate_birth_date()

def generate_birth_date_parts() -> dict:
    """生成出生日期的年月日部分（已补零）"""
    return random_generator.generate_birth_date_parts()
