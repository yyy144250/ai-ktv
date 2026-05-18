/**
 * AI-KTV 核心 Hook
 * 管理整个 KTV 视频制作流程的状态
 *
 * 流程优化：上传后立即进入歌词步骤，人声分离在后台并行执行
 */
import { useState, useRef, useCallback, useEffect } from 'react'

const API = '/api'

export function useKTV() {
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [step, setStep] = useState('upload') // upload | lyrics | lyrics_edit | aligning | rendering | done
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState(null)

  // 人声分离状态（后台并行，不影响 step）
  const [separationStatus, setSeparationStatus] = useState('idle')
  // idle | running | done | failed
  const [separationProgress, setSeparationProgress] = useState(0)
  const [separationMessage, setSeparationMessage] = useState('')

  const wsRef = useRef(null)
  const pollRef = useRef(null)
  // 记录前端当前 step，避免 WS 消息覆盖用户主动设置的 step
  const stepRef = useRef('upload')
  stepRef.current = step

  // 清理
  const cleanup = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  useEffect(() => () => cleanup(), [cleanup])

  // 处理后端推送的状态数据
  const _handleBackendData = useCallback((data) => {
    if (!data?.status) return

    setJob(data)
    const status = data.status
    const currentStep = stepRef.current

    // ---- 分离相关状态：更新分离进度，不切换 step ----
    if (status === 'separating') {
      setSeparationStatus('running')
      setSeparationProgress(data.progress ?? 0)
      setSeparationMessage(data.message ?? '人声分离中...')
      return  // 不影响主 step
    }

    if (status === 'separated') {
      setSeparationStatus('done')
      setSeparationProgress(100)
      setSeparationMessage('人声分离完成')
      // 如果用户还在歌词步骤，不切换 step（让用户继续操作歌词）
      if (currentStep === 'lyrics' || currentStep === 'lyrics_edit') {
        return
      }
    }

    // ---- 其他状态正常处理 ----
    setProgress(data.progress ?? 0)
    setMessage(data.message ?? '')

    switch (status) {
      case 'uploaded':
      case 'probed':
        // 不覆盖：上传后前端已主动进入 lyrics
        break
      case 'recognizing':
        setStep('recognizing')
        break
      case 'lyrics_ready':
        if (data?.error || (data?.message && data.message.includes('失败'))) {
          setError(data.message || data.error || '操作失败')
        }
        setStep('lyrics_edit')
        break
      case 'aligning':
        setStep('aligning')
        break
      case 'rendering':
        setStep('rendering')
        break
      case 'done':
        setStep('done')
        break
      case 'failed':
        // 分离失败
        if (currentStep === 'lyrics') {
          setSeparationStatus('failed')
          setSeparationMessage(data.message || '人声分离失败')
          setError(data.message || '人声分离失败')
        } else {
          setError(data.message || '发生错误')
        }
        break
    }
  }, [])

  // WebSocket 监听
  const connectWs = useCallback((id) => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/${id}`)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        _handleBackendData(data)
      } catch (err) {
        console.error('WS parse error:', err)
      }
    }

    ws.onerror = () => startPolling(id)
    ws.onclose = () => {
      wsRef.current = null
      startPolling(id)
    }
  }, [_handleBackendData])

  // 轮询兜底
  const startPolling = useCallback((id) => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/jobs/${id}`)
        if (res.ok) {
          const data = await res.json()
          _handleBackendData(data)

          const s = data.status
          // done/failed 时停止轮询；lyrics_ready 也停止（用户后续操作会重新触发 WS/轮询）
          if (s === 'done' || s === 'failed') {
            clearInterval(pollRef.current)
            pollRef.current = null
          }
        }
      } catch (e) {
        console.error('Poll error:', e)
      }
    }, 1500)
  }, [_handleBackendData])

  // ========== Actions ==========

  // 上传视频 → 自动启动分离 → 立即进入歌词步骤
  const uploadVideo = useCallback(async (file) => {
    setError(null)
    setStep('uploading')
    setProgress(0)
    setMessage('上传中...')
    setSeparationStatus('idle')

    try {
      const form = new FormData()
      form.append('file', file)

      const res = await fetch(`${API}/upload`, { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '上传失败')
      }

      const { job_id } = await res.json()
      setJobId(job_id)
      connectWs(job_id)

      // 启动后台分离
      setSeparationStatus('running')
      setSeparationMessage('正在提取音频...')
      const sepRes = await fetch(`${API}/jobs/${job_id}/separate`, { method: 'POST' })
      if (!sepRes.ok) {
        setSeparationStatus('failed')
        setSeparationMessage('启动人声分离失败')
      }

      // 立即进入歌词步骤，用户可以边等分离边搜索歌词
      setStep('lyrics')
      setMessage('')

    } catch (err) {
      setError(err.message)
      setStep('upload')
    }
  }, [connectWs])

  // AI 识别歌词（需要分离完成）
  const recognizeLyrics = useCallback(async () => {
    if (!jobId) return
    setError(null)
    setStep('recognizing')
    setMessage('正在识别歌词...')
    setProgress(0)

    try {
      const res = await fetch(`${API}/jobs/${jobId}/recognize`, { method: 'POST' })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '歌词识别失败')
      }
    } catch (err) {
      setError(err.message)
      setStep('lyrics')
    }
  }, [jobId])

  // 手动提交歌词
  const submitLyrics = useCallback(async (text, format = 'plain') => {
    if (!jobId) return
    setError(null)

    try {
      const res = await fetch(`${API}/jobs/${jobId}/lyrics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, format }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '提交歌词失败')
      }
      const data = await res.json()
      setJob(prev => ({ ...prev, lyrics: data.lyrics, status: 'lyrics_ready' }))
      setStep('lyrics_edit')
      setMessage('歌词已提交，假名已标注')
    } catch (err) {
      setError(err.message)
    }
  }, [jobId])

  // 搜索在线歌词
  const searchLyrics = useCallback(async (keyword, artist = '') => {
    if (!jobId) return []
    try {
      const res = await fetch(`${API}/jobs/${jobId}/search-lyrics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword, artist }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '搜索失败')
      }
      const data = await res.json()
      return data.results || []
    } catch (err) {
      setError(err.message)
      return []
    }
  }, [jobId])

  // 从在线源获取 LRC 歌词并提交
  const fetchAndSubmitLyrics = useCallback(async (source, songId) => {
    if (!jobId) return
    setError(null)

    try {
      const res = await fetch(`${API}/jobs/${jobId}/fetch-lyrics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, song_id: songId }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '获取歌词失败')
      }
      const data = await res.json()
      setJob(prev => ({ ...prev, lyrics: data.lyrics, status: 'lyrics_ready' }))
      setStep('lyrics_edit')
      setMessage('在线歌词已导入，时间轴已就绪')
    } catch (err) {
      setError(err.message)
    }
  }, [jobId])

  // 更新歌词
  const updateLyrics = useCallback(async (lines) => {
    if (!jobId) return
    setError(null)

    try {
      const res = await fetch(`${API}/jobs/${jobId}/lyrics`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lines }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '更新歌词失败')
      }
      const data = await res.json()
      setJob(prev => ({ ...prev, lyrics: data.lyrics }))
    } catch (err) {
      setError(err.message)
    }
  }, [jobId])

  // 对齐时间轴
  const alignLyrics = useCallback(async () => {
    if (!jobId) return
    setError(null)
    setStep('aligning')
    setMessage('正在对齐时间轴...')
    connectWs(jobId)

    try {
      const res = await fetch(`${API}/jobs/${jobId}/align`, { method: 'POST' })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '对齐失败')
      }
    } catch (err) {
      setError(err.message)
      setStep('lyrics_edit')
    }
  }, [jobId, connectWs])

  // 渲染视频
  const renderVideo = useCallback(async (options = {}) => {
    if (!jobId) return
    setError(null)
    setStep('rendering')
    setMessage('正在生成 KTV 视频...')
    connectWs(jobId)

    try {
      const res = await fetch(`${API}/jobs/${jobId}/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '渲染失败')
      }
    } catch (err) {
      setError(err.message)
      setStep('lyrics_edit')
    }
  }, [jobId, connectWs])

  // 清除错误
  const clearError = useCallback(() => setError(null), [])

  // 回退
  const goBack = useCallback(() => {
    setError(null)
    switch (step) {
      case 'lyrics':
      case 'recognizing':
        break
      case 'lyrics_edit':
        setStep('lyrics')
        break
      case 'aligning':
        setStep('lyrics_edit')
        break
      case 'rendering':
        setStep('lyrics_edit')
        break
      case 'done':
        setStep('lyrics_edit')
        break
      default:
        break
    }
  }, [step])

  // 重试分离
  const retrySeparation = useCallback(async () => {
    if (!jobId) return
    setError(null)
    setSeparationStatus('running')
    setSeparationProgress(0)
    setSeparationMessage('正在重新分离人声...')
    connectWs(jobId)
    try {
      const res = await fetch(`${API}/jobs/${jobId}/separate`, { method: 'POST' })
      if (!res.ok) throw new Error('启动人声分离失败')
    } catch (err) {
      setSeparationStatus('failed')
      setSeparationMessage(err.message)
      setError(err.message)
    }
  }, [jobId, connectWs])

  // 重置
  const reset = useCallback(() => {
    cleanup()
    setJobId(null)
    setJob(null)
    setStep('upload')
    setProgress(0)
    setMessage('')
    setError(null)
    setSeparationStatus('idle')
    setSeparationProgress(0)
    setSeparationMessage('')
  }, [cleanup])

  return {
    jobId, job, step, progress, message, error,
    separationStatus, separationProgress, separationMessage,
    uploadVideo, recognizeLyrics, submitLyrics,
    searchLyrics, fetchAndSubmitLyrics,
    updateLyrics, alignLyrics, renderVideo, reset,
    clearError, goBack, retrySeparation, setStep,
  }
}
