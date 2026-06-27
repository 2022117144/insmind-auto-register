请审查以下前端 TypeScript/TSX 文件。

项目背景: insMind (稿定设计海外版) 自动注册系统前端
文件路径: frontend/src/pages/ContentGeneration.tsx
文件类型: content

审查重点：
- routes/translations 文件：检查路由配置、导入路径、翻译键是否完整
- 页面组件文件：检查 API 对接、UI 一致性、错误处理、状态管理
- 确认无遗留 Dreamina 名称 (jimeng、dreamina 等)

文件内容:
```typescript
import { useEffect, useMemo, useState, useRef } from 'react'
import { VirtuosoGrid } from 'react-virtuoso'
import { Download, Sparkles, Plus, ImageIcon, Video, Box, Scaling, MonitorPlay, Clock, Send, Trash2, PlayCircle, ChevronLeft, ChevronRight, ArrowRight, RotateCcw } from 'lucide-react'
import { contentApi, ContentGenerationJob, ContentGenerationRequest } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { GlassDatePicker } from '@/components/ui/glass-date-picker'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

type JobType = 'image' | 'video'
type FilterType = 'all' | 'image' | 'video'

const fallbackModelOptions: Record<JobType, string[]> = {
    image: ['gpt-image-2', 'gpt-image-2-extreme', 'Qwen-Image-2-0', 'Qwen-Image-2-0-Pro', 'Nano-Banana2-Flash'],
    video: ['Pixverse-V6.0', 'Wan-2.7', 'Wan-2.2', 'Wan-2.6', 'Kling-3.0', 'Kling-2.6', 'Seedance-2.0', 'VEO-3.1'],
}

const ACTIVE_JOB_STATUSES: ContentGenerationJob['status'][] = ['submitting', 'submitted', 'processing']
const SEEDANCE_MODELS = ['Seedance-2.0', 'VEO-3.1', 'Wan-2.6']

const POLL_INTERVAL_MS = 4000
const CACHE_STALE_MS = 10000
let cachedJobs: ContentGenerationJob[] = []
let cachedAt = 0
let fetchInFlight = false

export default function ContentGeneration() {
    const [jobs, setJobs] = useState<ContentGenerationJob[]>(() => cachedJobs)
    const [jobType, setJobType] = useState<JobType>('image')
    const [filterType, setFilterType] = useState<FilterType>('all')
    const [filterStartDate, setFilterStartDate] = useState<string | undefined>()
    const [filterEndDate, setFilterEndDate] = useState<string | undefined>()
    const [prompt, setPrompt] = useState('')
    const [modelOptions, setModelOptions] = useState<Record<JobType, string[]>>(fallbackModelOptions)
    const [model, setModel] = useState(fallbackModelOptions.image[0])
    const [ratio, setRatio] = useState('1:1')
    const [resolution, setResolution] = useState('2k')
    const [duration, setDuration] = useState(5)
    const [omniReferenceEnabled, setOmniReferenceEnabled] = useState(false)
    const [inputImages, setInputImages] = useState<string[]>([])
    const [selectedIds, setSelectedIds] = useState<number[]>([])
    const [previewJob, setPreviewJob] = useState<ContentGenerationJob | null>(null)
    const [previewIndex, setPreviewIndex] = useState(0)
    const [cardImageIndexes, setCardImageIndexes] = useState<Record<number, number>>({})
    const [isDragging, setIsDragging] = useState(false)
    const [isFocused, setIsFocused] = useState(false)
    const [isHovered, setIsHovered] = useState(false)
    const [selectOpen, setSelectOpen] = useState(false)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    const durationOptions = useMemo(() => {
        if (jobType !== 'video') return []
        if (SEEDANCE_MODELS.includes(model)) {
            return Array.from({ length: 12 }, (_, index) => index + 4)
        }
        return [5, 10]
    }, [jobType, model])

    const supportsOmniReference = useMemo(() => {
        return jobType === 'video' && ['Seedance-2.0', 'VEO-3.1', 'Wan-2.6', 'Wan-2.7'].includes(model)
    }, [jobType, model])

    const fetchJobs = async (options?: { force?: boolean }) => {
        if (fetchInFlight) return
        const now = Date.now()
        if (!options?.force && now - cachedAt < CACHE_STALE_MS) return
        fetchInFlight = true
        try {
            const data = await contentApi.listJobs()
            cachedJobs = data
            cachedAt = Date.now()
            setJobs(data)
        } catch (e) {
            console.error('Failed to fetch jobs', e)
        } finally {
            fetchInFlight = false
        }
    }

    const fetchModels = async () => {
        try {
            const data = await contentApi.getModels()
            const nextOptions: Record<JobType, string[]> = {
                image: data.image_models.length ? data.image_models : fallbackModelOptions.image,
                video: data.video_models.length ? data.video_models : fallbackModelOptions.video,
            }
            setModelOptions(nextOptions)
            setModel(prev => nextOptions[jobType].includes(prev) ? prev : nextOptions[jobType][0])
        } catch (error) {
            console.error('Failed to fetch generation models', error)
            setModelOptions(fallbackModelOptions)
            setModel(prev => fallbackModelOptions[jobType].includes(prev) ? prev : fallbackModelOptions[jobType][0])
        }
    }

    useEffect(() => {
        fetchModels()
        let timer: ReturnType<typeof setInterval> | null = null

        const stop = () => {
            if (timer) {
                clearInterval(timer)
                timer = null
            }
        }

        const start = () => {
            if (timer) return
            timer = setInterval(() => fetchJobs(), POLL_INTERVAL_MS)
        }

        const handleVisibility = () => {
            if (document.visibilityState === 'visible') {
                fetchJobs()
                start()
            } else {
                stop()
            }
        }

        handleVisibility()
        document.addEventListener('visibilitychange', handleVisibility)
        return () => {
            stop()
            document.removeEventListener('visibilitychange', handleVisibility)
        }
    }, [])

    useEffect(() => {
        setModel(modelOptions[jobType][0])
        setResolution(jobType === 'image' ? '2k' : '720p')
        setRatio('1:1')
        setDuration(5)
        setOmniReferenceEnabled(false)
        setInputImages([])
        setSelectedIds([])
    }, [jobType])

    useEffect(() => {
        if (!supportsOmniReference && omniReferenceEnabled) {
            setOmniReferenceEnabled(false)
        }
    }, [supportsOmniReference, omniReferenceEnabled])

    useEffect(() => {
        if (jobType === 'video') {
            if (!durationOptions.includes(duration)) {
                setDuration(durationOptions[0] || 5)
            }
        }
    }, [jobType, model, duration, durationOptions])

    const handleGenerate = async () => {
        if (!prompt.trim()) return

        const payload: ContentGenerationRequest = {
            job_type: jobType,
            prompt,
            model,
            ratio,
            resolution,
            duration: jobType === 'video' ? duration : undefined,
            input_images: inputImages.length > 0 ? inputImages : undefined,
            async_mode: true,
            function_mode: supportsOmniReference && omniReferenceEnabled ? 'omni_reference' : undefined,
        }
        await contentApi.generate(payload)
        setPrompt('')
        setInputImages([])
        fetchJobs({ force: true })
    }

    // 重试失败任务——在原有任务上原地重试，不丢失参数，不产生重复卡片
    const handleRetry = async (job: ContentGenerationJob) => {
        try {
            await contentApi.retryJob(job.id)
            fetchJobs({ force: true })
        } catch (error: any) {
            console.error('Retry failed:', error)
        }
    }

    const handleFiles = async (files: FileList | File[]) => {
        const list = Array.from(files).slice(0, 10)
        const dataUrls = await Promise.all(list.map(file => {
            return new Promise<string>((resolve) => {
                const reader = new FileReader()
                reader.onload = () => resolve(String(reader.result || ''))
                reader.readAsDataURL(file)
            })
        }))
        setInputImages(prev => [...prev, ...dataUrls].slice(0, 10))
    }

    const handleDrop = async (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault()
        setIsDragging(false)
        if (event.dataTransfer.files?.length) {
            await handleFiles(event.dataTransfer.files)
        }
    }

    const handleFileClick = async (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files?.length) {
            await handleFiles(event.target.files)
            event.target.value = ''
        }
    }

    const handlePaste = async (event: React.ClipboardEvent) => {
        if (event.clipboardData.files?.length) {
            await handleFiles(event.clipboardData.files)
        }
    }

    const removeImage = (index: number) => {
        setInputImages(prev => prev.filter((_, i) => i !== index))
    }

    const filteredJobs = useMemo(() => {
        let res = jobs
        if (filterType !== 'all') {
            res = res.filter(j => j.job_type === filterType)
        }

        // Helper to parse date as Beijing Time (UTC+8)
        const parseAsBeijing = (dateStr: string, time: string = '00:00:00') => {
            return new Date(`${dateStr}T${time}+08:00`).getTime()
        }

        if (filterStartDate) {
            const startLimit = parseAsBeijing(filterStartDate)
            res = res.filter(j => j.created_at && new Date(j.created_at.replace(' ', 'T') + '+08:00').getTime() >= startLimit)
        }
        if (filterEndDate) {
            // Include entire end date day (up to 23:59:59 Beijing time)
            const endLimit = parseAsBeijing(filterEndDate, '23:59:59.999')
            res = res.filter(j => j.created_at && new Date(j.created_at.replace(' ', 'T') + '+08:00').getTime() <= endLimit)
        }
        return res
    }, [jobs, filterType, filterStartDate, filterEndDate])

    const toggleSelection = (id: number) => {
        setSelectedIds(prev => prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id])
    }
    
    const handleSelectAllToggle = () => {
        if (selectedIds.length === filteredJobs.length && filteredJobs.length > 0) {
            // 反选逻辑: all to none, otherwise invert selection? The requested was "全选和反选" (Select All and Invert Selection).
            // Actually, if it's "全不选" then they just want to deselect. Let's do Invert Selection.
            setSelectedIds(filteredJobs.filter(j => !selectedIds.includes(j.id)).map(j => j.id))
        } else {
            // If nothing is selected, select all. Or we can just strictly do Invert Selection.
            // Oh wait, the prompt asks: "全选和反选，反选不是全不选" => So "全选" (Select All) and "反选" (Invert Selection).
            // The logic: if selected === total, then Invert should naturally make it `none`. 
            setSelectedIds(filteredJobs.filter(j => !selectedIds.includes(j.id)).map(j => j.id))
        }
    }

    const isExpanded = isFocused || isHovered || selectOpen || prompt.trim() !== '' || inputImages.length > 0


    const handleDownload = async (url?: string, index?: number, localUrl?: string) => {
        if (!url && !localUrl) return
        
        // 1. 本地文件优先：直接跳转静态资源路径（速度最快）
        if (localUrl) {
            const link = document.createElement('a')
            link.href = localUrl
            link.download = localUrl.split('/').pop()?.split('?')[0] || `file_${index || 0}`
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            return
        }

        // 2. 远程文件通过 Proxy 接口跳转
        // 废弃原有的 fetch + blob 逻辑，避免浏览器等待大视频缓冲完才弹窗
        // 直接跳转链接会触发浏览器自带的下载管理，秒开“另存为”对话框
        if (url) {
            const downloadUrl = `/api/content/download-proxy?url=${encodeURIComponent(url)}`
            const link = document.createElement('a')
            link.href = downloadUrl
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
        }
    }

    const handleBatchDownload = async () => {
        const selectedJobs = filteredJobs.filter(job => selectedIds.includes(job.id))
        if (!selectedJobs.length) return
        
        const jobIds = selectedJobs.map(j => j.id).join(',')
        


... (truncated, 909 total lines)
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
