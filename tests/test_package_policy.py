from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from package_policy import validate_payload, payload_problem


class PackagePolicyTests(unittest.TestCase):
    def test_models_optional_runtimes_and_data_are_refused(self):
        for name in ['models/model.gguf','voice/model.safetensors','voice/weights.onnx','runtimes/model.fermion',
                     '_internal/claude_agent_sdk/_bundled/claude.exe','_internal/cyai/web/cyannota/ffmpeg/ffmpeg-core.wasm.part0',
                     '_internal/torch/lib/torch_cpu.dll','config.json','.data/conversations.sqlite3','secrets.dpapi',
                     '../outside','C:/config.json']:
            with self.subTest(name=name):
                self.assertIsNotNone(payload_problem(name))
                with self.assertRaises(ValueError):validate_payload([name])

    def test_minimal_runtime_sdk_and_source_licenses_remain_available(self):
        files=['CyAIOrchestrator.exe','_internal/python311.dll','_internal/claude_agent_sdk/_client.py',
               '_internal/cyai/web/cyannota/ffmpeg/ffmpeg-core.js',
               '_internal/cyai/web/cyannota/ffmpeg/ffmpeg-core.wasm.parts.json',
               '_internal/cyai/web/cyannota/source.zip','_internal/cyai/web/cyannota/LICENSE.txt']
        validate_payload(files)
