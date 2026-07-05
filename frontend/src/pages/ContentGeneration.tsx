import { useEffect, useMemo, useState, useRef } from 'react'
import { VirtuosoGrid } from 'react-virtuoso'
import { Download, Sparkles, Plus, ImageIcon, Video, Box, Scaling, MonitorPlay, Clock, Send, Trash2, PlayCircle, ChevronLeft, ChevronRight, ArrowRight, RotateCcw, Loader2 } from 'lucide-react'
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
    video: ['Pixverse-V6.0', 'Seedance-2.0-Mini'],
}

const ACTIVE_JOB_STATUSES: ContentGenerationJob['status'][] = ['submitting', 'submitted', 'processing']
const SEEDANCE_MODELS = ['Seedance-2.0', 'Seedance-2.0-Mini', 'VEO-3.1', 'Wan-2.6']

const POLL_INTERVAL_MS = 4000
const CACHE_STALE_MS = 10000
let cachedJobs: ContentGenerationJob[] = []
let cachedAt = 0
let fetchInFlight = false

export default function ContentGeneration() {
    const [jobs, setJobs] = useState<ContentGenerationJob[]>(() => cachedJobs)
    const [jobType, setJobType] = useState<JobType>('video')
    const [filterType, setFilterType] = useState<FilterType>('all')
    const [filterStartDate, setFilterStartDate] = useState<string | undefined>()
    const [filterEndDate, setFilterEndDate] = useState<string | undefined>()
    const [prompt, setPrompt] = useState('')
    const [modelOptions, setModelOptions] = useState<Record<JobType, string[]>>(fallbackModelOptions)
    const [model, setModel] = useState(fallbackModelOptions.video[0])
    const [ratio, setRatio] = useState('1:1')
    const [resolution, setResolution] = useState('360p')
    const [duration, setDuration] = useState(10)
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
    const [generating, setGenerating] = useState(false)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    const durationOptions = useMemo(() => {
        if (jobType !== 'video') return []
        if (model === 'Seedance-2.0-Mini') return [5]
        if (model === 'Pixverse-V6.0') return [10]
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
                video: data.video_models.length
                    ? data.video_models.filter((m: string) => m === 'Pixverse-V6.0' || m === 'Seedance-2.0-Mini' || m === 'Seedance-2.0')
                    : fallbackModelOptions.video,
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
        setResolution(jobType === 'image' ? '2k' : '360p')
        setRatio('1:1')
        setDuration(10)
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
        if (model === 'Seedance-2.0-Mini') {
            setResolution('480p')
            setDuration(5)
        } else if (model === 'Pixverse-V6.0') {
            setResolution('360p')
            setDuration(10)
        }
    }, [model])

    useEffect(() => {
        if (jobType === 'video') {
            if (!durationOptions.includes(duration)) {
                setDuration(durationOptions[0] || 5)
            }
        }
    }, [jobType, model, duration, durationOptions])

    const handleGenerate = async () => {
        if (!prompt.trim() || generating) return

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
        setGenerating(true)
        try {
            await contentApi.generate(payload)
            setPrompt('')
            setInputImages([])
            fetchJobs({ force: true })
            toast.success(jobType === 'video' ? '视频生成任务已提交' : '图片生成任务已提交')
        } catch (error: any) {
            toast.error(error.message || '生成请求失败，请检查后端服务')
            console.error('Generate failed:', error)
        } finally {
            setGenerating(false)
        }
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
                // 智能压缩：仅当必要，尽量保质量
                const compress = (img: HTMLImageElement): string => {
                    let quality = 0.92
                    let MAX = 4096  // 保留更多细节
                    let w = img.naturalWidth
                    let h = img.naturalHeight

                    // 超大图才缩
                    if (w > MAX || h > MAX) {
                        const ratio = Math.min(MAX / w, MAX / h)
                        w = Math.round(w * ratio)
                        h = Math.round(h * ratio)
                    }

                    const canvas = document.createElement('canvas')
                    canvas.width = w
                    canvas.height = h
                    const ctx = canvas.getContext('2d')
                    ctx?.drawImage(img, 0, 0, w, h)

                    // PNG 格式保持无损，JPEG 用高质量
                    const isPng = file.type === 'image/png'
                    return canvas.toDataURL(isPng ? 'image/png' : 'image/jpeg', quality)
                }

                // 仅在文件 >5MB 时压缩
                if (file.size > 5 * 1024 * 1024) {
                    const img = new Image()
                    const url = URL.createObjectURL(file)
                    img.onload = () => {
                        const compressed = compress(img)
                        URL.revokeObjectURL(url)
                        resolve(compressed)
                    }
                    img.onerror = () => {
                        URL.revokeObjectURL(url)
                        const reader = new FileReader()
                        reader.onload = () => resolve(String(reader.result || ''))
                        reader.readAsDataURL(file)
                    }
                    img.src = url
                } else {
                    const reader = new FileReader()
                    reader.onload = () => resolve(String(reader.result || ''))
                    reader.readAsDataURL(file)
                }
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
            const a = document.createElement('a')
            a.href = downloadUrl
            a.download = url.split('/').pop()?.split('?')[0] || 'download'
            document.body.appendChild(a)
            a.click()
            setTimeout(() => { document.body.removeChild(a) }, 100)
        }
    }

    const handleBatchDownload = async () => {
        const selectedJobs = filteredJobs.filter(job => selectedIds.includes(job.id))
        if (!selectedJobs.length) return
        
        const jobIds = selectedJobs.map(j => j.id).join(',')
        
        // 调用后端流式 ZIP 打包接口。不再在前端下载各子文件并打包。
        // 使用隐藏链接触发，确保浏览器能正确接收 Content-Disposition
        const batchUrl = `/api/content/batch-download?ids=${jobIds}`
        const link = document.createElement('a')
        link.href = batchUrl
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        
        toast.success(`正在准备下载包 (${selectedJobs.length} 个任务)...`)
    }
    
    const handleDelete = async (id: number) => {
        try {
            await contentApi.deleteJob(id)
            setSelectedIds(prev => prev.filter(i => i !== id))
            await fetchJobs({ force: true })
        } catch (e) {
            console.error('Failed to delete job', e)
        }
    }
    
    const handleBatchDelete = async () => {
        if (!selectedIds.length) return
        try {
            await contentApi.batchDeleteJobs(selectedIds)
            setSelectedIds([])
            await fetchJobs({ force: true })
        } catch (e) {
            console.error('Batch delete failed', e)
        }
    }

    return (
        <div className="flex-1 space-y-4 pb-48 h-[calc(100vh-100px)] overflow-y-auto pr-2 animate-in fade-in duration-500 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
            <div className="flex items-center justify-between sticky top-0 z-40 bg-background pb-4 pt-4 -mx-2 px-6 border-b border-white/5 shadow-md">
                <div className="flex items-center gap-2">
                    <Select value={filterType} onValueChange={(v) => setFilterType(v as FilterType)}>
                        <SelectTrigger className="w-[120px] h-9 bg-card/40 border-white/5 rounded-[10px]">
                            <SelectValue placeholder="全部类型" />
                        </SelectTrigger>
                        <SelectContent className="border-white/10 bg-black/90 backdrop-blur-xl rounded-[10px]">
                            <SelectItem value="all">全部</SelectItem>
                            <SelectItem value="image">图片</SelectItem>
                            <SelectItem value="video">视频</SelectItem>
                        </SelectContent>
                    </Select>
                    
                    <div className="flex items-center gap-2 bg-muted/20 p-1 rounded-lg border border-border/30 h-9">
                        <GlassDatePicker
                            value={filterStartDate || ''}
                            onChange={(v) => setFilterStartDate(v)}
                            placeholder="开始日期"
                            className="w-[120px] h-7 text-xs border-transparent bg-transparent"
                        />
                        <ArrowRight className="h-3 w-3 text-muted-foreground/50" />
                        <GlassDatePicker
                            value={filterEndDate || ''}
                            onChange={(v) => setFilterEndDate(v)}
                            placeholder="结束日期"
                            className="w-[120px] h-7 text-xs border-transparent bg-transparent"
                        />
                    </div>
                </div>
                
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" className="h-9 border-white/5 bg-card/40 hover:bg-white/10 rounded-[10px]" onClick={() => setSelectedIds(filteredJobs.map(j => j.id))}>
                        全选
                    </Button>
                    <Button variant="outline" size="sm" className="h-9 border-white/5 bg-card/40 hover:bg-white/10 rounded-[10px]" onClick={handleSelectAllToggle}>
                        反选
                    </Button>
                    <Button variant="outline" size="sm" className="h-9 border-white/5 bg-card/40 hover:bg-white/10 gap-2 rounded-[10px]" onClick={handleBatchDownload} disabled={selectedIds.length === 0}>
                        <Download className="h-4 w-4" />打包下载
                    </Button>
                    <Button variant="destructive" size="sm" className="h-9 gap-2 rounded-[10px]" onClick={handleBatchDelete} disabled={selectedIds.length === 0}>
                        <Trash2 className="h-4 w-4" />批量删除
                    </Button>
                </div>
            </div>

            <div style={{ paddingBottom: '320px' }}>
                    <VirtuosoGrid
                        useWindowScroll
                        initialItemCount={18}
                        totalCount={filteredJobs.length}
                        overscan={400}
                    listClassName="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 max-w-[1800px] mx-auto"
                    itemContent={(index) => {
                    const job = filteredJobs[index]
                    if (!job) return null
                    const currentIndex = cardImageIndexes[job.id] || 0
                    // Use thumbnail for card preview; original URL for fullscreen/download
                    const thumbCover = job.thumbnail_urls?.[currentIndex] || job.thumbnail_urls?.[0]
                    const cover = thumbCover || job.output_urls?.[currentIndex] || job.output_urls?.[0]
                    const originalCover = job.output_urls?.[currentIndex] || job.output_urls?.[0]
                    const selected = selectedIds.includes(job.id)
                    const count = job.output_urls?.length || 0
                    const canSelect = job.status === 'success'
                    return (
                        <Card key={job.id} className="group border border-white/5 bg-card/40 backdrop-blur rounded-[2rem] overflow-hidden shadow-2xl flex flex-col p-2 transition-all duration-300 hover:bg-white/5">
                            <CardContent className="p-0 relative flex-1 flex flex-col">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setPreviewIndex(currentIndex)
                                        // Preview always uses original URLs
                                        setPreviewJob({ ...job })
                                    }}
                                    className="w-full aspect-[3/4] rounded-[1.5rem] overflow-hidden bg-muted/40 flex items-center justify-center relative shadow-inner group/btn"
                                >
                                    {cover ? (
                                        job.job_type === 'video' ? (
                                             <div className="w-full h-full relative group/vid">
                                                 {/* Video - Visible by default, metadata preload for frame preview */}
                                                 <video 
                                                    src={originalCover || ""} 
                                                    className="w-full h-full object-contain relative z-10" 
                                                    preload="metadata" 
                                                    poster={thumbCover}
                                                    muted 
                                                    loop
                                                    playsInline
                                                    onMouseOver={(e) => {
                                                        e.currentTarget.play();
                                                    }}
                                                    onMouseOut={(e) => { 
                                                        e.currentTarget.pause(); 
                                                    }}
                                                 />
                                                 
                                                 <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 group-hover/vid:opacity-100 transition-opacity duration-300 pointer-events-none z-20">
                                                     <PlayCircle className="h-12 w-12 text-white/90 drop-shadow-2xl" />
                                                 </div>
                                                 {/* Video icon overlay - Bottom right to avoid conflict with download button */}
                                                 <div className="absolute bottom-3 right-3 z-30 pointer-events-none p-1.5 rounded-lg bg-black/60 backdrop-blur-md border border-white/10 shadow-lg">
                                                     <Video className="h-4 w-4 text-white" />
                                                 </div>
                                             </div>
                                        ) : (
                                            <img 
                                                src={cover || ""} 
                                                alt="preview" 
                                                loading="lazy"
                                                decoding="async"
                                                className="w-full h-full object-contain transition-transform duration-700 group-hover/btn:scale-105" 
                                            />
                                        )
                                    ) : (
                                        ACTIVE_JOB_STATUSES.includes(job.status) ? (
                                            <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/80 backdrop-blur-md overflow-hidden rounded-[1.5rem]">
                                                {/* Shimmer overlay */}
                                                <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-cyan-500/10 to-transparent" />
                                                {/* Scanning line */}
                                                <div className="absolute left-0 right-0 h-[2px] bg-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.8)] animate-[scan_2s_ease-in-out_infinite]" />
                                                
                                                <div className="relative flex items-center justify-center mt-2 group-hover/btn:scale-110 transition-transform duration-500">
                                                    <div className="absolute inset-0 rounded-full animate-ping bg-cyan-500/40 duration-1000"></div>
                                                    <div className="absolute inset-0 rounded-full animate-pulse bg-cyan-400/20 blur-xl scale-150 duration-2000"></div>
                                                    {job.job_type === 'image' ? <ImageIcon className="h-8 w-8 text-cyan-400 relative z-10" /> : <Video className="h-8 w-8 text-cyan-400 relative z-10" />}
                                                </div>
                                                <span className="mt-6 text-[11px] font-bold text-cyan-300 tracking-[0.3em] relative z-10 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)] opacity-90">GENERATING</span>
                                            </div>
                                        ) : (
                                            <Sparkles className="h-6 w-6 text-muted-foreground opacity-30" />
                                        )
                                    )}

                                    {/* 失败任务重试按钮 — 中心悬浮显示 */}
                                    {job.status === 'failed' && (
                                        <button
                                            type="button"
                                            className="absolute inset-0 flex flex-col items-center justify-center opacity-0 group-hover/btn:opacity-100 transition-all duration-300 z-20 bg-black/40 backdrop-blur-sm rounded-[1.5rem]"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                handleRetry(job)
                                            }}
                                        >
                                            <div className="flex flex-col items-center gap-2">
                                                <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-red-500/20 border border-red-500/50 text-red-400 shadow-[0_0_20px_rgba(239,68,68,0.4)] hover:bg-red-500/40 hover:shadow-[0_0_30px_rgba(239,68,68,0.6)] transition-all duration-300 hover:scale-110">
                                                    <RotateCcw className="h-5 w-5" />
                                                </span>
                                                <span className="text-[11px] font-semibold text-red-300 tracking-widest drop-shadow-md">重试</span>
                                                {job.error_message && (
                                                    <span className="text-[10px] text-red-300/60 px-3 text-center leading-tight max-w-[180px]">{job.error_message}</span>
                                                )}
                                            </div>
                                        </button>
                                    )}
                                    
                                    <button
                                        type="button"
                                        className={cn(
                                            "absolute top-3 left-3 h-7 w-7 rounded-full border border-white/20 flex items-center justify-center text-xs font-bold transition-all z-10",
                                            selected ? "bg-foreground text-background scale-110" : "bg-black/40 text-white/70 opacity-0 group-hover:opacity-100 hover:scale-110",
                                            !canSelect && "opacity-0 pointer-events-none"
                                        )}
                                        onClick={(e) => {
                                            e.stopPropagation()
                                            if (!canSelect) return
                                            toggleSelection(job.id)
                                        }}
                                    >
                                        ✓
                                    </button>

                                    <button
                                        type="button"
                                        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-all duration-300 hover:scale-110 z-10"
                                        onClick={(e) => {
                                            e.stopPropagation()
                                            handleDownload(originalCover, currentIndex, job.local_urls?.[currentIndex])
                                        }}
                                        disabled={!originalCover && !job.local_urls?.[currentIndex]}
                                    >
                                        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-black/50 border border-white/10 backdrop-blur">
                                            <Download className="h-4 w-4 text-white" />
                                        </span>
                                    </button>

                                    {job.job_type === 'image' && count > 1 && (
                                        <span className="absolute bottom-3 right-3 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-black/60 backdrop-blur-md text-white border border-white/10 z-10 pointer-events-none">
                                            {currentIndex + 1} / {count} 张
                                        </span>
                                    )}

                                    <div className="absolute bottom-3 left-3 z-10 flex items-center">
                                        {ACTIVE_JOB_STATUSES.includes(job.status) ? (
                                            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-500/20 border border-blue-500/30 backdrop-blur-md">
                                                <span className="relative flex h-1.5 w-1.5">
                                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                                                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500"></span>
                                                </span>
                                                <span className="text-[10px] text-blue-400 font-medium tracking-wider">
                                                    {job.status === 'submitting' ? '提交中' : job.status === 'submitted' ? '已提交' : '生成中'}
                                                </span>
                                            </div>
                                        ) : job.status === 'success' ? (
                                            <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 backdrop-blur-md font-medium px-2 py-0.5 pointer-events-none shadow-sm">完成</Badge>
                                        ) : (
                                            <div className="flex items-center gap-2">
                                                <Badge className="bg-red-500/20 text-red-400 border border-red-500/30 backdrop-blur-md font-medium px-2 py-0.5 pointer-events-none shadow-sm">失败</Badge>
                                                {job.error_message && (
                                                    <span className="text-[10px] text-red-300/70 max-w-[120px] truncate">{job.error_message}</span>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 pointer-events-none opacity-80 font-mono text-[10px] tracking-wider text-white mix-blend-difference drop-shadow-md">
                                        {job.created_at ? new Date(job.created_at).toLocaleDateString() : ''}
                                    </div>
                                </button>
                                
                                <div className="flex flex-row gap-2 mt-2 pt-1 items-center justify-between">
                                    {job.job_type === 'image' && count > 1 ? (
                                        <div className="flex items-center gap-2 overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                                            {(job.thumbnail_urls?.length ? job.thumbnail_urls : job.output_urls)?.map((url, idx) => {
                                                const originalUrl = job.output_urls?.[idx] || "";
                                                return (
                                                    <button
                                                        key={idx}
                                                        type="button"
                                                        onClick={(e) => {
                                                            e.stopPropagation()
                                                            setCardImageIndexes(prev => ({ ...prev, [job.id]: idx }))
                                                        }}
                                                        className={cn(
                                                            "h-10 w-10 shrink-0 rounded-[10px] overflow-hidden border-2 transition-all bg-muted/20",
                                                            currentIndex === idx 
                                                                ? "border-emerald-500/80 shadow-[0_0_10px_rgba(52,211,153,0.3)] opacity-100" 
                                                                : "border-transparent opacity-40 hover:opacity-100"
                                                        )}
                                                    >
                                                        <img 
                                                            src={url || ''} 
                                                            alt="" 
                                                            loading="lazy"
                                                            decoding="async"
                                                            className="w-full h-full object-cover" 
                                                            onError={(e) => {
                                                                const target = e.currentTarget;
                                                                const thumbUrl = job.thumbnail_urls?.[idx];
                                                                if (thumbUrl && originalUrl && target.src !== originalUrl) {
                                                                    target.src = originalUrl;
                                                                }
                                                            }}
                                                        />
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    ) : <div className="flex-1" />}

                                    <button
                                        type="button"
                                        className="opacity-0 group-hover:opacity-100 transition-all duration-300 hover:scale-110 z-20 shrink-0 ml-auto h-10 w-10 flex items-center justify-center rounded-[10px] bg-red-500/10 text-red-500 hover:bg-red-500/80 hover:text-white"
                                        onClick={(e) => {
                                            e.stopPropagation()
                                            handleDelete(job.id)
                                        }}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </button>
                                </div>
                            </CardContent>
                        </Card>
                    )
                }}
            />
        </div>


            <div className="fixed left-1/2 -translate-x-1/2 bottom-8 w-[min(1180px,96vw)] z-50 transition-all duration-300">
                <div
                    className={cn(
                        "rounded-[2rem] border border-white/10 bg-black/60 shadow-2xl backdrop-blur-3xl flex flex-col overflow-hidden relative transition-all duration-500 hover:border-white/20 hover:bg-black/70",
                        isDragging && "border-emerald-400/80 shadow-[0_0_30px_rgba(52,211,153,0.3)] bg-green-950/30",
                        isExpanded ? "p-5 gap-4" : "p-3 gap-0"
                    )}
                    onMouseEnter={() => setIsHovered(true)}
                    onMouseLeave={() => setIsHovered(false)}
                    onDragOver={(e) => {
                        e.preventDefault()
                        setIsDragging(true)
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleDrop}
                >
                    {/* Top Area: Uploaded Images */}
                    <div 
                        className={cn(
                            "flex items-center gap-3 overflow-x-auto transition-all duration-300 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]",
                            isExpanded ? "max-h-20 opacity-100 mb-0 pb-1" : "max-h-0 opacity-0 mb-0 pb-0"
                        )}
                    >
                        {inputImages.map((img, idx) => (
                            <div key={`${img}-${idx}`} className="group relative h-16 w-16 shrink-0 rounded-2xl overflow-hidden border border-white/10 bg-black/40 shadow-sm transition-transform hover:scale-105">
                                <img src={img} alt="ref" className="h-full w-full object-cover" />
                                <button
                                    className="absolute inset-0 bg-black/60 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                                    onClick={() => removeImage(idx)}
                                >
                                    <Trash2 className="h-4 w-4 text-red-400" />
                                </button>
                            </div>
                        ))}
                        <label className="h-16 w-16 shrink-0 rounded-2xl border border-dashed border-white/20 bg-white/5 flex flex-col items-center justify-center text-xs text-muted-foreground cursor-pointer hover:bg-white/10 hover:border-white/30 transition-all group">
                            <Plus className="h-5 w-5 mb-1 group-hover:text-emerald-400 transition-colors" />
                            <span className="text-[10px] scale-90">添加</span>
                            <input type="file" accept="image/*" multiple className="hidden" onChange={handleFileClick} />
                        </label>
                    </div>

                    {/* Middle Area: Prompt Input */}
                    <div 
                        className={cn(
                            "relative transition-all duration-300",
                            isExpanded ? "max-h-[300px] opacity-100" : "max-h-0 opacity-0 scale-95"
                        )}
                    >
                        <Textarea
                            ref={textareaRef}
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            onFocus={() => setIsFocused(true)}
                            onBlur={() => setIsFocused(false)}
                            onPaste={handlePaste}
                            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && prompt.trim()) { e.preventDefault(); handleGenerate(); } }}
                            placeholder="请描述你想生成的内容，或在此处粘贴图片..."
                            className="min-h-[100px] resize-none bg-white/5 border-transparent outline-none focus-visible:ring-1 focus-visible:ring-emerald-500/50 rounded-2xl text-[15px] leading-relaxed px-4 py-3 placeholder:text-muted-foreground/60 focus:bg-white/10 transition-all"
                        />
                    </div>

                    {/* Bottom Area: Parameters and Send Button */}
                    <div className={cn(
                        "flex items-center gap-3 overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] pb-1 pr-16 transition-all duration-300",
                        isExpanded ? "border-t border-white/5 pt-4" : "border-t-0 pt-0"
                    )}>
                        <Select value={jobType} onValueChange={(value) => setJobType(value as JobType)} onOpenChange={setSelectOpen}>
                            <SelectTrigger className="h-10 rounded-xl bg-white/5 border-transparent hover:bg-white/10 text-sm font-medium gap-2 w-[150px] shrink-0 transition-colors focus:ring-1 focus:ring-emerald-500/50">
                                <div className="flex items-center gap-2 opacity-80 min-w-0 w-full">
                                    {jobType === 'image' ? <ImageIcon className="h-4 w-4 shrink-0 text-blue-400" /> : <Video className="h-4 w-4 shrink-0 text-purple-400" />}
                                    <SelectValue placeholder="模式" />
                                </div>
                            </SelectTrigger>
                            <SelectContent side="top" className="rounded-xl border-white/10 bg-black/90 backdrop-blur-xl mb-2">
                                <SelectItem value="image" className="rounded-lg focus:bg-white/10 cursor-pointer">
                                    <div className="flex items-center gap-2">图片生成</div>
                                </SelectItem>
                                <SelectItem value="video" className="rounded-lg focus:bg-white/10 cursor-pointer">
                                    <div className="flex items-center gap-2">视频生成</div>
                                </SelectItem>
                            </SelectContent>
                        </Select>

                        <Select value={model} onValueChange={setModel} onOpenChange={setSelectOpen}>
                            <SelectTrigger className="h-10 rounded-xl bg-white/5 border-transparent hover:bg-white/10 text-sm gap-2 w-[330px] shrink-0 transition-colors">
                                <div className="flex items-center gap-2 opacity-80 min-w-0 w-full text-left whitespace-nowrap overflow-hidden">
                                    <Box className="h-4 w-4 shrink-0 text-emerald-400" />
                                    <SelectValue placeholder="模型" />
                                </div>
                            </SelectTrigger>
                            <SelectContent side="top" className="rounded-xl border-white/10 bg-black/90 backdrop-blur-xl mb-2">
                                {modelOptions[jobType].map((item) => (
                                    <SelectItem key={item} value={item} className="rounded-lg focus:bg-white/10 cursor-pointer">
                                        {item}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        <Select value={ratio} onValueChange={setRatio} onOpenChange={setSelectOpen}>
                            <SelectTrigger className="h-10 rounded-xl bg-white/5 border-transparent hover:bg-white/10 text-sm gap-2 w-[120px] shrink-0 transition-colors">
                                <div className="flex items-center gap-2 opacity-80 min-w-0 w-full whitespace-nowrap">
                                    <Scaling className="h-4 w-4 shrink-0 text-amber-400" />
                                    <SelectValue placeholder="比例" />
                                </div>
                            </SelectTrigger>
                            <SelectContent side="top" className="rounded-xl border-white/10 bg-black/90 backdrop-blur-xl mb-2">
                                {['1:1', '4:3', '3:4', '16:9', '9:16', '3:2', '2:3', '21:9'].map((item) => (
                                    <SelectItem key={item} value={item} className="rounded-lg focus:bg-white/10 cursor-pointer">{item}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        <Select value={resolution} onValueChange={setResolution} onOpenChange={setSelectOpen}>
                            <SelectTrigger className="h-10 rounded-xl bg-white/5 border-transparent hover:bg-white/10 text-sm gap-2 w-[128px] shrink-0 transition-colors">
                                <div className="flex items-center gap-2 opacity-80 min-w-0 w-full whitespace-nowrap">
                                    <MonitorPlay className="h-4 w-4 shrink-0 text-cyan-400" />
                                    <SelectValue placeholder="清晰度" />
                                </div>
                            </SelectTrigger>
                            <SelectContent side="top" className="rounded-xl border-white/10 bg-black/90 backdrop-blur-xl mb-2">
                                {(jobType === 'image' ? ['1k', '2k', '4k'] : model === 'Pixverse-V6.0' ? ['360p'] : model === 'Seedance-2.0-Mini' ? ['480p'] : ['360p', '480p']).map((item) => (
                                    <SelectItem key={item} value={item} className="rounded-lg focus:bg-white/10 cursor-pointer">{item}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        {jobType === 'video' && (
                            <>
                                <Select value={String(duration)} onValueChange={(value) => setDuration(Number(value))} onOpenChange={setSelectOpen}>
                                    <SelectTrigger className="h-10 rounded-xl bg-white/5 border-transparent hover:bg-white/10 text-sm gap-2 w-[120px] shrink-0 transition-colors">
                                        <div className="flex items-center gap-2 opacity-80 min-w-0 w-full whitespace-nowrap">
                                            <Clock className="h-4 w-4 shrink-0 text-rose-400" />
                                            <SelectValue placeholder="时长" />
                                        </div>
                                    </SelectTrigger>
                                    <SelectContent side="top" className="rounded-xl border-white/10 bg-black/90 backdrop-blur-xl mb-2">
                                        {durationOptions.map((item) => (
                                            <SelectItem key={item} value={String(item)} className="rounded-lg focus:bg-white/10 cursor-pointer">{item}s</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                {supportsOmniReference && (
                                    <button
                                        type="button"
                                        onClick={() => setOmniReferenceEnabled((prev) => !prev)}
                                        className={cn(
                                            'h-10 w-[154px] shrink-0 rounded-xl border px-3 text-sm transition-colors flex items-center justify-center gap-2',
                                            omniReferenceEnabled
                                                ? 'bg-emerald-500/15 border-emerald-500/35 text-emerald-300'
                                                : 'bg-white/5 border-transparent text-white/70 hover:bg-white/10'
                                        )}
                                    >
                                        <Box className="h-4 w-4 shrink-0" />
                                        <span className="truncate">Omni Reference</span>
                                    </button>
                                )}
                            </>
                        )}
                    </div>
                    
                    {/* Send Button Absolute Right */}
                    <div className={cn(
                        "absolute right-5 transition-all duration-300",
                        isExpanded ? "bottom-4 scale-100 opacity-100" : "bottom-2 scale-75 opacity-0 pointer-events-none"
                    )}>
                        <Button
                            onClick={handleGenerate}
                            disabled={!prompt.trim() || generating}
                            className={cn(
                                "h-12 w-12 rounded-full p-0 flex items-center justify-center transition-all duration-300 shadow-xl",
                                prompt.trim() && !generating
                                    ? "bg-gradient-to-r from-emerald-400 to-teal-500 hover:scale-110 hover:shadow-emerald-500/30 text-black border-none"
                                    : "bg-white/10 text-white/30 cursor-not-allowed border-transparent"
                            )}
                        >
                            {generating ? (
                                <Loader2 className="h-5 w-5 animate-spin" />
                            ) : (
                                <Send className={cn("h-5 w-5", prompt.trim() && "ml-0.5")} />
                            )}
                        </Button>
                    </div>
                </div>
            </div>

            <Dialog open={!!previewJob} onOpenChange={(open) => !open && setPreviewJob(null)}>
                <DialogContent className="max-w-[70vw] w-[1400px] h-[80vh] bg-[#0f1115]/95 backdrop-blur-2xl border-white/10 rounded-3xl p-0 overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.8)] flex flex-col md:flex-row focus:outline-none focus-visible:outline-none">
                    <DialogTitle className="sr-only">资产预览</DialogTitle>
                    <div className="flex-1 bg-black/60 relative flex items-center justify-center overflow-hidden border-r border-white/5 group">
                        {previewJob?.output_urls?.[previewIndex] || previewJob?.local_urls?.[previewIndex] ? (
                            previewJob.job_type === 'video' ? (
                                <video 
                                    src={previewJob.local_urls?.[previewIndex] || previewJob.output_urls?.[previewIndex]} 
                                    controls 
                                    autoPlay 
                                    loop 
                                    playsInline 
                                    className="w-full h-full object-contain focus:outline-none focus:ring-0" 
                                />
                            ) : (
                                <img 
                                    src={previewJob.local_urls?.[previewIndex] || previewJob.output_urls?.[previewIndex]} 
                                    alt="preview" 
                                    className="w-full h-full object-contain" 
                                />
                            )
                        ) : (
                            <Sparkles className="h-8 w-8 text-muted-foreground animate-pulse" />
                        )}
                        
                        {/* Image count corner indicator */}
                        {previewJob?.job_type === 'image' && previewJob.output_urls && previewJob.output_urls.length > 1 && (
                            <div className="absolute top-4 left-4 px-3 py-1.5 rounded-full bg-black/50 border border-white/10 backdrop-blur-md text-xs font-medium text-white/90 pointer-events-none">
                                {previewIndex + 1} / {previewJob.output_urls.length}
                            </div>
                        )}

                        {/* Left/Right controls for images */}
                        {previewJob?.job_type === 'image' && previewJob.output_urls && previewJob.output_urls.length > 1 && (
                            <>
                                <button 
                                    onClick={(e) => { e.stopPropagation(); setPreviewIndex(prev => Math.max(0, prev - 1)); }}
                                    className={cn(
                                        "absolute left-4 top-1/2 -translate-y-1/2 h-12 w-12 flex items-center justify-center rounded-full bg-black/50 border border-white/10 text-white/80 hover:bg-black/80 hover:text-white hover:scale-110 transition-all backdrop-blur-md opacity-0 group-hover:opacity-100",
                                        previewIndex === 0 && "hidden"
                                    )}
                                >
                                    <ChevronLeft className="h-7 w-7 pr-0.5" />
                                </button>
                                <button 
                                    onClick={(e) => { e.stopPropagation(); setPreviewIndex(prev => Math.min((previewJob.output_urls?.length || 1) - 1, prev + 1)); }}
                                    className={cn(
                                        "absolute right-4 top-1/2 -translate-y-1/2 h-12 w-12 flex items-center justify-center rounded-full bg-black/50 border border-white/10 text-white/80 hover:bg-black/80 hover:text-white hover:scale-110 transition-all backdrop-blur-md opacity-0 group-hover:opacity-100",
                                        previewIndex === (previewJob.output_urls?.length || 1) - 1 && "hidden"
                                    )}
                                >
                                    <ChevronRight className="h-7 w-7 pl-0.5" />
                                </button>
                                {/* Thumbnails at bottom overlay */}
                                <div className="absolute bottom-6 flex items-center gap-3 px-5 py-3 bg-black/50 backdrop-blur-xl rounded-2xl border border-white/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                                    {previewJob.output_urls.map((url, idx) => (
                                        <button
                                            key={idx}
                                            onClick={(e) => { e.stopPropagation(); setPreviewIndex(idx); }}
                                            className={cn(
                                                "h-14 w-14 shrink-0 rounded-xl overflow-hidden border-2 transition-all hover:scale-110",
                                                previewIndex === idx ? "border-emerald-500 shadow-[0_0_15px_rgba(52,211,153,0.4)] opacity-100 scale-110" : "border-transparent opacity-60 hover:opacity-100"
                                            )}
                                        >
                                            <img src={url} alt={`thumb-${idx}`} className="w-full h-full object-cover" />
                                        </button>
                                    ))}
                                </div>
                            </>
                        )}
                    </div>

                    {/* Right Side: Parameters & Prompt */}
                    <div className="w-full md:w-[360px] lg:w-[400px] shrink-0 bg-[#16181d] flex flex-col overflow-hidden">
                        <div className="p-6 border-b border-white/5 space-y-1 shrink-0">
                            <h3 className="text-xl font-bold text-white/90">生成详情</h3>
                            <p className="text-xs text-muted-foreground/60">{previewJob?.created_at ? new Date(previewJob.created_at).toLocaleString() : 'Just now'}</p>
                        </div>
                        
                        <div className="p-6 flex-1 flex flex-col gap-8">
                            <div className="space-y-3">
                                <span className="text-[11px] font-semibold text-white/40 uppercase tracking-widest pl-1">Prompt 提示词</span>
                                <div className="bg-black/40 border border-white/5 rounded-2xl p-4 text-[15px] text-white/80 leading-relaxed shadow-inner break-words h-[320px] overflow-y-auto">
                                    {previewJob?.prompt || '--'}
                                </div>
                            </div>
                            
                            <div className="space-y-3">
                                <span className="text-[11px] font-semibold text-white/40 uppercase tracking-widest pl-1">参数配置</span>
                                <div className="bg-black/40 border border-white/5 rounded-2xl p-5 grid gap-4 text-sm shadow-inner">
                                    <div className="flex justify-between items-center group">
                                        <span className="text-white/50 group-hover:text-white/70 transition-colors">设置模板</span>
                                        <span className="font-semibold text-emerald-400/90">{previewJob?.job_type === 'video' ? '视频生成' : '图片生成'}</span>
                                    </div>
                                    <div className="flex justify-between items-center group">
                                        <span className="text-white/50 group-hover:text-white/70 transition-colors">模型版本</span>
                                        <span className="font-medium text-white/80">{previewJob?.model || '--'}</span>
                                    </div>
                                    <div className="flex justify-between items-center group">
                                        <span className="text-white/50 group-hover:text-white/70 transition-colors">画面比例</span>
                                        <span className="font-medium text-white/80">{previewJob?.ratio || '--'}</span>
                                    </div>
                                    <div className="flex justify-between items-center group">
                                        <span className="text-white/50 group-hover:text-white/70 transition-colors">清晰度</span>
                                        <span className="font-medium text-white/80">{previewJob?.resolution || '--'}</span>
                                    </div>
                                    {previewJob?.duration && (
                                        <div className="flex justify-between items-center group">
                                            <span className="text-white/50 group-hover:text-white/70 transition-colors">视频时长</span>
                                            <span className="font-medium text-white/80">{previewJob?.duration}s</span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="mt-auto pt-4 pb-2" />
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    )
}
