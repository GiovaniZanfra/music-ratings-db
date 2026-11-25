# playlists_creation

Sorteios semanais, playlists curadas e análises em cima dos charts do RYM (top 40 por ano, 1970–2026).

- `CLAUDE.md`: as instruções completas (regras do sorteio, playlists, análises, persistência). É o que o agente lê.
- `files/`: os CSVs processados (geral e Brasil), com gêneros e subgêneros em one-hot.
- `agent/scripts/sortear.py`: o sorteio. Exemplo: `python3 agent/scripts/sortear.py novo --geral 15 --brasil 5`.
- `agent/scripts/avaliados.py`: cruza os álbuns com nota na planilha `music_db_ratings` com o RYM e grava `agent/sorteios/avaliados.csv`, que o sorteio usa com `--excluir-avaliados`. Isso é opcional: sem a flag, os álbuns com nota continuam no sorteio. Exemplo: `python3 agent/scripts/avaliados.py music_db_ratings.xlsx`.
- `agent/sorteios/`: cada sorteio (`estado.json` + `sorteio.md`), o `historico.csv` com todos os álbuns que já saíram e o `avaliados.csv`.
- `agent/playlists/`, `agent/analises/`, `agent/processamento/`: playlists curadas, análises e relatórios de processamento.

Os HTMLs originais dos charts (`htmls/`) ficam fora do repo: as páginas salvas trazem dados da sessão do RYM.

Rode os comandos de dentro desta pasta. Precisa de pandas (`pip install pandas`).
