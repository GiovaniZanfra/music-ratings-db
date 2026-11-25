#!/usr/bin/env python3
"""Cruza os álbuns com nota na planilha music_db_ratings (aba Albums) com os CSVs do RYM.

Uso (a partir de playlists_creation/):
  python3 agent/scripts/avaliados.py <music_db_ratings.xlsx>

A planilha vem do Drive (export .xlsx). "Com nota" = FinalScore preenchido na aba Albums.
Grava agent/sorteios/avaliados.csv (uma linha por álbum do RYM que casou), que o
sortear.py usa com --excluir-avaliados. Imprime também os casos em dúvida pra conferir.

Como casa (nomes normalizados: sem acento, pontuação e sufixos de remaster/deluxe/edição):
- título igual + artista com alguma palavra em comum. O RYM usa nome de exibição
  ("Marina", "Eno", "D2", "Tim Maia Racional"), por isso não exige o artista inteiro;
- título com grafia parecida só quando o artista bate de verdade, nunca confundindo
  continuação (Clube da esquina 2, Saturation III, Vol. II);
- ALIAS_ARTISTA e ALIAS_ALBUM pros casos em que o nome muda de língua ou de forma.
Quando o mesmo álbum aparece em mais de um ano no RYM (homônimo/regravação), todos saem:
melhor sobrar do que repetir. O ano do Last.fm não desempata (Twin Fantasy vem como 2011,
mas o "Twin Fantasy" do Spotify é o de 2018).
"""
import csv
import difflib
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sortear import ROOT, carregar, norm  # noqa: E402

SAIDA = ROOT / "agent/sorteios/avaliados.csv"
# sufixos de versão que o Last.fm/Spotify colam no título e o RYM não usa
VERSAO = (r"remaster|deluxe|edition|edicao|version|versao|expanded|anniversary|reissue|"
          r"bonus|extended|comemorativa|slidepack|mono|stereo|original album mix|\d{4}")
LIMIAR = 0.88
PALAVRAS_VAZIAS = {"the", "and", "de", "do", "da", "dos", "das", "e", "of", "his", "her",
                   "el", "la", "los", "las", "y", "band", "a", "o", "os", "as"}
# planilha (Last.fm) -> RYM, já normalizados com compacta()
ALIAS_ARTISTA = {"public image ltd": "pil"}
ALIAS_ALBUM = {
    ("kraftwerk", "computer world"): "computerwelt",
    ("boris", "akuma no uta"): "あくまのうた",
    ("einsturzende neubauten", "halber mensch"): "½ mensch",
    ("gilberto gil", "gil e jorge"): "ogum xango",
    ("itamar assumpcao", "beleleu e banda isca de policia"): "beleleu leleu eu",
}


def compacta(s):
    s = norm(s).replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s½]", " ", s)).strip()


def limpa_album(s):
    s = norm(s)
    s = re.sub(r"[\(\[][^\)\]]*(" + VERSAO + r")[^\)\]]*[\)\]]", " ", s)
    s = re.sub(r"\s-\s.*(" + VERSAO + r"|\bep\b).*$", " ", s)
    s = re.sub(r"\s-\s*ep$", " ", s)
    return compacta(s)


def partes_artista(s):
    """'Fela Kuti & The Africa '70' -> {'fela kuti and the africa 70', 'fela kuti', 'the africa 70', ...}"""
    s = norm(s)
    out = {compacta(s)}
    out |= {compacta(p) for p in re.split(r"\s*(?:/|&|,|\band\b|\be\b)\s*", s) if p.strip()}
    out |= {re.sub(r"^the ", "", p) for p in out}
    out |= {ALIAS_ARTISTA[p] for p in out if p in ALIAS_ARTISTA}
    return {p for p in out if p}


def palavras(s):
    return {w for p in partes_artista(s) for w in p.split()} - PALAVRAS_VAZIAS


ROMANOS = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}


def numeros(s):
    return {int(t) if t.isdigit() else ROMANOS[t] for t in s.split() if t.isdigit() or t in ROMANOS}


