"""Corpus oficial: comunicados del ENFEN y avisos del Senamhi en párrafos (definición en docs/oficial/definicion.md).

Uso: python src/oficial/corpus.py [--solo enfen|senamhi] [--sin-descarga] [--prueba]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from oficial import enfen, senamhi, validar  # noqa: E402
from oficial.comun import (DIR_OFICIAL, ClienteOficial, ahora, escribir_csv, filas_urls, guardar_gz, leer_csv,  # noqa: E402
                           leer_gz)

COL_COMUNICADOS = ["id", "tipo", "numero", "anio", "fecha_emision", "fecha_web", "vigente_desde", "vigente_hasta", "estado",
                   "magnitud_max_prevista", "magnitudes_mencionadas", "plazo", "proximo_anunciado", "titular", "slug", "url",
                   "lastmod", "sha256_pdf", "fuente_texto", "n_parrafos"]
COL_PROBABILIDADES = ["comunicado_id", "region", "periodo", "categoria", "probabilidad"]
COL_AVISOS = ["id", "anio", "numero", "b", "titulo", "tipo", "nivel", "estado", "relacion", "aviso_relacionado", "emision",
              "inicio", "fin", "duracion", "macroregiones", "metodo_macroregion", "url"]
COL_DIAS = ["aviso_id", "fecha", "mapa", "macroregion", "nivel_dia", "nivel_macroregion", "estaciones", "departamentos", "metodo"]
COL_PARRAFOS = ["id", "doc_id", "fuente", "orden", "seccion", "texto", "fecha_doc", "vigente_desde", "vigente_hasta",
                "macroregiones", "temas", "duplicado_de", "sha1"]
COL_VALIDACION = ["prueba", "criterio", "valor", "umbral", "pasa", "detalle"]


def conservar(nuevas, anteriores, ids_fallidos, clave="id"):
    """No empeorar el corpus: si un documento que ya estaba falla ahora, se conservan sus filas anteriores."""
    presentes = {f[clave] for f in nuevas}
    return nuevas + [f for f in anteriores if f[clave] in ids_fallidos and f[clave] not in presentes]


def correr_enfen(cli, descargar, alertas):
    estado = enfen.cargar_estado()
    slugs, lastmod, avisos = enfen.documentos(cli) if descargar else (list(dict.fromkeys(enfen.SEMILLAS + sorted(estado))), {}, [])
    alertas += [f"ENFEN · {a}" for a in avisos]
    fallidos = set()
    if descargar:
        for slug in slugs:
            try:
                if enfen.descargar(cli, slug, lastmod.get(slug, ""), estado):
                    alertas.append(f"ENFEN · PDF nuevo o cambiado: {slug}")
            except Exception as e:  # una descarga que falla no detiene las demás
                fallidos.add(slug)
                alertas.append(f"FALLO ENFEN · {slug}: {type(e).__name__} {e}"[:200])
        enfen.guardar_estado(estado)
    coms, probs, pars, val = enfen.construir(slugs, estado)
    for k, v in val.items():
        if "error" in v:
            alertas.append(f"FALLO ENFEN · {k}: {v['error']}")
            fallidos.add(k)
    return coms, probs, pars, val, fallidos


def correr_senamhi(cli, descargar, alertas):
    estado = senamhi.cargar_estado()
    ruta_tabla = senamhi.DIR / "tabla.html.gz"
    contenido = None
    if descargar:
        try:
            contenido = cli.traer(senamhi.BASE + "?p=aviso-meteorologico").content
            guardar_gz(ruta_tabla, contenido)
        except Exception as e:
            alertas.append(f"FALLO Senamhi · tabla de avisos: {type(e).__name__} {e}"[:200] + " (se usa la última copia)")
    if contenido is None:
        if not ruta_tabla.exists():
            raise RuntimeError("no hay tabla de avisos del Senamhi")
        contenido = leer_gz(ruta_tabla)
    tabla = senamhi.leer_tabla(contenido)
    en_tabla = {f"{f['anio']}-{f['b']}" for f in tabla}
    faltan = sorted({f["id"] for f in filas_urls() if f["medio"] == "senamhi"} - en_tabla)
    if faltan:
        alertas.append(f"Senamhi · {len(faltan)} avisos de data/urls ya no están en la tabla: {', '.join(faltan[:5])}")
    fallidos = set()
    if descargar:
        for f in tabla:
            clase = senamhi.candidato(f)
            if not clase:
                continue
            try:
                senamhi.descargar(cli, f, clase, estado)
            except Exception as e:
                fallidos.add(f"senamhi-{f['anio']}-{f['numero']:03d}")
                alertas.append(f"FALLO Senamhi · aviso {f['anio']}-{f['numero']}: {type(e).__name__} {e}"[:200])
        senamhi.guardar_estado(estado)
    avisos, dias, pars, val = senamhi.construir(tabla)
    for v in val:
        if "error" in v:
            fallidos.add(v["aviso_id"])
            alertas.append(f"FALLO Senamhi · {v['aviso_id']}: {v['error']}")
    return avisos, dias, pars, val, fallidos


def main(argv=None):
    ap = argparse.ArgumentParser(description="Construye el corpus oficial (ENFEN y Senamhi).")
    ap.add_argument("--solo", choices=["enfen", "senamhi"])
    ap.add_argument("--sin-descarga", action="store_true", help="solo vuelve a extraer desde data/raw/oficial")
    ap.add_argument("--prueba", action="store_true", help="no escribe data/oficial")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    inicio = ahora()
    cli = ClienteOficial()
    alertas, filas_val, salida, fuentes_ok = [], [], {}, 0
    ant_par = leer_csv(DIR_OFICIAL / "parrafos.csv")

    if args.solo in (None, "enfen"):
        try:
            coms, probs, pars, val, fall = correr_enfen(cli, not args.sin_descarga, alertas)
            ids_f = {c["id"] for c in leer_csv(DIR_OFICIAL / "comunicados.csv") if c["slug"] in fall}
            salida["comunicados.csv"] = (COL_COMUNICADOS, conservar(coms, leer_csv(DIR_OFICIAL / "comunicados.csv"), ids_f))
            salida["probabilidades.csv"] = (COL_PROBABILIDADES, conservar(probs, leer_csv(DIR_OFICIAL / "probabilidades.csv"), ids_f, "comunicado_id"))
            salida["parrafos_enfen"] = conservar(pars, [p for p in ant_par if p["fuente"] == "enfen"], ids_f, "doc_id")
            filas_val += validar.validar_enfen(coms, pars, val)
            fuentes_ok += 1
        except Exception as e:
            alertas.append(f"FALLO ENFEN completo: {type(e).__name__} {e}"[:200])
    if args.solo in (None, "senamhi"):
        try:
            avisos, dias, pars, val, fall = correr_senamhi(cli, not args.sin_descarga, alertas)
            salida["avisos.csv"] = (COL_AVISOS, conservar(avisos, leer_csv(DIR_OFICIAL / "avisos.csv"), fall))
            salida["aviso_dias.csv"] = (COL_DIAS, conservar(dias, leer_csv(DIR_OFICIAL / "aviso_dias.csv"), fall, "aviso_id"))
            salida["parrafos_senamhi"] = conservar(pars, [p for p in ant_par if p["fuente"] == "senamhi"], fall, "doc_id")
            filas_val += validar.validar_senamhi(avisos, dias, val)
            fuentes_ok += 1
        except Exception as e:
            alertas.append(f"FALLO Senamhi completo: {type(e).__name__} {e}"[:200])

    # párrafos: se reemplaza solo la fuente que se corrió
    pars = salida.pop("parrafos_enfen", [p for p in ant_par if p["fuente"] == "enfen"]) + \
        salida.pop("parrafos_senamhi", [p for p in ant_par if p["fuente"] == "senamhi"])
    salida["parrafos.csv"] = (COL_PARRAFOS, sorted(pars, key=lambda p: (p["fuente"], p["doc_id"], int(p["orden"]))))
    if filas_val:
        salida["validacion.csv"] = (COL_VALIDACION, filas_val)

    print(f"\nCorpus oficial {inicio.isoformat()}{' [PRUEBA]' if args.prueba else ''}")
    for nombre, (_, filas) in salida.items():
        print(f"  {nombre:20} {len(filas):5} filas")
    print("\nPruebas de viabilidad:")
    for prueba in dict.fromkeys(f["prueba"] for f in filas_val):
        grupo = [f for f in filas_val if f["prueba"] == prueba]
        resultado = "" if "informativo" in prueba else ("PASA" if all(f["pasa"] for f in grupo) else "NO PASA")
        print(f"  {prueba} {resultado}")
        for f in grupo:
            marca = "·" if "informativo" in prueba else ("ok" if f["pasa"] else "NO")
            print(f"    [{marca:2}] {f['criterio']}: {f['valor']} (umbral {f['umbral']})" + (f" — {f['detalle'][:120]}" if f["detalle"] else ""))
    print("\n" + ("\n".join("- " + a for a in alertas) if alertas else "Sin alertas."))
    print(f"\nDuración: {(ahora() - inicio).total_seconds() / 60:.1f} min")

    if not args.prueba and fuentes_ok:
        for nombre, (cols, filas) in salida.items():
            escribir_csv(DIR_OFICIAL / nombre, cols, filas)
        print("Escrito en data/oficial/")
    return 0 if fuentes_ok else 1


if __name__ == "__main__":
    sys.exit(main())
