/**
 * AI-KTV 核心 Hook
 * 管理整个 KTV 视频制作流程的状态
 */
import { useState, useRef, useCallback, useEffect } from 'react'

const API = '/api'

export function useKTV() {
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [step, setStep] = useState('upload') // upload | separating | lyrics | aligning | rendering | done
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState(null)
  const wsRef = useRef(null)
  const pollRef = useRef(null)

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

  // WebSocket 监听 — 每次需要实时追踪时调用
  const connectWs = useCallback((id) => {
    // 关闭旧连接但不清轮询
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
        setJob(data)
        setProgress(data.progress ?? 0)
        setMessage(data.message ?? '')
        _updateStep(data)
      } catch (err) {
        console.error('WS parse error:', err)
      }
    }

    ws.onerror = () => {
      startPolling(id)
    }

    ws.onclose = () => {
      wsRef.current = null
      // WS 断开后启动轮询兜底
      startPolling(id)
    }
  }, [])

  // 轮询 — 作为 WS 的兜底
  const startPolling = useCallback((id) => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/jobs/${id}`)
        if (res.ok) {
          const data = await res.json()
          setJob(data)
          setProgress(data.progress ?? 0)
          setMessage(data.message ?? '')
          _updateStep(data)

          // 到稳定态时停止轮询
          const s = data.status
          if (s === 'done' || s === 'failed' || s === 'separated' ||
              s === 'lyrics_ready' || s === 'probed') {
            clearInterval(pollRef.current)
            pollRef.current = null
          }
        }
      } catch (e) {
        console.error('Poll error:', e)
      }
    }, 1500)
  }, [])

  // 根据后端状态更新前端步骤
  const _updateStep = (data) => {
    const status = data?.status
    if (!status) return

    switch (status) {
      case 'uploaded':
      case 'probed':
        setStep('uploaded')
        break
      case 'separating':
        setStep('separating')
        break
      case 'separated':
        setStep('lyrics')
        break
      case 'recognizing':
        setStep('recognizing')
        break
      case 'lyrics_ready':
        // 检查是否有 error 信息（对齐失败的情况）
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
        setError(data.message || '发生错误')
        break
    }
  }

  // ========== Actions ==========

  // 上传视频
  const uploadVideo = useCallback(async (file) => {
    setError(null)
    setStep('uploading')
    setProgress(0)
    setMessage('上传中...')

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

      // 自动开始分离
      setStep('separating')
      setMessage('正在提取音频并分离人声...')
      const sepRes = await fetch(`${API}/jobs/${job_id}/separate`, { method: 'POST' })
      if (!sepRes.ok) throw new Error('启动人声分离失败')

    } catch (err) {
      setError(err.message)
      setStep('upload')
    }
  }, [connectWs])

  // AI 识别歌词
  const recognizeLyrics = useCallback(async () => {
    if (!jobId) return
    setError(null)
    setStep('recognizing')
    setMessage('正在识别歌词...')

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
    connectWs(jobId)  // 重新建立 WS 追踪进度

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
    connectWs(jobId)  // 重新建立 WS 追踪进度

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

  // 回退到上一步（不丢失数据）
  const goBack = useCallback(() => {
    setError(null)
    switch (step) {
      case 'lyrics':
      case 'recognizing':
        // 回到分离完成状态不合理，停留在歌词页
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

  // 重试当前步骤
  const retrySeparation = useCallback(async () => {
    if (!jobId) return
    setError(null)
    setStep('separating')
    setMessage('正在重新分离人声...')
    connectWs(jobId)
    try {
      const res = await fetch(`${API}/jobs/${jobId}/separate`, { method: 'POST' })
      if (!res.ok) throw new Error('启动人声分离失败')
    } catch (err) {
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
  }, [cleanup])

  return {
    jobId, job, step, progress, message, error,
    uploadVideo, recognizeLyrics, submitLyrics,
    updateLyrics, alignLyrics, renderVideo, reset,
    clearError, goBack, retrySeparation, setStep,
  }
}
