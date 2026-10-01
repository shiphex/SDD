import { useEffect, useMemo, useRef, useState } from 'react';
import './tokens.css';
import './audio-sync.css';

type Scene = {
  id: string;
  start: number;
  end: number;
  title: string;
  body?: string;
  visual?: string;
};

type Timeline = {
  audioSrc: string;
  scenes: Scene[];
};

const emptyTimeline: Timeline = { audioSrc: '', scenes: [] };

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return '00:00';
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const rest = safeSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
}

export default function App() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [timeline, setTimeline] = useState<Timeline>(emptyTimeline);
  const [loadError, setLoadError] = useState('');
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    fetch('/timeline.json')
      .then((response) => {
        if (!response.ok) throw new Error(`timeline.json returned ${response.status}`);
        return response.json() as Promise<Timeline>;
      })
      .then((data) => setTimeline(data))
      .catch((error: unknown) => setLoadError(String(error)));
  }, []);

  const activeIndex = useMemo(() => {
    const match = timeline.scenes.findIndex(
      (scene) => currentTime >= scene.start && currentTime < scene.end,
    );
    if (match >= 0) return match;
    let prior = -1;
    timeline.scenes.forEach((scene, index) => {
      if (scene.start <= currentTime) prior = index;
    });
    return prior;
  }, [currentTime, timeline.scenes]);
  const activeScene = activeIndex >= 0 ? timeline.scenes[activeIndex] : undefined;

  function seekTo(seconds: number) {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, Math.min(seconds, duration || seconds));
    setCurrentTime(audio.currentTime);
  }

  return (
    <main className="audio-presentation">
      <section className="stage" aria-live="polite">
        <div className="stage-label">讲解演示 · 音频同步</div>
        {activeScene ? (
          <>
            <div className="scene-counter">
              {String(activeIndex + 1).padStart(2, '0')} / {String(timeline.scenes.length).padStart(2, '0')}
            </div>
            <h1>{activeScene.title}</h1>
            {activeScene.body && <p className="scene-body">{activeScene.body}</p>}
            {activeScene.visual && <p className="visual-note">{activeScene.visual}</p>}
          </>
        ) : (
          <div className="empty-state">
            <h1>等待画面提纲</h1>
            <p>在 public/timeline.json 填入按最终音轨时间编排的画面步骤。</p>
          </div>
        )}
        {loadError && <p className="load-error">无法读取时间线：{loadError}</p>}
      </section>

      <section className="transport" aria-label="音频播放与定位">
        <audio
          ref={audioRef}
          controls
          preload="metadata"
          src={timeline.audioSrc || undefined}
          onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)}
          onDurationChange={(event) => setDuration(event.currentTarget.duration)}
          onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
          onSeeked={(event) => setCurrentTime(event.currentTarget.currentTime)}
        />
        <div className="seek-row">
          <span>{formatTime(currentTime)}</span>
          <input
            aria-label="音频定位"
            type="range"
            min={0}
            max={duration || 0}
            step={0.05}
            value={Math.min(currentTime, duration || 0)}
            onChange={(event) => seekTo(Number(event.currentTarget.value))}
            disabled={!duration}
          />
          <span>{formatTime(duration)}</span>
        </div>
      </section>

      <nav className="scene-list" aria-label="画面步骤">
        {timeline.scenes.map((scene, index) => (
          <button
            className={index === activeIndex ? 'scene-button active' : 'scene-button'}
            key={scene.id}
            type="button"
            onClick={() => seekTo(scene.start)}
          >
            <span>{formatTime(scene.start)}</span>
            <strong>{scene.title}</strong>
          </button>
        ))}
      </nav>
    </main>
  );
}
