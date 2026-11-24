"""Motor de la app sin torch (docs/app/definicion.md, sección 14): ONNX en float32 con la librería tokenizers.
Memoria (sección 16): los pesos van en un archivo aparte que onnxruntime lee del disco sin copiarlos, y los dos modelos
comparten el tokenizador.

python -m radar.nlp.motor preparar   ->  guarda el tokenizador y los pesos aparte de cada modelo de la app (una vez,
                                            con transformers)

El tokenizador se guarda tal como lo arma transformers (no el tokenizer.json del repositorio: con e5 difiere en los
espacios repetidos), así los tokens son los mismos que con torch. Los archivos ONNX quedan en la caché de Hugging
Face. Si falta alguno, `para_app` devuelve None y quien llama usa torch como antes.
"""

import argparse
import functools
import json
import logging
import threading
from pathlib import Path

import numpy as np

from radar import config
from radar.comun.archivos import guardar_json, leer_json, sha256
from radar.comun.registro import configurar

log = logging.getLogger(__name__)

ARCHIVO_PESOS, ARCHIVO_ORIGEN = "pesos.bin", "origen.json"
ARCHIVO_ONNX = "onnx/model.onnx"  # float32; los cuantizados dan otros vectores (sección 14.2)


def _ruta_tokenizador(repo):
    return config.DIR_MOTOR_APP / (repo.replace("/", "--") + ".json")


def _ruta_onnx(repo):
    from huggingface_hub import hf_hub_download

    return hf_hub_download(repo, ARCHIVO_ONNX, local_files_only=True)


def _dir_pesos(repo):
    return config.DIR_MOTOR_APP / (repo.replace("/", "--") + "-pesos")


def _origen(ruta):
    """Huella del ONNX de origen: la revisión del repositorio (carpeta de la caché) y el tamaño. No se relee el archivo
    entero en cada arranque."""
    ruta = Path(ruta)
    return {"revision": ruta.parent.parent.name, "bytes": ruta.stat().st_size}


def _ruta_pesos_aparte(repo):
    """El modelo con los pesos aparte, o None si falta, está incompleto o salió de otro ONNX."""
    carpeta = _dir_pesos(repo)
    marca = leer_json(carpeta / ARCHIVO_ORIGEN)
    modelo, pesos = carpeta / "modelo.onnx", carpeta / ARCHIVO_PESOS
    if not marca or not modelo.exists() or not pesos.exists():
        return None
    if marca["origen"] != _origen(_ruta_onnx(repo)) or marca["bytes_pesos"] != pesos.stat().st_size:
        log.warning("%s: los pesos aparte no corresponden al ONNX actual: se usa el ONNX completo", repo)
        return None
    return modelo


def separar_pesos(repo):
    """Escribe el mismo modelo con los pesos aparte (lo hace onnxruntime). La marca se escribe al final: un corte a
    medias deja a la app con el ONNX completo."""
    import onnxruntime as ort

    carpeta = _dir_pesos(repo)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / ARCHIVO_ORIGEN).unlink(missing_ok=True)
    opciones = ort.SessionOptions()
    opciones.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL  # el mismo grafo
    opciones.optimized_model_filepath = str(carpeta / "modelo.onnx")
    opciones.add_session_config_entry("session.optimized_model_external_initializers_file_name", ARCHIVO_PESOS)
    opciones.add_session_config_entry("session.optimized_model_external_initializers_min_size_in_bytes", "1024")
    ort.InferenceSession(_ruta_onnx(repo), opciones, providers=["CPUExecutionProvider"])
    marca = {"origen": _origen(_ruta_onnx(repo)), "bytes_pesos": (carpeta / ARCHIVO_PESOS).stat().st_size}
    guardar_json(carpeta / ARCHIVO_ORIGEN, marca)


@functools.cache
def _huella_contenido(ruta, _modificado):
    """Lo que decide los tokens, para saber si dos modelos pueden compartir tokenizador. No cuentan el truncamiento ni
    el relleno (los pone `lote`) ni el `lstrip` de <mask>: el separador ya quita esos espacios (sección 16.5)."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    t = json.loads(datos["tokenizador"])
    fijos = {k: v for k, v in t.items() if k not in ("truncation", "padding", "added_tokens")}
    especiales = [
        {k: v for k, v in e.items() if not (k == "lstrip" and e["content"] == "<mask>")} for e in t["added_tokens"]
    ]
    return sha256(json.dumps([fijos, especiales, datos["pad"], datos["pad_id"]], sort_keys=True).encode("utf-8"))


_compartidos = {}


def tokenizador(repo):
    """El tokenizador del modelo; si otro modelo ya cargó uno con el mismo contenido, es ese."""
    ruta = _ruta_tokenizador(repo)
    clave = _huella_contenido(ruta, ruta.stat().st_mtime_ns)
    if clave not in _compartidos:
        _compartidos[clave] = Tokenizador(ruta)
    return _compartidos[clave]


class Tokenizador:
    """Lo que Candidato y embeddings.Modelo piden a un tokenizador de transformers: tok(textos)["input_ids"]."""

    def __init__(self, ruta):
        from tokenizers import Tokenizer

        datos = json.loads(ruta.read_text(encoding="utf-8"))
        self.base = Tokenizer.from_str(datos["tokenizador"])
        self.base.no_truncation()
        self.base.no_padding()
        self.pad_id, self.pad = datos["pad_id"], datos["pad"]
        self.candado = threading.Lock()  # `lote` cambia el truncamiento y el relleno mientras tokeniza

    def __call__(self, textos, add_special_tokens=True, **_):
        unico = isinstance(textos, str)
        with self.candado:
            cod = self.base.encode_batch([textos] if unico else list(textos), add_special_tokens=add_special_tokens)
        ids = [c.ids for c in cod]
        return {"input_ids": ids[0] if unico else ids}

    def lote(self, textos, largo):
        """(ids, máscara) con truncamiento y relleno, como transformers con truncation=True y padding=True."""
        with self.candado:
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
        self.tok = self.tokenizer = tokenizador(repo)
        self.max_seq_length = largo
        aparte = _ruta_pesos_aparte(repo)
        self.pesos_aparte = aparte is not None
        self.sesion = ort.InferenceSession(str(aparte or _ruta_onnx(repo)), providers=["CPUExecutionProvider"])
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
    """Guarda el tokenizador de cada modelo tal como lo arma transformers y separa los pesos del ONNX."""
    import transformers
    from transformers import AutoTokenizer

    config.DIR_MOTOR_APP.mkdir(parents=True, exist_ok=True)
    for repo, _, _ in modelos_app():
        tok = AutoTokenizer.from_pretrained(repo)
        datos = {"repo": repo, "transformers": transformers.__version__, "pad": tok.pad_token,
                 "pad_id": tok.pad_token_id, "tokenizador": tok.backend_tokenizer.to_str()}  # fmt: skip
        _ruta_tokenizador(repo).write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        separar_pesos(repo)
        log.info(f"{repo}: tokenizador y pesos aparte guardados; ONNX en {_ruta_onnx(repo)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Motor ONNX de la app (sección 14).")
    ap.add_argument("accion", choices=("preparar",))
    ap.parse_args(argv)
    configurar("nlp-motor")
    preparar()


if __name__ == "__main__":
    main()
