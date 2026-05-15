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
  const { step, error, reset } = ktv

  const getStepIndex = () => {
    switch (step) {
      case 'upload':
      case 'uploading': return 0
      case 'separating': return 1
      case 'lyrics':
      case 'recognizing': return 2
      case 'lyrics_edit': return 3
      case 'aligning': return 4
      case 'rendering': return 5
      case 'done': return 6
      default: return 0
    }
  }

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
            <div className="flex items-center justify-between">
              <p className="text-red-300 text-sm">⚠️ {error}</p>
              <button onClick={() => {}} className="text-red-400 text-xs hover:text-red-300">
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

          {step === 'separating' && (
            <ProcessingStep
              title="人声分离中"
              progress={ktv.progress}
              message={ktv.message}
              icon="🎵"
            />
          )}

          {(step === 'lyrics' || step === 'recognizing') && (
            <LyricsStep
              onSubmit={ktv.submitLyrics}
              onRecognize={ktv.recognizeLyrics}
              recognizing={step === 'recognizing'}
              progress={ktv.progress}
              message={ktv.message}
            />
          )}

          {step === 'lyrics_edit' && (
            <LyricsEditStep
              job={ktv.job}
              onUpdate={ktv.updateLyrics}
              onAlign={ktv.alignLyrics}
              onRender={ktv.renderVideo}
            />
          )}

          {step === 'aligning' && (
            <ProcessingStep
              title="时间轴对齐中"
              progress={ktv.progress}
              message={ktv.message}
              icon="⏱️"
            />
          )}

          {step === 'rendering' && (
            <RenderStep progress={ktv.progress} message={ktv.message} />
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
