请审查以下前端 TypeScript/TSX 文件。

项目背景: insMind (稿定设计海外版) 自动注册系统前端
文件路径: frontend/src/pages/Settings.tsx
文件类型: settings

审查重点：
- routes/translations 文件：检查路由配置、导入路径、翻译键是否完整
- 页面组件文件：检查 API 对接、UI 一致性、错误处理、状态管理
- 确认无遗留 Dreamina 名称 (jimeng、dreamina 等)

文件内容:
```typescript
import { useEffect, useState } from 'react'
import {
    Loader2,
    Languages,
    Lock,
    Zap,
    Cpu,
    Cloud
} from 'lucide-react'
import { settingsApi, Settings } from '../services/api'
import { useLanguage } from '../contexts/LanguageContext'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"


export default function SettingsPage() {
    const [settings, setSettings] = useState<Settings | null>(null)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const { language, setLanguage, t } = useLanguage()

    const [secrets, setSecrets] = useState({
        clash_secret: '',
        cf_api_token: ''
    })

    useEffect(() => {
        fetchSettings()
    }, [])

    const fetchSettings = async () => {
        try {
            const data = await settingsApi.get()
            setSettings(data)
            setSecrets({
                clash_secret: data.clash_secret || '',
                cf_api_token: data.cf_api_token || ''
            })
        } catch (error) {
            console.error('Failed to fetch settings:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleSave = async () => {
        if (!settings) return
        setSaving(true)
        try {
            await settingsApi.update({
                ...settings,
                ...secrets
            })
        } catch (error) {
            console.error('Save failed:', error)
        } finally {
            setSaving(false)
        }
    }

    if (loading || !settings) {
        return (
            <div className="flex h-[50vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">{t('settings.title')}</h2>
                    <p className="text-muted-foreground">{t('settings.subtitle')}</p>
                </div>
                <Button onClick={handleSave} disabled={saving}>
                    {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {t('settings.commit')}
                </Button>
            </div>

            <Tabs defaultValue="general" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="general">{t('settings.tabs.general')}</TabsTrigger>
                    <TabsTrigger value="engine">{t('settings.tabs.engine')}</TabsTrigger>
                    <TabsTrigger value="proxy">{t('settings.tabs.proxy')}</TabsTrigger>
                    <TabsTrigger value="cloud">{t('settings.tabs.cloud')}</TabsTrigger>
                </TabsList>

                <TabsContent value="general" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Languages className="h-5 w-5" />
                                {t('settings.language')}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="grid gap-6">
                            <div className="grid grid-cols-2 gap-4">
                                <Button
                                    variant={language === 'en' ? 'default' : 'outline'}
                                    className="h-24 flex flex-col gap-2"
                                    onClick={() => setLanguage('en')}
                                >
                                    <span className="text-2xl">🇺🇸</span>
                                    <span>{t('settings.lang.en')}</span>
                                </Button>
                                <Button
                                    variant={language === 'zh' ? 'default' : 'outline'}
                                    className="h-24 flex flex-col gap-2"
                                    onClick={() => setLanguage('zh')}
                                >
                                    <span className="text-2xl">🇨🇳</span>
                                    <span>{t('settings.lang.zh')}</span>
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Lock className="h-5 w-5" />
                                {t('settings.account_gen')}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid gap-2">
                                <Label>{t('settings.pwd_len')}</Label>
                                <Input
                                    type="number"
                                    value={settings.password_length}
                                    onChange={e => setSettings({ ...settings, password_length: Number(e.target.value) })}
                                />
                            </div>
                            <div className="flex items-center justify-between rounded-lg border p-4">
                                <div className="space-y-0.5">
                                    <Label className="text-base">{t('settings.include_special')}</Label>
                                    <p className="text-sm text-muted-foreground">
                                        {t('settings.include_special_desc')}
                                    </p>
                                </div>
                                <Switch
                                    checked={settings.password_include_special}
                                    onCheckedChange={(checked) => setSettings({ ...settings, password_include_special: checked })}
                                />
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="engine" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Zap className="h-5 w-5" />
                                {t('settings.engine')}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-2">
                                <Label>insMind API 地址</Label>
                                <Input
                                    value={settings.insmind_url}
                                    onChange={e => setSettings({ ...settings, insmind_url: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>注册超时（秒）</Label>
                                <Input
                                    type="number"
                                    value={settings.insmind_register_timeout}
                                    onChange={e => setSettings({ ...settings, insmind_register_timeout: Number(e.target.value) })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>验证等待缓冲（秒）</Label>
                                <Input
                                    type="number"
                                    value={settings.insmind_verification_timeout}
                                    onChange={e => setSettings({ ...settings, insmind_verification_timeout: Number(e.target.value) })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('settings.fault_thresh')}</Label>
                                <Input
                                    type="number"
                                    value={settings.max_retry_count}
                                    onChange={e => setSettings({ ...settings, max_retry_count: Number(e.target.value) })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('settings.reg_int_min')}</Label>
                                <Input
                                    type="number"
                                    value={settings.register_interval_min}
                                    onChange={e => setSettings({ ...settings, register_interval_min: Number(e.target.value) })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('settings.reg_int_max')}</Label>
                                <Input
                                    type="number"
                                    value={settings.register_interval_max}
                                    onChange={e => setSettings({ ...settings, register_interval_max: Number(e.target.value) })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('settings.max_conc')}</Label>
                                <Input
                                    type="number"
                                    min={1}
                                    max={10}
                                    value={settings.max_concurrency || 1}
                                    onChange={e => setSettings({ ...settings, max_concurrency: Math.min(10, Math.max(1, Number(e.target.value))) })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>图片异步轮询间隔（秒）</Label>
                                <Input
                                    type="number"
                                    min={1}
                                    value={settings.gen_image_async_poll_interval}
                                    onChange={e => setSettings({ ...settings, gen_image_async_poll_interval: Math.max(1, Number(e.target.value)) })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>视频异步轮询间隔（秒）</Label>
                                <Input
                                    type="number"
                                    min={1}
                                    value={settings.gen_video_async_poll_interval}
                                    onChange={e => setSettings({ ...settings, gen_video_async_poll_interval: Math.max(1, Number(e.target.value)) })}
                                />
                            </div>
                            <div className="flex items-center justify-between rounded-lg border p-4 md:col-span-2">
                                <div className="space-y-0.5">
                                    <Label className="text-base">异步生成</Label>
                                    <p className="text-sm text-muted-foreground">
                                        默认启用。关闭后会等待远端生成完成再返回结果。
                                    </p>
                                </div>
                                <Switch
                                    checked={settings.gen_async_enabled}
                                    onCheckedChange={(checked) => setSettings({ ...settings, gen_async_enabled: checked })}
                                />
                            </div>
                            <div className="flex items-center justify-between rounded-lg border p-4 md:col-span-2">
                                <div className="space-y-0.5">
                                    <Label className="text-base">{t('settings.browser_headless')}</Label>
                                    <p className="text-sm text-muted-foreground">
                                        {t('settings.browser_headless_desc')}
                                    </p>
                                </div>
                                <Switch
                                    checked={settings.browser_headless}
                                    onCheckedChange={(checked) => setSettings({ ...settings, browser_headless: checked })}
                                />
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="proxy" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Cpu className="h-5 w-5" />
                                {t('settings.proxy_layer')}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label>{t('settings.clash_url')}</Label>
                                <Input
                                    value={settings.clash_controller_url}
                                    onChange={e => setSettings({ ...settings, clash_controller_url: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('settings.secret_key')}</Label>
                                <Input
                                    type="password"
                                    value={secrets.clash_secret}
                                    onChange={e => setSecrets({ ...secrets, clash_secret: e.target.value })}
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                                <div className="space-y-2 md:col-span-2">
                                    <Label>{t('settings.ext_proxy_path')}</Label>
                                    <Input
                                        placeholder="e.g., ./proxies.txt"
                                        value={settings.ext_proxy_file_path || ''}
                                        onChange={e => setSettings({ ...settings, ext_proxy_file_path: e.target.value })}
                                    />
                                </div>


... (truncated, 375 total lines)
```

请按以下格式输出：
## 审查结果
- 功能正确性: PASS/FAIL | 理由
- UI/UX 一致性: PASS/FAIL | 理由
- 代码质量: PASS/FAIL | 理由
- 安全性: PASS/FAIL | 理由
- 完整性: PASS/FAIL | 理由

## 具体问题
列出所有发现的问题（如果有）

## 改进建议
