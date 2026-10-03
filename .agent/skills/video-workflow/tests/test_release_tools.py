"""Release helpers must preserve approved audio and package only named final files."""
import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    import release_tools
except ModuleNotFoundError:
    release_tools = None


class ReleaseToolsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(release_tools, 'Release helpers have not been implemented')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def manifest(self, entries=None):
        public = self.root / '成片.srt'
        public.write_bytes('1\n00:00:00,000 --> 00:00:01,000\n示例\n'.encode('utf-8'))
        (self.root / 'raw-recording.wav').write_bytes(b'private recording')
        path = self.root / 'public-files.json'
        path.write_text(json.dumps({'files': entries if entries is not None else [
            {'path': public.name, 'sha256': hashlib.sha256(public.read_bytes()).hexdigest()}]},
            ensure_ascii=False), encoding='utf-8-sig')
        return path, public

    def test_package_includes_only_named_public_files_with_exact_bytes(self):
        manifest, public = self.manifest()
        archive = self.root / 'out' / '投稿包.zip'
        result = release_tools.package_public(manifest, archive)
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(z.namelist(), [public.name])
            self.assertEqual(z.read(public.name), public.read_bytes())
        self.assertEqual(result['files'][0]['sha256'], hashlib.sha256(public.read_bytes()).hexdigest())
        self.assertNotIn('uploaded', result)

    def test_package_rejects_changed_hash_before_creating_archive(self):
        manifest, public = self.manifest()
        public.write_bytes(b'changed after review')
        output = self.root / 'out.zip'
        with self.assertRaisesRegex(ValueError, 'hash'):
            release_tools.package_public(manifest, output)
        self.assertFalse(output.exists())

    def test_package_detects_file_change_during_archiving(self):
        manifest, public = self.manifest()
        output = self.root/'out.zip'
        original_write = zipfile.ZipFile.write
        def change_and_write(archive, filename, arcname=None):
            public.write_bytes(b'changed after initial hash check')
            return original_write(archive, filename, arcname=arcname)
        with patch.object(zipfile.ZipFile, 'write', change_and_write):
            with self.assertRaisesRegex(ValueError, 'hash'):
                release_tools.package_public(manifest, output)
        self.assertFalse(output.exists())

    def test_package_rejects_traversal_absolute_paths_and_duplicates(self):
        for names in [['../secret.txt'], ['C:/recording.wav'], ['/tmp/recording.wav'],
                      ['成片.srt', '成片.srt'], ['cover.jpg', 'COVER.jpg']]:
            with self.subTest(names=names):
                manifest, _ = self.manifest([{'path': name, 'sha256':'0'*64} for name in names])
                with self.assertRaises(ValueError):
                    release_tools.package_public(manifest, self.root/'out.zip')
                self.assertFalse((self.root/'out.zip').exists())

    def test_package_rejects_empty_manifest_and_preserves_existing_output(self):
        manifest, _ = self.manifest([])
        with self.assertRaisesRegex(ValueError, 'empty'):
            release_tools.package_public(manifest, self.root/'new.zip')
        manifest, _ = self.manifest()
        output = self.root/'old.zip';output.write_bytes(b'accepted prior package')
        with self.assertRaisesRegex(ValueError, 'exists'):
            release_tools.package_public(manifest, output)
        self.assertEqual(output.read_bytes(), b'accepted prior package')

    def wav(self, path, seconds=2, frequency=440):
        with wave.open(str(path),'wb') as wav:
            wav.setparams((1,2,16000,0,'NONE',''))
            pcm = array.array('h', (int(6000*math.sin(2*math.pi*frequency*n/16000))
                                    for n in range(round(seconds*16000))))
            if sys.byteorder != 'little':pcm.byteswap()
            wav.writeframes(pcm.tobytes())
        return path

    def video(self, name, wav, seconds=2, color='blue'):
        path=self.root/name
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
                        f'color=c={color}:s=320x180:r=30:d={seconds}','-i',str(wav),
                        '-t',str(seconds),'-c:v','libx264','-preset','ultrafast','-c:a','aac',
                        '-metadata','title=private source title',str(path)],check=True)
        return path

    def test_reuse_rejects_changed_pcm_before_reading_video(self):
        old=self.wav(self.root/'old.wav');new=self.wav(self.root/'new.wav',frequency=880)
        output=self.root/'release.mp4'
        with self.assertRaisesRegex(ValueError, 'hash|unchanged'):
            release_tools.reuse_audio(self.root/'visual.mp4',self.root/'baseline.mp4',new,old,output)
        self.assertFalse(output.exists())

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
    def test_reuse_copies_aac_and_new_picture_without_source_metadata(self):
        wav=self.wav(self.root/'accepted.wav')
        old=self.video('baseline.mp4',wav,color='blue')
        visual=self.video('new-visual.mp4',wav,color='red')
        output=self.root/'out'/'发布.mp4'
        result=release_tools.reuse_audio(visual,old,wav,wav,output)
        def payload(path,stream):
            return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map',stream,
                                            '-c','copy','-f','hash','-'],text=True).strip()
        self.assertEqual(payload(old,'0:a:0'),payload(output,'0:a:0'))
        self.assertEqual(payload(visual,'0:v:0'),payload(output,'0:v:0'))
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',
                                                 str(output)],text=True,encoding='utf-8'))
        self.assertNotIn('title',probe['format'].get('tags',{}))
        self.assertIn('aac_sha256',result)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
    def test_reuse_rejects_different_duration_and_preserves_inputs(self):
        wav=self.wav(self.root/'accepted.wav')
        old=self.video('baseline.mp4',wav)
        short=self.video('short.mp4',wav,seconds=1)
        old_bytes=old.read_bytes()
        with self.assertRaisesRegex(ValueError,'duration'):
            release_tools.reuse_audio(short,old,wav,wav,self.root/'out.mp4')
        with self.assertRaisesRegex(ValueError,'exists|overwrite'):
            release_tools.reuse_audio(old,old,wav,wav,old)
        self.assertEqual(old.read_bytes(),old_bytes)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
    def test_reuse_rejects_short_picture_hidden_by_long_audio_stream(self):
        wav=self.wav(self.root/'accepted.wav')
        old=self.video('baseline.mp4',wav)
        short=self.root/'short-picture.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
                        'color=c=red:s=320x180:r=30:d=1','-i',str(wav),'-c:v','libx264',
                        '-preset','ultrafast','-c:a','aac',str(short)],check=True)
        output=self.root/'release.mp4'
        with self.assertRaisesRegex(ValueError,'duration|coverage'):
            release_tools.reuse_audio(short,old,wav,wav,output)
        self.assertFalse(output.exists())

    def test_cli_packages_utf8_manifest_and_emits_json(self):
        manifest,_=self.manifest();output=self.root/'cli.zip'
        tool=Path(__file__).resolve().parents[1]/'scripts'/'release_tools.py'
        result=subprocess.run([sys.executable,str(tool),'package-public','--manifest',str(manifest),
                               '--output',str(output)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['files'][0]['path'],'成片.srt')


if __name__=='__main__':unittest.main()
