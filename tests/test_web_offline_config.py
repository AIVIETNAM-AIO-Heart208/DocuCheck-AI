"""VietOCR config adapter uses local YAML without fetching a named config."""

import sys
import types

from docucheck.ocr.recognizers import VietOCRBaseline


def test_local_config_path_avoids_network_loader(tmp_path,monkeypatch):
    model=tmp_path / "weights.pth"
    model.write_bytes(b"fake-weights")
    config=tmp_path / "config.yml"
    config.write_text("fake fixture; FakeCfg does not parse YAML")
    calls=[]
    class FakeCfg:
        @staticmethod
        def load_config_from_file(path):
            calls.append(path)
            return {"cnn":{},"predictor":{}}
        @staticmethod
        def load_config_from_name(name):
            raise AssertionError("Offline adapter fetched a named config")
    class FakePredictor:
        def __init__(self,cfg):
            assert cfg["weights"]==str(model)
            assert cfg["cnn"]["pretrained"] is False
    config_module=types.ModuleType("vietocr.tool.config")
    config_module.Cfg=FakeCfg
    predictor_module=types.ModuleType("vietocr.tool.predictor")
    predictor_module.Predictor=FakePredictor
    for name in ("vietocr","vietocr.tool"):
        monkeypatch.setitem(sys.modules,name,types.ModuleType(name))
    monkeypatch.setitem(sys.modules,"vietocr.tool.config",config_module)
    monkeypatch.setitem(sys.modules,"vietocr.tool.predictor",predictor_module)
    recognizer=VietOCRBaseline(model_path=model,device="cpu",config_path=config,scale_factor=2)
    assert calls==[str(config)]
    assert recognizer.scale_factor==2
