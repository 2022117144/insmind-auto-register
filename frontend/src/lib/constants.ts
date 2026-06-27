
// Region mappings
export const REGION_MAP: Record<string, { flag: string; name: string; code: string }> = {
    'JP': { flag: 'https://flagcdn.com/w40/jp.png', name: '日本', code: 'JP' },
    'US': { flag: 'https://flagcdn.com/w40/us.png', name: '美国', code: 'US' },
    'CA': { flag: 'https://flagcdn.com/w40/ca.png', name: '加拿大', code: 'CA' },
    'SG': { flag: 'https://flagcdn.com/w40/sg.png', name: '新加坡', code: 'SG' },
    'HK': { flag: 'https://flagcdn.com/w40/hk.png', name: '香港', code: 'HK' },
    'TW': { flag: 'https://flagcdn.com/w40/tw.png', name: '台湾', code: 'TW' },
    'KR': { flag: 'https://flagcdn.com/w40/kr.png', name: '韩国', code: 'KR' },
    'GB': { flag: 'https://flagcdn.com/w40/gb.png', name: '英国', code: 'GB' },
    'DE': { flag: 'https://flagcdn.com/w40/de.png', name: '德国', code: 'DE' },
    'CN': { flag: 'https://flagcdn.com/w40/cn.png', name: '中国', code: 'CN' },
};

export const parseRegion = (regionTag: string | undefined) => {
    if (!regionTag) return null;
    const normalizedTag = regionTag.toUpperCase().replace(/\s+/g, '');
    if (normalizedTag === 'DEFAULT' || normalizedTag === 'UNKNOWN') return null;
    for (const [key, value] of Object.entries(REGION_MAP)) {
        if (normalizedTag.includes(key)) return value;
    }
    // Expanded parsing logic from Tasks.tsx
    if (normalizedTag.includes('日本') || normalizedTag.includes('TOKYO')) return REGION_MAP['JP'];
    if (normalizedTag.includes('美国') || normalizedTag.includes('USA')) return REGION_MAP['US'];
    if (normalizedTag.includes('加拿大') || normalizedTag.includes('CANADA')) return REGION_MAP['CA'];
    if (normalizedTag.includes('新加坡') || normalizedTag.includes('SINGAPORE')) return REGION_MAP['SG'];
    if (normalizedTag.includes('香港') || normalizedTag.includes('HONGKONG')) return REGION_MAP['HK'];
    if (normalizedTag.includes('台湾') || normalizedTag.includes('TAIWAN')) return REGION_MAP['TW'];
    if (normalizedTag.includes('韩国') || normalizedTag.includes('KOREA')) return REGION_MAP['KR'];
    if (normalizedTag.includes('英国') || normalizedTag.includes('UK') || normalizedTag.includes('GB')) return REGION_MAP['GB'];
    if (normalizedTag.includes('德国') || normalizedTag.includes('GERMANY')) return REGION_MAP['DE'];
    if (normalizedTag.includes('中国') || normalizedTag.includes('CHINA') || normalizedTag.includes('CN')) return REGION_MAP['CN'];

    return null;
};
