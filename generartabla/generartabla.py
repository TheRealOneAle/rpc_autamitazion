import psycopg2

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
    letra = chr(65 + i)  # A, B, C...
    headers += f"<th>{letra}</th>"

rows_html = ""
for i, r in enumerate(rows):
    style = ""
    if i == 0:
        style = 'style="background-color: #FFF673;"'
    elif i == 1:
        style = 'style="background-color: #9FCDD6;"'
    elif i == 2:
        style = 'style="background-color: #80C491;"'

    
    rows_html += f"""
    <tr {style}>
        <td>{i}</td>
        <td class="team-cell">
            <img src="flags/{r[1].lower()}.svg" class="flag">
                {r[0]}
        </td>
        problemas_html = ""
            for j in range(cantidadProblemas):
                if problemasTeameam[i][j] == 1:
                    problemas_html += '<td class="ok">✔</td>'
                else:
                    problemas_html += '<td class="fail">-</td>'
        <td>{r[3]} ({r[4]})</td>
    </tr>
    """

# 🔹 HTML completo
html = f"""
<html>
<head>
<style>
    .team-cell {{
        display: flex;
        align-items: center;
        gap: 10px;
        justify-content: left;
    }}
    
    .flag {{
        width: 25px;
        height: 25px;
        border-radius: 50%;
        object-fit: cover;
    }}

    .cabecera {{
        display: flex;
        align-items: center;   /* alinea verticalmente */
        justify-content: center; /* centra todo horizontalmente */
        gap: 15px; /* espacio entre logo y texto */
    }}
    
    .logorpc{{
        width: 100px;
    }}    

    body {{
        font-family: Arial, sans-serif;
        background-color: #f4f6f7;
    }}
    h2 {{
        text-align: center;
    }}
    table {{
        border-collapse: collapse;
        margin: auto;
        width: 60%;
        font-size: 18px;
        background: white;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.2);
    }}
    th {{
        background-color: #CF1F4A;
        color: white;
        padding: 12px;
    }}
    td {{
        padding: 10px;
        text-align: center;
    }}
    tr:nth-child(even) {{
        background-color: #f2f2f2;
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