def parecido(rym, planilha):
    """Grafia parecida, sem confundir continuação: se o RYM tem um número que a planilha
    não tem (Clube da esquina 2, Saturation III, Vol. II), não casa."""
    if not numeros(rym) <= numeros(planilha):
        return False
    if len(rym.split()) >= 3 and planilha.startswith(rym + " "):  # "..., Vol. 1 & 2" no fim
        return True
    return difflib.SequenceMatcher(None, rym, planilha).ratio() >= LIMIAR


def formas_planilha(artista, album):
    alb = limpa_album(album)
    formas = {alb, compacta(album), compacta(f"{artista} {alb}")}  # "Vol. 4" -> "Black Sabbath Vol. 4"
    for p in partes_artista(artista):
        if (p, alb) in ALIAS_ALBUM:
            formas.add(ALIAS_ALBUM[(p, alb)])
    return alb, formas


def formas_rym(album):
    # "Luar (A gente precisa ver o luar)" também vale como "Luar"
    return {compacta(album), compacta(re.sub(r"\s*\([^)]*\)", "", album))}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    planilha = pd.read_excel(sys.argv[1], sheet_name="Albums")
    nota = planilha[planilha.FinalScore.notna()]

    rym = []
    for fonte, df in carregar().items():
        for r in df[["chave", "year", "artist", "album"]].itertuples(index=False):
            rym.append((fonte, r, partes_artista(r.artist), palavras(r.artist),
                        formas_rym(r.album), compacta(r.album)))

    linhas, duvidas, sem_par = [], [], []
    for s in nota.itertuples(index=False):
        alb, formas = formas_planilha(s.ArtistName, s.AlbumName)
        partes, pals = partes_artista(s.ArtistName), palavras(s.ArtistName)
        achou = [(f, r, "exato") for f, r, ra_partes, ra_pals, ra_formas, _ in rym
                 if (partes & ra_partes or pals & ra_pals) and formas & ra_formas]
        if not achou:  # grafia parecida só com o artista batendo de verdade
            achou = [(f, r, "parecido") for f, r, ra_partes, _, _, ra in rym
                     if partes & ra_partes and parecido(ra, alb)]
        if not achou:
            sem_par.append(s)
            continue
        anos = sorted({int(r.year) for _, r, _ in achou})
        if len(anos) > 1:
            duvidas.append(f"vários anos: {s.ArtistName} – {s.AlbumName} → {anos}, todos excluídos")
        for fonte, r, tipo in achou:
            linhas.append({
                "chave": r.chave, "fonte": fonte, "year": int(r.year), "artist": r.artist,
                "album": r.album, "planilha_artista": s.ArtistName, "planilha_album": s.AlbumName,
                "casamento": tipo,
            })
        for chave in dict.fromkeys(r.chave for _, r, tipo in achou
                                   if tipo == "parecido" or not (partes & partes_artista(r.artist))):
            r = next(r for _, r, _ in achou if r.chave == chave)
            duvidas.append(f"nome diferente: {s.ArtistName} – {s.AlbumName}  ≈  {r.artist} – {r.album} ({r.year})")

    # mesmo álbum pode estar no geral e no Brasil: uma linha por (fonte, chave)
    vistos, unicas = set(), []
    for l in linhas:
        if (l["fonte"], l["chave"]) not in vistos:
            vistos.add((l["fonte"], l["chave"]))
            unicas.append(l)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(unicas[0]))
        w.writeheader()
        w.writerows(unicas)

    por_fonte = pd.Series([l["fonte"] for l in unicas]).value_counts().to_dict()
    print(f"álbuns com nota na planilha: {len(nota)}")
    print(f"casaram com o RYM: {len(nota) - len(sem_par)} → {len(unicas)} linhas {por_fonte}")
    print(f"sem par no RYM (fora do top 40 do ano, de antes de 1970, ou grafia muito diferente): {len(sem_par)}")
    if duvidas:
        print("\nconferir:")
        print("\n".join(f"  {d}" for d in duvidas))
    print(f"\n[salvo em {SAIDA.relative_to(ROOT)}]")


if __name__ == "__main__":
    main()
