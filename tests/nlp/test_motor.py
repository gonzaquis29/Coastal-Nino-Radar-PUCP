"""Motor de la app sin torch (docs/app/definicion.md, sección 14), con un tokenizador sintético."""

import json

import numpy as np
from tokenizers import Tokenizer, models, pre_tokenizers, processors

from radar import config
from radar.app import validar_arranque as va
from radar.nlp import motor

VOCAB = {"<pad>": 0, "<s>": 1, "</s>": 2, "[UNK]": 3, "el": 4, "nino": 5, "costero": 6, "mar": 7}


def tokenizador(tmp_path):
    t = Tokenizer(models.WordLevel(VOCAB, unk_token="[UNK]"))
    t.pre_tokenizer = pre_tokenizers.Whitespace()
    t.post_processor = processors.TemplateProcessing(single="<s> $A </s>", special_tokens=[("<s>", 1), ("</s>", 2)])
    ruta = tmp_path / "tok.json"
    ruta.write_text(json.dumps({"pad": "<pad>", "pad_id": 0, "tokenizador": t.to_str()}), encoding="utf-8")
    return motor.Tokenizador(ruta)


def test_tokenizador_como_el_de_transformers(tmp_path):
    tok = tokenizador(tmp_path)
    assert tok("el nino")["input_ids"] == [1, 4, 5, 2]
    assert tok(["el nino", "mar"], add_special_tokens=False)["input_ids"] == [[4, 5], [7]]


def test_lote_trunca_rellena_y_vuelve_sin_truncar(tmp_path):
    tok = tokenizador(tmp_path)
    ids, mascara = tok.lote(["el nino costero mar", "mar"], largo=4)
    assert ids.tolist() == [[1, 4, 5, 2], [1, 7, 2, 0]]
    assert mascara.tolist() == [[1, 1, 1, 1], [1, 1, 1, 0]]
    assert len(tok("el nino costero mar el nino")["input_ids"]) == 8  # el truncamiento no queda puesto


def test_vectores_con_promedio_de_tokens_y_normalizados(tmp_path):
    class Sesion:
        def run(self, _, feed):
            return [np.ones(feed["input_ids"].shape + (3,), dtype=np.float32) * feed["input_ids"][..., None]]

    o = motor.Onnx32.__new__(motor.Onnx32)
    o.tok, o.prefijo, o.largo, o.sesion, o.entradas = (
        tokenizador(tmp_path),
        "",
        8,
        Sesion(),
        {"input_ids", "attention_mask"},
    )
    v = o.encode(["el nino", "mar"])
    assert v.shape == (2, 3) and np.allclose(np.linalg.norm(v, axis=1), 1)


def test_sin_archivos_o_con_torch_no_hay_motor(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DIR_MOTOR_APP", tmp_path)
    assert motor.para_app("org/no-existe") is None  # falta el tokenizador: la app sigue con torch
    monkeypatch.setattr(config, "MOTOR_APP", "torch")
    assert motor.para_app("org/no-existe") is None


def escribir_tokenizador(ruta, **cambios):
    especiales = [{"content": "<s>", "lstrip": False}, {"content": "<mask>", "lstrip": False}]
    datos = {"model": {"vocab": VOCAB}, "truncation": None, "padding": None, "added_tokens": especiales} | cambios
    ruta.write_text(json.dumps({"pad": "<pad>", "pad_id": 0, "tokenizador": json.dumps(datos)}), encoding="utf-8")


def test_tokenizador_se_comparte_solo_con_el_mismo_contenido(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DIR_MOTOR_APP", tmp_path)
    monkeypatch.setattr(motor, "_compartidos", {})
    monkeypatch.setattr(motor, "Tokenizador", lambda ruta: object())
    mascara = [{"content": "<s>", "lstrip": False}, {"content": "<mask>", "lstrip": True}]
    especial = [{"content": "<s>", "lstrip": True}, {"content": "<mask>", "lstrip": False}]
    escribir_tokenizador(tmp_path / "a.json")
    escribir_tokenizador(tmp_path / "b.json", truncation={"max_length": 128}, added_tokens=mascara)
    escribir_tokenizador(tmp_path / "c.json", model={"vocab": {"otro": 0}})
    escribir_tokenizador(tmp_path / "d.json", added_tokens=especial)
    assert motor.tokenizador("a") is motor.tokenizador("b")
    assert len({id(motor.tokenizador(x)) for x in "acd"}) == 3


def test_pesos_aparte_solo_si_estan_completos_y_son_del_mismo_onnx(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DIR_MOTOR_APP", tmp_path)
    onnx = tmp_path / "rev1" / "onnx" / "model.onnx"
    onnx.parent.mkdir(parents=True)
    onnx.write_bytes(b"12345")
    monkeypatch.setattr(motor, "_ruta_onnx", lambda repo: str(onnx))
    carpeta = motor._dir_pesos("org/m")
    carpeta.mkdir()
    assert motor._ruta_pesos_aparte("org/m") is None
    (carpeta / "modelo.onnx").write_bytes(b"m")
    (carpeta / motor.ARCHIVO_PESOS).write_bytes(b"ppp")
    assert motor._ruta_pesos_aparte("org/m") is None  # sin la marca: se cortó a medias
    marca = {"origen": {"revision": "rev1", "bytes": 5}, "bytes_pesos": 3}
    (carpeta / motor.ARCHIVO_ORIGEN).write_text(json.dumps(marca), encoding="utf-8")
    assert motor._ruta_pesos_aparte("org/m") == carpeta / "modelo.onnx"
    (carpeta / motor.ARCHIVO_PESOS).write_bytes(b"pp")
    assert motor._ruta_pesos_aparte("org/m") is None
    (carpeta / motor.ARCHIVO_PESOS).write_bytes(b"ppp")
    onnx.write_bytes(b"123456")  # otro ONNX
    assert motor._ruta_pesos_aparte("org/m") is None


def test_sinteticos_fijados():
    assert len(va.TEXTOS) == 40 and len(va.CONSULTAS) == 20
    assert va.ARRANQUE_MAXIMO == 8.0 and va.COSENO_MINIMO == 0.9999
