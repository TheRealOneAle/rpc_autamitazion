const express = require('express');
const cors = require('cors');
const { Client } = require('pg');

const app = express();
app.use(cors());
app.use(express.json());

const DB_CONFIG = {
  host: process.env.DB_HOST || 'postgres',
  port: parseInt(process.env.DB_PORT) || 5432,
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASS || '1234',
  database: process.env.DB_NAME || 'bkboca',
  connectionTimeoutMillis: 5000
};

async function getClient() {
  const client = new Client(DB_CONFIG);
  await client.connect();
  return client;
}

app.post('/api/connect', async (req, res) => {
    const { host, port, user, password } = req.body;
    
    console.log(`Intento de conexión a ${host}:${port} como ${user}`);

    const client = new Client({
        host,
        port: parseInt(port) || 5432,
        user,
        password,
        database: 'bkboca',
        connectionTimeoutMillis: 5000 
    });

    try {
        await client.connect();
        const resDb = await client.query('SELECT current_database();');
        await client.end();
        console.log('Conexión exitosa a la base de datos');
        res.json({ success: true, message: `Conectado de forma segura a la base de datos: ${resDb.rows[0].current_database}` });
    } catch (error) {
        console.error('Error de conexión:', error.message);
        res.status(500).json({ success: false, message: `Error de conexión: ${error.message}` });
    }
});

app.post('/api/query', async (req, res) => {
    const { host, port, user, password, query } = req.body;
    
    if (!query) {
        return res.status(400).json({ success: false, error: "No se proporcionó ninguna consulta SQL" });
    }

    console.log(`Ejecutando query en ${host}:${port}: ${query}`);

    const client = new Client({
        host,
        port: parseInt(port) || 5432,
        user,
        password,
        database: 'bkboca',
        connectionTimeoutMillis: 5000 
    });

    try {
        await client.connect();
        const result = await client.query(query);
        await client.end();
        res.json({ success: true, rows: result.rows, command: result.command, rowCount: result.rowCount });
    } catch (error) {
        console.error('Error de query:', error.message);
        res.status(500).json({ success: false, error: `Error ejecutando consulta: ${error.message}` });
    }
});

// Endpoint para obtener problemas y colores (usado por generarglobos)
app.get('/api/problems', async (req, res) => {
  try {
    const client = await getClient();
    const result = await client.query(
      'SELECT problemnumber, problemcolor FROM problemtable WHERE problemnumber != 0;'
    );
    await client.end();
    res.json({ success: true, rows: result.rows });
  } catch (error) {
    console.error('Error obteniendo problemas:', error.message);
    res.status(500).json({ success: false, error: `Error: ${error.message}` });
  }
});

// Endpoint para obtener runs AC por equipo y problema (usado por generartabla)
app.get('/api/teams/ac', async (req, res) => {
  try {
    const client = await getClient();
    const result = await client.query(
      'SELECT DISTINCT usernumber, runproblem FROM runtable WHERE runanswer = 1;'
    );
    await client.end();
    res.json({ success: true, rows: result.rows });
  } catch (error) {
    console.error('Error obteniendo AC runs:', error.message);
    res.status(500).json({ success: false, error: `Error: ${error.message}` });
  }
});

// Endpoint para obtener ranking (usado por generartabla)
app.get('/api/ranking', async (req, res) => {
  try {
    const client = await getClient();
    const result = await client.query(`
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
          b.userfullname,
          b.country,
          b.usernumber,
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
    `);
    const rows = result.rows;

    const query2 = await client.query('SELECT count(*) FROM problemtable;');
    const cantidadProblemas = query2.rows[0].count - 1;

    await client.end();
    res.json({ 
      success: true, 
      rows: rows,
      cantidadProblemas: cantidadProblemas 
    });
  } catch (error) {
    console.error('Error obteniendo ranking:', error.message);
    res.status(500).json({ success: false, error: `Error: ${error.message}` });
  }
});

// Endpoint para obtener total de problemas
app.get('/api/problems/count', async (req, res) => {
  try {
    const client = await getClient();
    const result = await client.query('SELECT count(*) FROM problemtable;');
    await client.end();
    res.json({ success: true, count: result.rows[0].count });
  } catch (error) {
    console.error('Error obteniendo count de problemas:', error.message);
    res.status(500).json({ success: false, error: `Error: ${error.message}` });
  }
});

const PORT = 3001;
app.listen(PORT, () => {
    console.log(`API intermediaria corriendo en http://localhost:${PORT}`);
});
