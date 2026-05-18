import { useKTV } from './hooks/useKTV'
import Header from './components/Header'
import StepIndicator from './components/StepIndicator'
import UploadStep from './components/UploadStep'
import ProcessingStep from './components/ProcessingStep'
import LyricsStep from './components/LyricsStep'
import LyricsEditStep from './components/LyricsEditStep'
import RenderStep from './components/RenderStep'
import DoneStep from './components/DoneStep'

export default function App() {
  const ktv = useKTV()
  const { step, error, reset, clearError, goBack } = ktv

  const getStepIndex = () => {
    switch (step) {
      case 'upload':
      case 'uploading': return 0
      case 'lyrics':
      case 'recognizing': return 1
      case 'lyrics_edit': return 2
      case 'aligning': return 3
      case 'rendering': return 4
      case 'done': return 5
      default: return 0
    }
  }

  // 根据当前步骤获取重试方法
  const getRetryAction = () => {
    switch (step) {
      case 'aligning':
        return { label: '重试对齐', action: ktv.alignLyrics }
      case 'rendering':
        return { label: '重试合成', action: () => ktv.renderVideo() }
      default:
        return null
    }
  }

  // 能否返回上一步
  const canGoBack = ['lyrics', 'lyrics_edit', 'aligning', 'rendering', 'done'].includes(step)

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* 背景装饰 */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] bg-primary-600/20 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[400px] h-[400px] bg-accent-500/15 rounded-full blur-[120px]" />
        <div className="absolute top-[40%] right-[20%] w-[300px] h-[300px] bg-purple-600/10 rounded-full blur-[100px]" />
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8">
        <Header />

        {/* 步骤指示器 */}
        {step !== 'upload' && step !== 'uploading' && (
          <StepIndicator currentStep={getStepIndex()} />
        )}

        {/* 错误提示 */}
        {error && (
          <div className="glass-card p-4 mb-6 border-red-500/30 bg-red-500/10">
            <p className="text-red-300 text-sm mb-3">⚠️ {error}</p>
            <div className="flex items-center gap-2 flex-wrap">
              {getRetryAction() && (
                <button
                  onClick={() => { clearError(); getRetryAction().action() }}
                  className="px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 text-xs font-medium transition-all"
                >
                  🔄 {getRetryAction().label}
                </button>
              )}
              {canGoBack && (
                <button
                  onClick={goBack}
                  className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-gray-300 text-xs font-medium transition-all"
                >
                  ← 返回上一步
                </button>
              )}
              <button
                onClick={reset}
                className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 text-xs transition-all"
              >
                从头开始
              </button>
              <button
                onClick={clearError}
                className="ml-auto text-gray-500 text-xs hover:text-gray-400"
              >
                关闭
              </button>
            </div>
          </div>
        )}

        {/* 主内容 */}
        <main>
          {(step === 'upload' || step === 'uploading') && (
            <UploadStep onUpload={ktv.uploadVideo} loading={step === 'uploading'} />
          )}

          {(step === 'lyrics' || step === 'recognizing') && (
            <LyricsStep
              onSubmit={ktv.submitLyrics}
              onRecognize={ktv.recognizeLyrics}
              onSearchLyrics={ktv.searchLyrics}
              onFetchLyrics={ktv.fetchAndSubmitLyrics}
              recognizing={step === 'recognizing'}
              progress={ktv.progress}
              message={ktv.message}
              separationStatus={ktv.separationStatus}
              separationProgress={ktv.separationProgress}
              separationMessage={ktv.separationMessage}
              onRetrySeparation={ktv.retrySeparation}
            />
          )}

          {step === 'lyrics_edit' && (
            <LyricsEditStep
              job={ktv.job}
              onUpdate={ktv.updateLyrics}
              onAlign={ktv.alignLyrics}
              onRender={ktv.renderVideo}
              separationStatus={ktv.separationStatus}
              separationProgress={ktv.separationProgress}
              separationMessage={ktv.separationMessage}
              onRetrySeparation={ktv.retrySeparation}
            />
          )}

          {step === 'aligning' && (
            <ProcessingStep
              title="时间轴对齐中"
              progress={ktv.progress}
              message={ktv.message}
              icon="⏱️"
              error={error}
              onRetry={ktv.alignLyrics}
              onBack={() => ktv.setStep('lyrics_edit')}
            />
          )}

          {step === 'rendering' && (
            <RenderStep
              progress={ktv.progress}
              message={ktv.message}
              error={error}
              onRetry={() => ktv.renderVideo()}
              onBack={() => ktv.setStep('lyrics_edit')}
            />
          )}

          {step === 'done' && (
            <DoneStep job={ktv.job} jobId={ktv.jobId} onReset={reset} />
          )}
        </main>

        {/* 底部 */}
        <footer className="text-center mt-12 text-gray-500 text-sm">
          Powered by <span className="text-primary-400">Demucs</span> · 
          <span className="text-primary-400"> Whisper</span> · 
          <span className="text-primary-400"> FFmpeg</span>
          <br />
          <span className="text-xs">Anisong / JPop カラオケ動画メーカー</span>
        </footer>
      </div>
    </div>
  )
}
