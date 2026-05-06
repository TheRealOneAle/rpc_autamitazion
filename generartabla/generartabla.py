import psycopg2
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import time
import os

# 🔹 Conexión
conn = psycopg2.connect(
    host="localhost",
    database="bkboca",
    user="postgres",
    password="1234"
)

cur = conn.cursor()

query = """
WITH ac AS (
    SELECT 
        usernumber,
        runproblem,
        MIN(rundate) AS ac_time,
        MIN(rundatediff) AS rundatediff
    FROM runtable
    WHERE runanswer = 1
    GROUP BY usernumber, runproblem
),

fallos AS (
    SELECT 
        ac.usernumber,
        ac.runproblem,
        ac.ac_time,
        ac.rundatediff,
        COUNT(*) FILTER (
            WHERE r.runanswer > 1 
              AND r.rundate < ac.ac_time
        ) AS intentos_fallidos
    FROM ac
    JOIN runtable r
        ON r.usernumber = ac.usernumber
       AND r.runproblem = ac.runproblem
    GROUP BY ac.usernumber, ac.runproblem, ac.ac_time, ac.rundatediff
)

SELECT 
    b.userfullname, b.country, b.usernumber,
    COUNT(*) AS problemas_resueltos,
    SUM(
        f.rundatediff/60 + (f.intentos_fallidos * 20)
    ) AS points
FROM fallos f
JOIN usertable b 
    ON f.usernumber = b.usernumber
WHERE b.usertype = 'team'
GROUP BY b.userfullname, b.country, b.usernumber
ORDER BY problemas_resueltos DESC, points ASC
LIMIT 10;
"""

cur.execute(query)
rows = cur.fetchall()
query2= """
    select count(*) from problemtable;
"""
teams = [row[2] for row in rows]

queryTeamsAC = """
SELECT DISTINCT usernumber, runproblem
FROM runtable
WHERE runanswer = 1
AND usernumber = ANY(%s);
"""
cur.execute(queryTeamsAC, (teams,))
teamsAC = cur.fetchall()
cur.execute(query2)
cantidadProblemas = cur.fetchone()[0] - 1

teamsIndex = {team: i for i, team in enumerate(teams)}

problemasTeam = [
    [0 for _ in range(cantidadProblemas)]
    for _ in range(10)
]

for team, problem in teamsAC:
    if team in teamsIndex:
        i = teamsIndex[team]
        j = problem - 1  # si empieza en 1

        if 0 <= j < cantidadProblemas:
            problemasTeam[i][j] = 1


cur.close()
conn.close()
headers = ""
for i in range(cantidadProblemas):
    headers += f"<th>{chr(65 + i)}</th>"
rows_html = ""
for i, r in enumerate(rows):
    style = ""
    if i == 0:
        style = 'style="background-color:#FFF673;"'
    elif i == 1:
        style = 'style="background-color:#9FCDD6;"'
    elif i == 2:
        style = 'style="background-color:#80C491;"'
    problemasHtml = ""
    for j in range(cantidadProblemas):
        if problemasTeam[i][j] == 1:
            problemasHtml += f'<td class="problemTeam"><img src="file:///home/alejo/Proyectos/microservicios/Proyecto_Boca/generarglobos/globosgenerados/{chr(65 + j)}.png" class="balloon"></td>'
        else:
            problemasHtml += '<td>-</td>'
    rows_html += f"""
    <tr {style}>
        <td class="numequipo">{i}</td>
        <td class="team-col">
            <img src="file:///home/alejo/Proyectos/microservicios/Proyecto_Boca/generartabla/flags/{r[1].lower()}.svg" class="flag">
            <span>{r[0]}</span>
        </td>
        {problemasHtml}
        <td class="puntos">{r[3]} ({r[4]})</td>
    </tr>
    """
html = f"""
<html>
<head>
<style>
body {{
    font-family: Arial, sans-serif;
    background-color: #f4f6f7;
}}
.cabecera {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 15px;
}}
.logorpc {{
    width: 100px;
}}
table {{
    border-collapse: collapse;
    margin: auto;
    width: 65%;
    background: white;
    border-radius: 10px;
    overflow: hidden;
}}
th {{
    background-color: #CF1F4A;
    color: white;
    padding: 12px;
}}
td {{
    vertical-align: middle
}}
.numequipo {{
    text-align: center;
}}
.puntos{{
    text-align: center;
}}
.problemTeam {{
    text-align: center;
}}
tr:nth-child(even) {{
    background-color: #f2f2f2;
}}
.balloon {{
    width: 28px;
}}
.flag {{
    width: 25px;
    height: 25px;
    border-radius: 50%;
    vertical-align: middle
}}
.team-col {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px;
}}
</style>
</head>
<body>
<div class="cabecera">
    <img src="logorpc/rpc.png" class="logorpc">
    <h2>Top 10 Latinoamerica</h2>
</div>
<table>
<tr>
    <th>#</th>
    <th>Equipo</th>
    {headers}
    <th>Total</th>
</tr>
{rows_html}
</table>
</body>
</html>
"""

with open("ranking.html", "w", encoding="utf-8") as f:
    f.write(html)
    
# Generate image using Selenium
options = Options()
options.headless = True
driver = webdriver.Firefox(options=options)
driver.set_window_size(1200, 800)  # Adjust size as needed
driver.get("file:///" + os.path.abspath("ranking.html"))
time.sleep(2)  # Allow page to fully load
driver.save_screenshot("ranking.jpg")
driver.quit()

