# RYM playlists

Sorteios semanais, playlists curadas e análises em cima de charts do RYM (top 40 por ano, 1970–2026).

## Arquivos

- `files/rym_top40_1970_2026_no_old_classical.csv`: **geral**, sem clássico antigo (2183 linhas, 478 `genre_*`, 768 `subgenre_*`). No Drive: `rym_top40_1970_2026_no_old_classical`.
- `files/rym_top40_1970_2026_brazil.csv`: **Brasil**, mesmo schema, só artistas brasileiros (2249 linhas, 410 `genre_*`, 612 `subgenre_*`).
- `htmls/rym htmls/` e `htmls/rym html brazil/`: HTMLs originais dos charts (57 anos cada).
- Colunas: `year, position, rym_position, artist, album, rating, n_ratings`, depois `genre_*` (gêneros primários, OHE) e `subgenre_*` (secundários, OHE). `position` é a posição renumerada depois do filtro, e `rym_position` é a posição original do chart.
- Os CSVs têm BOM, então leia com `encoding="utf-8-sig"`.
- A identidade de um álbum é **(ano, artista, álbum)**, nunca só artista+álbum. Tem homônimo e regravação em anos diferentes (Cartola 1974/1976, Twin Fantasy 2011/2018, Peter Gabriel 1980/1982) e até no mesmo ano (Paulinho da Viola 1971 tem dois LPs homônimos, posições 5 e 28 no Brasil).
- Python: `python3` do miniconda, com pandas 2.2. O `bs4` não está instalado; antes de processar HTML, rode `pip install beautifulsoup4 lxml`.

## Persistência

Tudo o que for gerado fica salvo em `agent/` **antes** de responder. No fim da resposta, diga o caminho do arquivo.

- **Sorteios**: sempre pelo script, nunca à mão:
  - `python3 agent/scripts/sortear.py novo [--geral 15] [--brasil 5] [--top-geral K] [--top-brasil K] [--excluir-anteriores]`
  - `python3 agent/scripts/sortear.py tirar "trecho do artista ou álbum"`, `... trocar` e `... mostrar` agem no sorteio mais recente (ou no de `--id`).
  - `--sem <gênero>` (em `novo`, `tirar` e `trocar`) exclui pelo gênero primário dali em diante e fica gravado na regra do sorteio. `--sem metal` pega tudo com "metal" no nome, mais grindcore, deathgrind, deathcore, djent e crossover thrash. Metal que aparece só como gênero secundário continua elegível.
  - Ele grava `agent/sorteios/<AAAA-MM-DD>/estado.json` + `sorteio.md` e regenera `agent/sorteios/historico.csv` (todos os álbuns que já saíram). Esse histórico é a fonte pra "álbum de lista anterior" e pra "excluir anteriores".
  - A saída já traz o método, o número de elegíveis, a tabela, o bloco pra copiar e as coincidências. Repasse isso, sem mexer no resultado.
- **Playlists curadas**: `agent/playlists/AAAA-MM-DD_<slug>.md`, com critério, restrições, lista (tabela + bloco pra copiar) e o que ficou de fora. Para checar "álbum de lista anterior", olhe também essa pasta.
- **Análises, EDA, pitches e buscas "tem X?"**: `agent/analises/AAAA-MM-DD_<slug>.md`. Arquivos auxiliares (csv, png, o `.py` que gerou números não triviais) levam o mesmo prefixo, pra dar pra refazer.
- **Dados novos (zip de HTML)**: o CSV processado vai em `files/`, com o mesmo padrão de nome dos atuais. O relatório (o que foi removido, os casos em dúvida, as contagens) vai em `agent/processamento/AAAA-MM-DD_<slug>.md`, e o extrator em `agent/scripts/`. Suba o CSV no Drive pelo conector do Google Drive. Se falhar, diga isso e deixe o CSV local.
- Código reaproveitável vai em `agent/scripts/`.

## Sorteio semanal

1. O padrão é 20 álbuns: 15 do geral e 5 do Brasil. Às vezes são 20 só do geral (`--geral 20 --brasil 0`).
2. Tem que ser aleatório de verdade: aleatoriedade do sistema, sem seed fixa e sem "balancear" nada. Diga qual método usou e quantos álbuns eram elegíveis.
3. Só aplique filtro de posição quando pedido, por exemplo "top 10 do ano" no geral e "top 5" no Brasil. "Sem filtro" quer dizer o arquivo inteiro.
4. Não repita álbum entre geral e Brasil.
5. Não exclua álbuns de sorteios anteriores, a menos que peçam.
6. "Tira X": remova e sorteie um substituto do mesmo pool e com a mesma regra. O removido não volta. "Troca" quer dizer trocar o último que entrou.
7. Entregue sempre: uma tabela curta (ano, posição, artista – álbum, rating, gêneros) e depois a lista final completa num bloco de código, no formato `Artista - Álbum (Ano)`.
8. Comente coincidências em uma linha (artista repetido, brasileiro que saiu pelo geral, álbum de lista anterior), sem mexer no resultado.

## Playlist curada (quando não é sorteio)

- Diversidade de gênero, década, nota, popularidade e importância contextual.
- Siga as restrições de ano que forem dadas ("5 anos diferentes", "de 2000 pra frente").
- Diga com honestidade o que ficou de fora por causa da restrição.

## Análises

- EDA / curiosidades por álbum:
  - posição no ano
  - posição "Ever" no dataset, por rating com `n_ratings` de desempate
  - ranking dentro de cada gênero, no formato posição/total
  - percentil de popularidade
  - #1 do ano
  - outros álbuns do mesmo artista
  - vizinhos com tags parecidas, por Jaccard em genre+subgenre
  - primeiro ano em que o gênero aparece
  - padrões da lista toda
- Avise quando a métrica é calculada no dataset e não é o ranking oficial do RYM.
- Aponte falhas do dataset que aparecerem: nomes duplicados, gênero com 1 álbum só, notas recentes ainda instáveis (poucos `n_ratings`).
- Pitch por álbum: cena, gêneros e subgêneros, contexto histórico e por onde começar a ouvir.
- "Tem X no arquivo?": busque por artista e por álbum, sem acento e sem diferenciar maiúscula, incluindo grafias alternativas. Se não tiver, explique o motivo com dados (nota de corte do ano, formato EP etc.). Pesquise na web só se pedirem.

## Processar dados novos

- Zip de HTMLs do RYM: extraia, faça o OHE no mesmo schema e salve igual ao arquivo geral (ver Persistência).
- Filtre o que obviamente não pertence ao recorte, como artista estrangeiro no arquivo do Brasil. Liste o que foi removido e os casos que ficaram em dúvida.

## Estilo

- Português informal, direto e conciso.
- Seja honesto nos trade-offs e nas limitações, por exemplo quando não deu pra salvar no Drive ou quando um site bloqueou a leitura.
- Não invente fato. Quando não souber, diga.
