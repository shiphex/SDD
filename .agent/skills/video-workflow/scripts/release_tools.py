"""Local release helpers. They do not approve content, log in, or upload files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import wave
import zipfile


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _new_output(path: Path, inputs: list[Path]) -> Path:
    path = path.resolve()
    if path in [source.resolve() for source in inputs]:
        raise ValueError('Output would overwrite an input')
    if path.exists():
        raise ValueError('Output already exists; use a new release path')
    return path


def _probe(path: Path) -> dict:
    return json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
        text=True, encoding='utf-8'))


def _aac_hash(path: Path) -> str:
    result = subprocess.check_output(
        ['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0', '-c', 'copy',
         '-f', 'hash', '-hash', 'sha256', '-'], text=True, encoding='utf-8')
    match = re.fullmatch(r'SHA256=([0-9a-f]{64})\s*', result)
    if not match:
        raise ValueError('Unable to verify AAC packet payload hash')
    return match[1]


def reuse_audio(video: Path, baseline_video: Path, audio: Path,
                baseline_audio: Path, output: Path) -> dict:
    """Mux new visuals with the AAC track from the accepted, unchanged baseline."""
    output = _new_output(output, [video, baseline_video, audio, baseline_audio])
    audio_hash = _sha256(audio)
    if audio_hash != _sha256(baseline_audio):
        raise ValueError('Audio hash changed; AAC reuse requires an unchanged WAV')
    with wave.open(str(audio), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getcomptype()) != (1, 2, 'NONE'):
            raise ValueError('Expected mono 16-bit PCM WAV')
        duration = wav.getnframes() / wav.getframerate()
    if duration <= 0:
        raise ValueError('Audio duration must be positive')
    picture_probe = _probe(video)
    baseline_probe = _probe(baseline_video)
    if not any(s['codec_type'] == 'video' for s in picture_probe['streams']):
        raise ValueError('New visuals have no video stream')
    picture = next(s for s in picture_probe['streams'] if s['codec_type'] == 'video')
    def check_picture(stream: dict) -> None:
        seconds = float(stream.get('duration', 0))
        start = float(stream.get('start_time', 0))
        if not 0 < seconds or abs(seconds - duration) > .05:
            raise ValueError('Video stream duration does not cover the unchanged WAV')
        if not abs(start) <= .001:
            raise ValueError('Video stream coverage must start at zero')
    check_picture(picture)
    sound = next((s for s in baseline_probe['streams'] if s['codec_type'] == 'audio'), None)
    if sound is None or sound['codec_name'] != 'aac':
        raise ValueError('Baseline video must contain AAC audio')
    for label, seconds in [('visuals', float(picture_probe['format']['duration'])),
                           ('baseline', float(baseline_probe['format']['duration'])),
                           ('AAC', float(sound.get('duration', baseline_probe['format']['duration'])))]:
        if not 0 < seconds or abs(seconds - duration) > .2:
            raise ValueError(f'{label} duration differs from the unchanged WAV')
    if abs(float(sound.get('start_time', 0))) > .05:
        raise ValueError('Baseline audio has a nonzero start offset')
    expected = _aac_hash(baseline_video)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='release-audio-', dir=output.parent) as temp:
        staged = Path(temp) / 'release.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video), '-i', str(baseline_video),
                        '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', '-map_metadata', '-1',
                        '-map_metadata:s', '-1', '-map_chapters', '-1', '-movflags', '+faststart',
                        str(staged)], check=True)
        actual = _aac_hash(staged)
        if actual != expected:
            raise ValueError('Output AAC hash differs from the accepted baseline')
        if abs(float(_probe(staged)['format']['duration']) - duration) > .2:
            raise ValueError('Output duration differs from the unchanged WAV')
        check_picture(next(s for s in _probe(staged)['streams'] if s['codec_type'] == 'video'))
        staged.replace(output)
    return {'output': str(output), 'wav_sha256': audio_hash, 'aac_sha256': actual,
            'baseline_video_sha256': _sha256(baseline_video), 'audio_seconds': duration,
            'operation': 'stream_copy'}


def package_public(manifest: Path, output: Path) -> dict:
    """Build a ZIP exclusively from relative paths and reviewed hashes in a manifest."""
    manifest = manifest.resolve()
    data = json.loads(manifest.read_text(encoding='utf-8-sig'))
    entries = data.get('files')
    if not isinstance(entries, list) or not entries:
        raise ValueError('Public file manifest is empty')
    root = manifest.parent
    selected = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
            raise ValueError('Each public file requires a relative path and SHA256')
        name = entry['path'].replace('\\', '/')
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or ':' in name or not relative.parts:
            raise ValueError('Public file paths must stay relative and inside the manifest directory')
        name = str(relative)
        if name.casefold() in seen:
            raise ValueError('Duplicate public archive path')
        seen.add(name.casefold())
        expected = entry.get('sha256', '')
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
            raise ValueError('Each public file requires a valid SHA256 hash')
        source = (root / name).resolve()
        if not source.is_relative_to(root):
            raise ValueError('Public file path resolves outside the manifest directory')
        selected.append((name, source, expected.lower()))
    output = _new_output(output, [manifest] + [s for _, s, _ in selected])
    for name, source, expected in selected:
        if not source.is_file():
            raise ValueError(f'Missing public file: {name}')
        if _sha256(source) != expected:
            raise ValueError(f'Public file hash changed: {name}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='release-package-', dir=output.parent) as temp:
        staged = Path(temp) / 'public.zip'
        with zipfile.ZipFile(staged, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, source, _ in selected:
                archive.write(source, arcname=name)
        files = []
        with zipfile.ZipFile(staged) as archive:
            if archive.namelist() != [name for name, _, _ in selected]:
                raise ValueError('ZIP contents differ from the public manifest')
            for name, _, expected in selected:
                digest = hashlib.sha256()
                with archive.open(name) as content:
                    for chunk in iter(lambda: content.read(1024 * 1024), b''):
                        digest.update(chunk)
                if digest.hexdigest() != expected:
                    raise ValueError(f'Archived public file hash changed: {name}')
                files.append({'path': name, 'sha256': expected, 'bytes': archive.getinfo(name).file_size})
        staged.replace(output)
    return {'output': str(output), 'sha256': _sha256(output), 'files': files}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    reuse = commands.add_parser('reuse-audio')
    for flag in ('video', 'baseline-video', 'audio', 'baseline-audio', 'output'):
        reuse.add_argument('--' + flag, type=Path, required=True)
    package = commands.add_parser('package-public')
    for flag in ('manifest', 'output'):
        package.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'reuse-audio':
            result = reuse_audio(args.video, args.baseline_video, args.audio, args.baseline_audio, args.output)
        else:
            result = package_public(args.manifest, args.output)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, f'error: {error}\n')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
