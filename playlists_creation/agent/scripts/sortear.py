#!/usr/bin/env python3
"""Sorteio semanal de álbuns (RYM top 40/ano) com estado persistido.

Uso (a partir da raiz do projeto):
  python agent/scripts/sortear.py novo [--geral 15] [--brasil 5] [--top-geral K] [--top-brasil K] [--excluir-anteriores] [--excluir-avaliados]
  python agent/scripts/sortear.py tirar "trecho do artista ou álbum"   # remove e sorteia substituto
  python agent/scripts/sortear.py trocar                               # troca o último que entrou
  python agent/scripts/sortear.py mostrar

tirar/trocar/mostrar agem no sorteio mais recente (ou --id).
novo/tirar/trocar aceitam --sem <gênero> (ex.: --sem metal): exclui por gênero primário daí em diante.
--excluir-avaliados tira os álbuns que já têm nota na planilha music_db_ratings
(lista em agent/sorteios/avaliados.csv, gerada por agent/scripts/avaliados.py).
Aleatoriedade: secrets.SystemRandom (os.urandom), sem seed.
Cada comando grava <dir>/<id>/estado.json + sorteio.md e regenera <dir>/historico.csv.
"""
import argparse
import csv
import json
import re
import secrets
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ARQUIVOS = {
    "geral": ROOT / "files/rym_top40_1970_2026_no_old_classical.csv",
    "brasil": ROOT / "files/rym_top40_1970_2026_brazil.csv",
}
FONTES = ("geral", "brasil")
# --sem <termo> exclui por gênero primário; famílias que não se resolvem por substring do nome
FAMILIAS = {"metal": r"metal|deathcore|djent|grind|crossover_thrash"}
AVALIADOS = ROOT / "agent/sorteios/avaliados.csv"
RNG = secrets.SystemRandom()
METODO = "secrets.SystemRandom (entropia do SO via os.urandom, sem seed)"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().casefold()


def chave(year, artist, album):
    # artista+álbum se repete em anos diferentes (homônimos, regravações), então o ano entra na chave
    return f"{int(year)}|{norm(artist)}|{norm(album)}"


def carregar():
    dfs = {}
    for fonte, path in ARQUIVOS.items():
        df = pd.read_csv(path, encoding="utf-8-sig")
        df["chave"] = [chave(*t) for t in zip(df.year, df.artist, df.album)]
        # homônimos no mesmo ano são álbuns distintos (Paulinho da Viola tem dois LPs homônimos em 1971)
        n = df.groupby("chave").cumcount()
        df["chave"] = df["chave"].where(n == 0, df["chave"] + "|" + (n + 1).astype(str))
        dfs[fonte] = df
    return dfs


def generos(row):
    nomes = []
    for c in row.index:
        if c.startswith("genre_") and row[c] == 1:
            nome = re.sub(r"(^|_)r_b($|_)", r"\1r&b\2", c[len("genre_"):])
            nomes.append(nome.replace("_", " "))
    return ", ".join(nomes)


def registro(row, fonte, slot, entrada):
    return {
        "slot": slot,
        "entrada": entrada,
        "fonte": fonte,
        "chave": row["chave"],
        "year": int(row["year"]),
        "position": int(row["position"]),
        "rym_position": int(row["rym_position"]),
        "artist": row["artist"],
        "album": row["album"],
        "rating": float(row["rating"]),
        "n_ratings": int(row["n_ratings"]),
        "generos": generos(row),
    }


