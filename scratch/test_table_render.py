import os
import sys

sys.path.insert(0, os.path.abspath("generartabla"))
from app import _ranking_html, _screenshot_html

rows = [
    {
        "pos": 1,
        "userfullname": "UTP - CodeDeGrace",
        "university": "Universidad Tecnológica de Pereira",
        "country": "CO",
        "problemas_resueltos": 11,
        "points": 1462
    },
    {
        "pos": 2,
        "userfullname": "UN ALL IN",
        "university": "UNAL Bogota",
        "country": "CO",
        "problemas_resueltos": 10,
        "points": 967
    },
    {
        "pos": 3,
        "userfullname": "SQLazo \U0001F911",
        "university": "Icesi",
        "country": "CO",
        "problemas_resueltos": 10,
        "points": 1125
    },
    {
        "pos": 19,
        "userfullname": "UNIVALLE EN RPC \U0001F60E\U0001F4C8top1",
        "university": "UNIVALLE EN NACIONAL \U0001F921\U0001F4C9top100",
        "country": "BO",
        "problemas_resueltos": 6,
        "points": 724
    }
]

problemasTeam = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
    [1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [1, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0],
]

html = _ranking_html(
    rows,
    cantidadProblemas=12,
    problemasTeam=problemasTeam,
    titulo="TOP 20 COLOMBIA",
    top_n=20,
    rpc_name="RPC 08",
    datetime_str="22/09/2026 18:33 Hora de Colombia"
)

out_path = "scratch/test_table_clean.jpg"
_screenshot_html(html, out_path)
print(f"Table image successfully generated at {out_path}!")
