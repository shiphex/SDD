import array
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import media_tools as media


class RetimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source.wav'
        self.samples = array.array('h', [int(3000*math.sin(2*math.pi*440*n/16000))
                                       if n < 16000 or n >= 24000 else n % 71
                                       for n in range(40000)])
        with wave.open(str(self.source), 'wb') as w:
            w.setparams((1,2,16000,0,'NONE',''))
            w.writeframes(self.samples.tobytes())
        self.base_map = self.root / 'base.json'
        self.base_map.write_text(json.dumps({'source': str(self.source), 'source_duration':2.5,
            'output_duration':2.5, 'cuts':[], 'kept':[{'source_start':0,'source_end':2.5,
                'output_start':0,'output_end':2.5}]}))
        def source(path, aid):
            return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'artifact_id':aid}
        self.data = {'source':source(self.source,'full-retime-baseline-audio'),
            'source_map':source(self.base_map,'full-retime-baseline-map'),
            'segments':[{'start':0,'end':1,'kind':'speech','tempo':1.25},
                        {'start':1,'end':1.5,'kind':'pause','tempo':1},
                        {'start':1.5,'end':2.5,'kind':'speech','tempo':1.25}]}
        self.plan = self.root/'timeline.json'
        self.plan.write_text(json.dumps(self.data))

    def run_retime(self):
        with patch.object(media, '_assert_retime_approved'):
            media.retime_audio(self.plan,self.root/'out.wav',self.root/'maps'/'out.json',run_id='fixture')

    def test_speech_changes_duration_and_preserves_pitch_pause_pcm(self):
        self.run_retime()
        data=json.loads((self.root/'maps'/'out.json').read_text())
        self.assertEqual(data['schema_version'],3)
        self.assertAlmostEqual(data['output_duration'],2.1,places=4)
        with wave.open(str(self.root/'out.wav')) as w: out=array.array('h',w.readframes(w.getnframes()))
        pause=data['kept'][1]
        a,b=round(pause['output_start']*16000),round(pause['output_end']*16000)
        self.assertEqual(out[a:b],self.samples[16000:24000])
        # A chipmunk resampling implementation would move the tone to 550 Hz.
        tone=out[1600:11200]
        crossings=sum(tone[n-1]<0<=tone[n] for n in range(1,len(tone)))
        self.assertAlmostEqual(crossings/(len(tone)/16000),440,delta=5)
        media.validate_cut_map(data,2.1)
        data['kept'][1]['output_end']+=.01
        with self.assertRaises(ValueError): media.validate_cut_map(data,2.1)

    def test_wrong_hash_and_invalid_segments_rejected(self):
        self.data['source']['sha256']='0'*64
        self.plan.write_text(json.dumps(self.data))
        with self.assertRaisesRegex(ValueError,'hash'): self.run_retime()
        self.data['source']['sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.data['segments'][1]['start']=.9
        self.plan.write_text(json.dumps(self.data))
        with self.assertRaisesRegex(ValueError,'continuous'): self.run_retime()

    def test_retime_rejects_gate_before_reading_inputs(self):
        with patch.object(media.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','denied')):
            with self.assertRaisesRegex(ValueError,'approval'):
                media.retime_audio(self.root/'missing.json',self.root/'out.wav',self.root/'out.json',run_id='fixture')

    def test_outputs_cannot_overwrite_timeline(self):
        original=self.plan.read_bytes()
        with patch.object(media, '_assert_retime_approved'):
            with self.assertRaisesRegex(ValueError,'overwrite'):
                media.retime_audio(self.plan,self.plan,self.root/'out.json',run_id='fixture')
        self.assertEqual(self.plan.read_bytes(),original)

    def test_schema_three_requires_source_partition_and_declared_cuts(self):
        self.run_retime()
        data=json.loads((self.root/'maps'/'out.json').read_text())
        data['kept'][0]['source_start']+=.2
        data['kept'][0]['source_end']+=.2
        with self.assertRaisesRegex(ValueError,'source|partition'):
            media.validate_cut_map(data,data['output_duration'])
        self.data['segments']=[{'start':0,'end':1,'kind':'speech','tempo':1.25},
             {'start':1,'end':1.25,'kind':'pause','tempo':1},
             {'start':1.25,'end':1.4,'kind':'cut','tempo':1},
             {'start':1.4,'end':1.5,'kind':'pause','tempo':1},
             {'start':1.5,'end':2.5,'kind':'speech','tempo':1.25}]
        self.plan.write_text(json.dumps(self.data));self.run_retime()
        data=json.loads((self.root/'maps'/'out.json').read_text())
        media.validate_cut_map(data,data['output_duration'])
        data['cuts']=[]
        with self.assertRaisesRegex(ValueError,'source|partition'):
            media.validate_cut_map(data,data['output_duration'])


if __name__=='__main__': unittest.main()
