"""Motor de la app sin torch (docs/app/definicion.md, sección 14): ONNX en float32 con la librería tokenizers.

python -m radar.nlp.motor preparar   ->  guarda el tokenizador de cada modelo de la app (una vez, con transformers)

El tokenizador se guarda tal como lo arma transformers (no el tokenizer.json del repositorio: con e5 difiere en los
espacios repetidos), así los tokens son los mismos que con torch. Los archivos ONNX quedan en la caché de Hugging
Face. Si falta alguno, `para_app` devuelve None y quien llama usa torch como antes.
"""

import argparse
import json
import logging

import numpy as np

from radar import config
from radar.comun.registro import configurar

log = logging.getLogger(__name__)

ARCHIVO_ONNX = "onnx/model.onnx"  # float32; los cuantizados dan otros vectores (sección 14.2)


def _ruta_tokenizador(repo):
    return config.DIR_MOTOR_APP / (repo.replace("/", "--") + ".json")


def _ruta_onnx(repo):
    from huggingface_hub import hf_hub_download

    return hf_hub_download(repo, ARCHIVO_ONNX, local_files_only=True)


class Tokenizador:
    """Lo que Candidato y embeddings.Modelo piden a un tokenizador de transformers: tok(textos)["input_ids"]."""

    def __init__(self, ruta):
        from tokenizers import Tokenizer

        datos = json.loads(ruta.read_text(encoding="utf-8"))
        self.base = Tokenizer.from_str(datos["tokenizador"])
        self.base.no_truncation()
        self.base.no_padding()
        self.pad_id, self.pad = datos["pad_id"], datos["pad"]

    def __call__(self, textos, add_special_tokens=True, **_):
        unico = isinstance(textos, str)
        cod = self.base.encode_batch([textos] if unico else list(textos), add_special_tokens=add_special_tokens)
        ids = [c.ids for c in cod]
        return {"input_ids": ids[0] if unico else ids}

    def lote(self, textos, largo):
        """(ids, máscara) con truncamiento y relleno, como transformers con truncation=True y padding=True."""
        self.base.enable_truncation(largo)
        self.base.enable_padding(pad_id=self.pad_id, pad_token=self.pad)
        try:
            cod = self.base.encode_batch(list(textos))
        finally:
            self.base.no_truncation()
            self.base.no_padding()
        return (
            np.array([c.ids for c in cod], dtype=np.int64),
            np.array([c.attention_mask for c in cod], dtype=np.int64),
        )


class Onnx32:
    """El mismo cálculo que viabilidad.Torch (promedio de tokens y normalización) con onnxruntime.

    Sirve de motor de embeddings.Modelo (tok, embeber con el prefijo) y en lugar de un SentenceTransformer en
    candidatos.Candidato (tokenizer, max_seq_length, encode sin prefijo: lo agrega Candidato)."""

    def __init__(self, repo, prefijo="", largo=512):
        import onnxruntime as ort

        self.repo, self.prefijo, self.largo = repo, prefijo, largo
        self.tok = self.tokenizer = Tokenizador(_ruta_tokenizador(repo))
        self.max_seq_length = largo
        self.sesion = ort.InferenceSession(_ruta_onnx(repo), providers=["CPUExecutionProvider"])
        self.entradas = {i.name for i in self.sesion.get_inputs()}

    def _vectores(self, textos):
        ids, mascara = self.tok.lote(textos, self.largo)
        feed = {"input_ids": ids, "attention_mask": mascara, "token_type_ids": np.zeros_like(ids)}
        h = self.sesion.run(None, {k: v for k, v in feed.items() if k in self.entradas})[0]
        m = mascara[..., None].astype(np.float32)
        v = (h * m).sum(1) / m.sum(1)
        return (v / np.linalg.norm(v, axis=1, keepdims=True)).astype(np.float32)

    def embeber(self, textos):
        return self._vectores([self.prefijo + t for t in textos])

    def encode(self, textos, normalize_embeddings=True, batch_size=16, **_):
        if not textos:
            return np.zeros((0, 1), dtype=np.float32)
        return np.vstack([self._vectores(list(textos[i : i + batch_size])) for i in range(0, len(textos), batch_size)])


def para_app(repo, prefijo="", largo=512):
    """El motor ONNX si config.MOTOR_APP lo pide y están sus archivos; si no, None (quien llama usa torch)."""
    if config.MOTOR_APP != "onnx32":
        return None
    try:
        return Onnx32(repo, prefijo, largo)
    except Exception as e:  # cualquier falta (archivo, librería) deja a la app con torch, nunca sin funcionar
        log.warning("%s sin motor ONNX (%s: %s): se usa torch", repo, type(e).__name__, e)
        return None


def modelos_app():
    """(repo, prefijo, largo) de los dos modelos que usa la API: MiniLM en el semáforo y e5 en el agente."""
    from radar.nlp import embeddings, viabilidad

    return [(config.MODELOS_EMBEDDING[n], viabilidad.PREFIJO[n], embeddings.LARGOS[n]) for n in ("minilm", "e5")]


def preparar():
    """Guarda el tokenizador de cada modelo tal como lo arma transformers, y comprueba que el ONNX esté."""
    import transformers
    from transformers import AutoTokenizer

    config.DIR_MOTOR_APP.mkdir(parents=True, exist_ok=True)
    for repo, _, _ in modelos_app():
        tok = AutoTokenizer.from_pretrained(repo)
        datos = {"repo": repo, "transformers": transformers.__version__, "pad": tok.pad_token,
                 "pad_id": tok.pad_token_id, "tokenizador": tok.backend_tokenizer.to_str()}  # fmt: skip
        _ruta_tokenizador(repo).write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        log.info(f"{repo}: tokenizador guardado; ONNX en {_ruta_onnx(repo)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Motor ONNX de la app (sección 14).")
    ap.add_argument("accion", choices=("preparar",))
    ap.parse_args(argv)
    configurar("nlp-motor")
    preparar()


if __name__ == "__main__":
    main()