def estados(base):
    out = []
    for p in sorted(base.glob("*/estado.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def anteriores(base, sorteio_id):
    """chave -> ids dos outros sorteios em que o álbum saiu (só a lista final, sem removidos)."""
    m = defaultdict(list)
    for e in estados(base):
        if e["id"] != sorteio_id:
            for p in e["escolhidos"]:
                m[p["chave"]].append(e["id"])
    return m


def avaliados():
    """chaves do RYM que já têm nota na planilha (ver agent/scripts/avaliados.py)."""
    if not AVALIADOS.exists():
        sys.exit(f"{AVALIADOS.relative_to(ROOT)} não existe: rode agent/scripts/avaliados.py antes")
    with open(AVALIADOS, encoding="utf-8") as f:
        return {l["chave"] for l in csv.DictReader(f)}


def colunas_excluidas(df, termos):
    pad = "|".join(FAMILIAS.get(t, re.sub(r"[^a-z0-9]+", "_", norm(t))) for t in termos)
    return [c for c in df.columns if c.startswith("genre_") and re.search(pad, c[len("genre_"):])]


def pool(dfs, estado, fonte, bloqueio_anterior):
    df = dfs[fonte]
    top = estado["regras"][fonte]["top"]
    if top:
        df = df[df.position <= top]
    sem = estado["regras"].get("sem", [])
    if sem:
        df = df[df[colunas_excluidas(df, sem)].sum(axis=1) == 0]
    bloqueadas = {p["chave"] for p in estado["escolhidos"] + estado["removidos"]}
    if estado["regras"]["excluir_anteriores"]:
        bloqueadas |= bloqueio_anterior
    if estado["regras"].get("excluir_avaliados"):
        bloqueadas |= avaliados()
    return df[~df.chave.isin(bloqueadas)]


def descrever_regra(regras, fonte):
    r = regras[fonte]
    return f"{fonte}: {r['n']} álbuns, " + (f"top {r['top']} do ano" if r["top"] else "sem filtro")


def coincidencias(estado, dfs, ant):
    notas = []
    artistas = Counter(norm(p["artist"]) for p in estado["escolhidos"])
    for p in estado["escolhidos"]:
        if artistas[norm(p["artist"])] > 1:
            notas.append(f"artista repetido: {p['artist']}")
            artistas[norm(p["artist"])] = 0
    br = set(dfs["brasil"].artist.map(norm))
    for p in estado["escolhidos"]:
        if p["fonte"] == "geral" and norm(p["artist"]) in br:
            notas.append(f"brasileiro pelo geral: {p['artist']} – {p['album']}")
        if p["chave"] in ant:
            notas.append(f"já saiu em {', '.join(ant[p['chave']])}: {p['artist']} – {p['album']}")
    return notas


def render(estado, dfs, ant):
    regras = estado["regras"]
    linhas = [
        f"# Sorteio {estado['id']}",
        "",
        f"- Método: {estado['metodo']}",
        "- Regras: " + "; ".join(descrever_regra(regras, f) for f in FONTES if regras[f]["n"])
        + ("; excluindo álbuns de sorteios anteriores" if regras["excluir_anteriores"] else "")
        + ("; excluindo álbuns que já têm nota na planilha" if regras.get("excluir_avaliados") else "")
        + (f"; sem gênero primário: {', '.join(regras['sem'])}" if regras.get("sem") else ""),
        "- Elegíveis no momento do sorteio: "
        + ", ".join(f"{f} {estado['elegiveis'][f]}" for f in FONTES if f in estado["elegiveis"]),
        "",
        "| # | Fonte | Ano | Pos | Artista – Álbum | Rating | Gêneros |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in estado["escolhidos"]:
        linhas.append(
            f"| {p['slot']} | {p['fonte']} | {p['year']} | {p['position']} | "
            f"{p['artist']} – {p['album']} | {p['rating']:.2f} | {p['generos']} |"
        )
    linhas += ["", "```text"]
    linhas += [f"{p['artist']} - {p['album']} ({p['year']})" for p in estado["escolhidos"]]
    linhas += ["```", ""]
    notas = coincidencias(estado, dfs, ant)
    linhas.append("**Coincidências:** " + ("; ".join(notas) if notas else "nenhuma"))
    if estado["removidos"]:
        linhas += ["", "**Removidos (não voltam):**"]
        linhas += [f"- {e}" for e in estado["eventos"] if e.startswith(("tirar", "trocar"))]
    return "\n".join(linhas) + "\n"


def salvar(base, estado, dfs):
    pasta = base / estado["id"]
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    md = render(estado, dfs, anteriores(base, estado["id"]))
    (pasta / "sorteio.md").write_text(md, encoding="utf-8")
    campos = ["sorteio", "fonte", "slot", "year", "position", "artist", "album", "rating", "n_ratings"]
    with open(base / "historico.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for e in estados(base):
            for p in e["escolhidos"]:
                w.writerow({"sorteio": e["id"], **p})
    print(md)
    print(f"[salvo em {pasta.relative_to(ROOT) if pasta.is_relative_to(ROOT) else pasta}]")


def carregar_estado(base, sorteio_id):
    todos = estados(base)
    if not todos:
        sys.exit("nenhum sorteio salvo ainda")
    if sorteio_id:
        achados = [e for e in todos if e["id"] == sorteio_id]
        if not achados:
            sys.exit(f"sorteio {sorteio_id} não encontrado")
        return achados[0]
    return max(todos, key=lambda e: e["criado"])


def novo_id(base):
    hoje = date.today().isoformat()
    sid, i = hoje, 2
    while (base / sid).exists():
        sid, i = f"{hoje}_{i}", i + 1
    return sid


def cmd_novo(args, base, dfs):
    sid = novo_id(base)
    estado = {
        "id": sid,
        "criado": datetime.now().isoformat(timespec="seconds"),
        "metodo": METODO,
        "regras": {
            "geral": {"n": args.geral, "top": args.top_geral},
            "brasil": {"n": args.brasil, "top": args.top_brasil},
            "excluir_anteriores": args.excluir_anteriores,
            "excluir_avaliados": args.excluir_avaliados,
            "sem": args.sem,
        },
        "elegiveis": {},
        "escolhidos": [],
        "removidos": [],
        "eventos": [],
    }
    bloqueio = set(anteriores(base, sid))
    slot = 0
    for fonte in FONTES:  # geral primeiro; o Brasil já exclui o que saiu no geral
        n = estado["regras"][fonte]["n"]
        if not n:
            continue
        p = pool(dfs, estado, fonte, bloqueio)
        estado["elegiveis"][fonte] = len(p)
        if len(p) < n:
            sys.exit(f"{fonte}: só {len(p)} elegíveis para {n} pedidos")
        for i in RNG.sample(list(p.index), n):
            slot += 1
            estado["escolhidos"].append(registro(p.loc[i], fonte, slot, slot))
    estado["eventos"].append("novo: " + "; ".join(descrever_regra(estado["regras"], f) for f in FONTES))
    salvar(base, estado, dfs)


def substituir(base, estado, dfs, alvo, verbo):
    fonte = alvo["fonte"]
    idx = estado["escolhidos"].index(alvo)
    estado["escolhidos"].pop(idx)
    estado["removidos"].append(alvo)
    p = pool(dfs, estado, fonte, set(anteriores(base, estado["id"])))
    if p.empty:
        sys.exit(f"{fonte}: sem elegíveis para substituir")
    entrada = max([x["entrada"] for x in estado["escolhidos"] + estado["removidos"]]) + 1
    novo = registro(p.loc[RNG.choice(list(p.index))], fonte, alvo["slot"], entrada)
    estado["escolhidos"].insert(idx, novo)
    estado["eventos"].append(
        f"{verbo}: {alvo['artist']} – {alvo['album']} ({alvo['year']}) → "
        f"{novo['artist']} – {novo['album']} ({novo['year']}) [{fonte}, {len(p)} elegíveis]"
    )
    salvar(base, estado, dfs)


def adicionar_sem(estado, termos):
    """Exclusão de gênero pedida no meio do sorteio vale daqui pra frente (não mexe no que já saiu)."""
    sem = estado["regras"].setdefault("sem", [])
    for t in termos:
        if t not in sem:
            sem.append(t)
            estado["eventos"].append(f"regra: sem gênero primário {t} a partir daqui")


def cmd_tirar(args, base, dfs):
    estado = carregar_estado(base, args.id)
    adicionar_sem(estado, args.sem)
    q = norm(args.consulta)
    achados = [p for p in estado["escolhidos"] if q in norm(f"{p['artist']} - {p['album']}")]
    if len(achados) != 1:
        opcoes = "\n".join(f"  {p['artist']} - {p['album']} ({p['year']})" for p in achados)
        sys.exit(f"'{args.consulta}' casou com {len(achados)} álbuns" + (f":\n{opcoes}" if achados else ""))
    substituir(base, estado, dfs, achados[0], "tirar")


def cmd_trocar(args, base, dfs):
    estado = carregar_estado(base, args.id)
    adicionar_sem(estado, args.sem)
    ultimo = max(estado["escolhidos"], key=lambda p: p["entrada"])
    substituir(base, estado, dfs, ultimo, "trocar")


def cmd_mostrar(args, base, dfs):
    estado = carregar_estado(base, args.id)
    print(render(estado, dfs, anteriores(base, estado["id"])))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=ROOT / "agent/sorteios", help="pasta dos sorteios")
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("novo")
    n.add_argument("--geral", type=int, default=15)
    n.add_argument("--brasil", type=int, default=5)
    n.add_argument("--top-geral", type=int)
    n.add_argument("--top-brasil", type=int)
    n.add_argument("--excluir-anteriores", action="store_true")
    n.add_argument("--excluir-avaliados", action="store_true",
                   help="tira os álbuns com nota na planilha (agent/sorteios/avaliados.csv)")

    t = sub.add_parser("tirar")
    t.add_argument("consulta")
    tr = sub.add_parser("trocar")
    m = sub.add_parser("mostrar")
    for sp in (t, tr, m):
        sp.add_argument("--id")
    for sp in (n, t, tr):
        sp.add_argument("--sem", action="append", default=[], help="exclui gênero primário (ex.: metal)")

    args = ap.parse_args()
    args.dir.mkdir(parents=True, exist_ok=True)
    dfs = carregar()
    {"novo": cmd_novo, "tirar": cmd_tirar, "trocar": cmd_trocar, "mostrar": cmd_mostrar}[args.cmd](args, args.dir, dfs)


if __name__ == "__main__":
    main()
