import { useEffect, useMemo, useState, useRef } from 'react'
import { VirtuosoGrid } from 'react-virtuoso'
import { Download, Sparkles, Plus, ImageIcon, Box, Scaling, Send, Trash2, RotateCcw, Loader2, ArrowRight, X } from 'lucide-react'
import { photogptGenApi, PhotoGPTGenJob } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { GlassDatePicker } from '@/components/ui/glass-date-picker'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

const ACTIVE_JOB_STATUSES: PhotoGPTGenJob['status'][] = ['submitting', 'submitted', 'processing']

const POLL_INTERVAL_MS = 4000
const CACHE_STALE_MS = 10000
let cachedJobs: PhotoGPTGenJob[] = []
let cachedAt = 0
let fetchInFlight = false

const ASPECT_RATIOS = ['1:1', '16:9', '9:16', '4:3', '3:4']
const RESOLUTIONS = ['1K', '2K', '4K']
const QUALITIES = ['low', 'medium', 'high']

export default function Img2Generation() {
    const [jobs, setJobs] = useState<PhotoGPTGenJob[]>(() => cachedJobs)
    const [filterStartDate, setFilterStartDate] = useState<string | undefined>()
    const [filterEndDate, setFilterEndDate] = useState<string | undefined>()
    const [prompt, setPrompt] = useState('')
    const [aspectRatio, setAspectRatio] = useState('1:1')
    const [resolution, setResolution] = useState('1K')
    const [quality, setQuality] = useState('medium')
    const [outputNum, setOutputNum] = useState(1)
    const [inputImages, setInputImages] = useState<string[]>([])
    const [selectedIds, setSelectedIds] = useState<number[]>([])
    const [previewJob, setPreviewJob] = useState<PhotoGPTGenJob | null>(null)
    const [previewIndex, setPreviewIndex] = useState(0)
    const [cardImageIndexes, setCardImageIndexes] = useState<Record<number, number>>({})
    const [isFocused, setIsFocused] = useState(false)
    const [isHovered, setIsHovered] = useState(false)
    const [selectOpen, setSelectOpen] = useState(false)
    const [generating, setGenerating] = useState(false)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    const fetchJobs = async (options?: { force?: boolean }) => {
        if (fetchInFlight) return
        const now = Date.now()
        if (!options?.force && now - cachedAt < CACHE_STALE_MS) return
        fetchInFlight = true
        try {
            const data = await photogptGenApi.listJobs()
            cachedJobs = data
            cachedAt = Date.now()
            setJobs(data)
        } catch (e) {
            console.error('Failed to fetch jobs', e)
        } finally {
            fetchInFlight = false
        }
    }

    useEffect(() => {
        let timer: ReturnType<typeof setInterval> | null = null
        const stop = () => { if (timer) { clearInterval(timer); timer = null } }
        const start = () => { if (timer) return; timer = setInterval(() => fetchJobs(), POLL_INTERVAL_MS) }
        const handleVisibility = () => {
            if (document.visibilityState === 'visible') { fetchJobs(); start() }
            else { stop() }
        }
        handleVisibility()
        document.addEventListener('visibilitychange', handleVisibility)
        return () => { stop(); document.removeEventListener('visibilitychange', handleVisibility) }
    }, [])

    const handleGenerate = async () => {
        if (!prompt.trim() || generating) return
        setGenerating(true)
        try {
            await photogptGenApi.generate({
                prompt,
                aspect_ratio: aspectRatio,
                output_num: outputNum,
                quality,
                resolution,
                input_urls: inputImages.length > 0 ? inputImages : undefined,
            })
            setPrompt('')
            setInputImages([])
            fetchJobs({ force: true })
            toast.success('图片生成任务已提交')
        } catch (error: any) {
            toast.error(error.message || '生成请求失败')
            console.error('Generate failed:', error)
        } finally {
            setGenerating(false)
        }
    }

    const handleRetry = async (job: PhotoGPTGenJob) => {
        try {
            await photogptGenApi.retryJob(job.id)
            fetchJobs({ force: true })
        } catch (error: any) {
            console.error('Retry failed:', error)
        }
    }

    const handleFiles = async (files: FileList | File[]) => {
        const list = Array.from(files).slice(0, 4)
        const dataUrls = await Promise.all(list.map(file => {
            return new Promise<string>((resolve) => {
                const compress = (img: HTMLImageElement): string => {
                    let quality = 0.92
                    let MAX = 4096
                    let w = img.naturalWidth
                    let h = img.naturalHeight
                    if (w > MAX || h > MAX) {
                        const ratio = Math.min(MAX / w, MAX / h)
                        w = Math.round(w * ratio)
                        h = Math.round(h * ratio)
                    }
                    const canvas = document.createElement('canvas')
                    canvas.width = w; canvas.height = h
                    const ctx = canvas.getContext('2d')
                    ctx?.drawImage(img, 0, 0, w, h)
                    const isPng = file.type === 'image/png'
                    return canvas.toDataURL(isPng ? 'image/png' : 'image/jpeg', quality)
                }
                if (file.size > 5 * 1024 * 1024) {
                    const img = new Image()
                    const url = URL.createObjectURL(file)
                    img.onload = () => { const compressed = compress(img); URL.revokeObjectURL(url); resolve(compressed) }
                    img.onerror = () => { URL.revokeObjectURL(url); const reader = new FileReader(); reader.onload = () => resolve(String(reader.result || '')); reader.readAsDataURL(file) }
                    img.src = url
                } else {
                    const reader = new FileReader()
                    reader.onload = () => resolve(String(reader.result || ''))
                    reader.readAsDataURL(file)
                }
            })
        }))
        setInputImages(prev => [...prev, ...dataUrls].slice(0, 4))
    }

    const handleDrop = async (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault()
        if (event.dataTransfer.files?.length) { await handleFiles(event.dataTransfer.files) }
    }

    const handleFileClick = async (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files?.length) { await handleFiles(event.target.files); event.target.value = '' }
    }

    const handlePaste = async (event: React.ClipboardEvent) => {
        if (event.clipboardData.files?.length) { await handleFiles(event.clipboardData.files) }
    }

    const removeImage = (index: number) => setInputImages(prev => prev.filter((_, i) => i !== index))

    const filteredJobs = useMemo(() => {
        let res = jobs
        const parseAsBeijing = (dateStr: string, time: string = '00:00:00') => new Date(`${dateStr}T${time}+08:00`).getTime()
        if (filterStartDate) {
            const startLimit = parseAsBeijing(filterStartDate)
            res = res.filter(j => j.created_at && new Date(j.created_at.replace(' ', 'T') + '+08:00').getTime() >= startLimit)
        }
        if (filterEndDate) {
            const endLimit = parseAsBeijing(filterEndDate, '23:59:59.999')
            res = res.filter(j => j.created_at && new Date(j.created_at.replace(' ', 'T') + '+08:00').getTime() <= endLimit)
        }
        return res
    }, [jobs, filterStartDate, filterEndDate])

    const toggleSelection = (id: number) => {
        setSelectedIds(prev => prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id])
    }

    const handleSelectAllToggle = () => {
        setSelectedIds(filteredJobs.filter(j => !selectedIds.includes(j.id)).map(j => j.id))
    }

    const isExpanded = true

    const handleDownload = async (url?: string, index?: number) => {
        if (!url) return
        const downloadUrl = `/api/content/download-proxy?url=${encodeURIComponent(url)}`
        const link = document.createElement('a')
        link.href = downloadUrl
        document.body.appendChild(link); link.click(); document.body.removeChild(link)
    }

    const handleBatchDownload = async () => {
        const selectedJobs = filteredJobs.filter(job => selectedIds.includes(job.id))
        if (!selectedJobs.length) return
        const jobIds = selectedJobs.map(j => j.id).join(',')
        const batchUrl = `/api/content/batch-download?ids=${jobIds}`
        const link = document.createElement('a')
        link.href = batchUrl
        document.body.appendChild(link); link.click(); document.body.removeChild(link)
        toast.success(`正在准备下载包 (${selectedJobs.length} 个任务)...`)
    }

    const handleDelete = async (id: number) => {
        try {
            await photogptGenApi.deleteJob(id)
            setSelectedIds(prev => prev.filter(i => i !== id))
            await fetchJobs({ force: true })
        } catch (e) {
            console.error('Failed to delete job', e)
        }
    }

    const handleBatchDelete = async () => {
        if (!selectedIds.length) return
        try {
            await photogptGenApi.batchDeleteJobs(selectedIds)
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

            {/* Generate Input Area — Fixed at bottom */}
            <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 w-full max-w-4xl px-4">
                <div
                    className={cn(
                        "relative transition-all duration-300 ease-out",
                        isExpanded ? "w-full" : "w-[600px] mx-auto"
                    )}
                    onMouseEnter={() => setIsHovered(true)}
                    onMouseLeave={() => setIsHovered(false)}
                >
                    <div className={cn(
                        "rounded-3xl border shadow-2xl backdrop-blur-xl transition-all duration-300",
                        isExpanded
                            ? "bg-black/90 border-white/20 shadow-white/5"
                            : "bg-black/70 border-white/10 hover:border-white/30 hover:bg-black/80"
                    )}>
                        {/* Image Upload Area */}
                        <div className="px-4 pt-4 flex items-center gap-2 flex-wrap">
                            {inputImages.map((dataUrl, i) => (
                                <div key={i} className="relative group/img">
                                    <img src={dataUrl} alt="" className="w-14 h-14 rounded-xl object-cover border border-white/10" />
                                    <button
                                        onClick={() => removeImage(i)}
                                        className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500/80 flex items-center justify-center opacity-0 group-hover/img:opacity-100 transition-opacity"
                                    >
                                        <X className="h-3 w-3 text-white" />
                                    </button>
                                </div>
                            ))}
                            <label className="cursor-pointer">
                                <div className="w-14 h-14 rounded-xl border-2 border-dashed border-white/20 flex items-center justify-center hover:border-white/40 transition-colors">
                                    <Plus className="h-5 w-5 text-white/60" />
                                </div>
                                <input type="file" accept="image/*" multiple className="hidden" onChange={handleFileClick} />
                            </label>
                        </div>

                        {/* Prompt Input */}
                        <div className="px-4 pt-2 pb-2">
                            <Textarea
                                ref={textareaRef}
                                placeholder="描述你要生成的图片..."
                                value={prompt}
                                onChange={e => setPrompt(e.target.value)}
                                onFocus={() => setIsFocused(true)}
                                onBlur={() => setIsFocused(false)}
                                onPaste={handlePaste}
                                onDragOver={e => e.preventDefault()}
                                onDrop={handleDrop}
                                className="min-h-[48px] max-h-[120px] bg-transparent border-none text-white placeholder:text-white/40 resize-none text-base focus-visible:ring-0 focus-visible:ring-offset-0 p-0"
                                rows={1}
                                onInput={e => {
                                    const target = e.currentTarget
                                    target.style.height = 'auto'
                                    target.style.height = Math.min(target.scrollHeight, 120) + 'px'
                                }}
                            />
                        </div>

                        {/* Options Row */}
                        <div className="flex items-center gap-2 px-4 pb-3 flex-wrap">
                            <Select value={aspectRatio} onValueChange={setAspectRatio}>
                                <SelectTrigger className="h-8 w-[90px] bg-white/5 border-white/10 text-xs text-white/80 rounded-xl">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="border-white/10 bg-black/90 backdrop-blur-xl rounded-xl">
                                    {ASPECT_RATIOS.map(r => (
                                        <SelectItem key={r} value={r} className="text-xs">{r}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Select value={resolution} onValueChange={setResolution}>
                                <SelectTrigger className="h-8 w-[80px] bg-white/5 border-white/10 text-xs text-white/80 rounded-xl">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="border-white/10 bg-black/90 backdrop-blur-xl rounded-xl">
                                    {RESOLUTIONS.map(r => (
                                        <SelectItem key={r} value={r} className="text-xs">{r}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Select value={quality} onValueChange={setQuality}>
                                <SelectTrigger className="h-8 w-[90px] bg-white/5 border-white/10 text-xs text-white/80 rounded-xl">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="border-white/10 bg-black/90 backdrop-blur-xl rounded-xl">
                                    {QUALITIES.map(q => (
                                        <SelectItem key={q} value={q} className="text-xs capitalize">{q}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Select value={String(outputNum)} onValueChange={v => setOutputNum(Number(v))}>
                                <SelectTrigger className="h-8 w-[70px] bg-white/5 border-white/10 text-xs text-white/80 rounded-xl">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="border-white/10 bg-black/90 backdrop-blur-xl rounded-xl">
                                    {[1, 2, 3, 4].map(n => (
                                        <SelectItem key={n} value={String(n)} className="text-xs">{n} 张</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            <div className="flex-1" />

                            <Button
                                onClick={handleGenerate}
                                disabled={!prompt.trim() || generating}
                                className="h-9 px-5 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-400 hover:to-pink-400 text-white rounded-xl shadow-lg shadow-purple-500/20 font-semibold text-sm"
                            >
                                {generating ? (
                                    <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                                ) : (
                                    <Sparkles className="h-4 w-4 mr-1.5" />
                                )}
                                {generating ? '生成中...' : '生成'}
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Job Grid */}
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
                        const cover = job.output_urls?.[currentIndex] || job.output_urls?.[0]
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
                                            setPreviewJob({ ...job })
                                        }}
                                        className="w-full aspect-[3/4] rounded-[1.5rem] overflow-hidden bg-muted/40 flex items-center justify-center relative shadow-inner group/btn"
                                    >
                                        {cover ? (
                                            <img
                                                src={cover}
                                                alt="preview"
                                                loading="lazy"
                                                decoding="async"
                                                className="w-full h-full object-contain transition-transform duration-700 group-hover/btn:scale-105"
                                            />
                                        ) : (
                                            ACTIVE_JOB_STATUSES.includes(job.status) ? (
                                                <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/80 backdrop-blur-md overflow-hidden rounded-[1.5rem]">
                                                    <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-cyan-500/10 to-transparent" />
                                                    <div className="absolute left-0 right-0 h-[2px] bg-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.8)] animate-[scan_2s_ease-in-out_infinite]" />
                                                    <div className="relative flex items-center justify-center mt-2 group-hover/btn:scale-110 transition-transform duration-500">
                                                        <div className="absolute inset-0 rounded-full animate-ping bg-cyan-500/40 duration-1000"></div>
                                                        <div className="absolute inset-0 rounded-full animate-pulse bg-cyan-400/20 blur-xl scale-150 duration-2000"></div>
                                                        <ImageIcon className="h-8 w-8 text-cyan-400 relative z-10" />
                                                    </div>
                                                    <span className="mt-6 text-[11px] font-bold text-cyan-300 tracking-[0.3em] relative z-10 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)] opacity-90">GENERATING</span>
                                                </div>
                                            ) : (
                                                <Sparkles className="h-6 w-6 text-muted-foreground opacity-30" />
                                            )
                                        )}

                                        {job.status === 'failed' && (
                                            <button
                                                type="button"
                                                className="absolute inset-0 flex flex-col items-center justify-center opacity-0 group-hover/btn:opacity-100 transition-all duration-300 z-20 bg-black/40 backdrop-blur-sm rounded-[1.5rem]"
                                                onClick={(e) => { e.stopPropagation(); handleRetry(job) }}
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
                                            onClick={(e) => { e.stopPropagation(); if (!canSelect) return; toggleSelection(job.id) }}
                                        >✓</button>

                                        <button
                                            type="button"
                                            className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-all duration-300 hover:scale-110 z-10"
                                            onClick={(e) => { e.stopPropagation(); handleDownload(originalCover, currentIndex) }}
                                            disabled={!originalCover}
                                        >
                                            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-black/50 border border-white/10 backdrop-blur">
                                                <Download className="h-4 w-4 text-white" />
                                            </span>
                                        </button>

                                        {count > 1 && (
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
                                    </button>
                                </CardContent>
                            </Card>
                        )
                    }}
                />
            </div>

            {/* Preview Dialog */}
            <Dialog open={!!previewJob} onOpenChange={(open) => { if (!open) setPreviewJob(null) }}>
                <DialogContent className="max-w-4xl w-[90vw] bg-black/95 border border-white/10 rounded-3xl">
                    <DialogTitle className="sr-only">图片预览</DialogTitle>
                    {previewJob && (
                        <div className="flex flex-col items-center gap-4">
                            <img
                                src={previewJob.output_urls?.[previewIndex] || ''}
                                alt="生成结果"
                                className="max-h-[70vh] w-auto object-contain rounded-2xl"
                            />
                            <div className="flex items-center gap-4">
                                <Button variant="outline" size="sm" onClick={() => setPreviewIndex(prev => Math.max(0, prev - 1))} disabled={previewIndex <= 0}>
                                    上一张
                                </Button>
                                <span className="text-sm text-white/60">{previewIndex + 1} / {previewJob.output_urls?.length || 1}</span>
                                <Button variant="outline" size="sm" onClick={() => setPreviewIndex(prev => Math.min((previewJob.output_urls?.length || 1) - 1, prev + 1))} disabled={previewIndex >= (previewJob.output_urls?.length || 1) - 1}>
                                    下一张
                                </Button>
                                <Button size="sm" onClick={() => handleDownload(previewJob.output_urls?.[previewIndex], previewIndex)} disabled={!previewJob.output_urls?.[previewIndex]}>
                                    <Download className="h-4 w-4 mr-1" />下载
                                </Button>
                            </div>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    )
}