// server.js

const http = require('http');

const API_KEY = "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";
const PORT = 3000;

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/chat') {
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', async () => {
      try {
        const userInput = JSON.parse(body).message;

        const fetch = (...args) => import('node-fetch').then(({default: fetch}) => fetch(...args));
        const response = await fetch('https://api.openai.com/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${API_KEY}`
          },
          body: JSON.stringify({
            model: 'gpt-3.5-turbo',
            messages: [{ role: 'user', content: userInput }]
          })
        });

        const data = await response.json();
        const reply = data.choices?.[0]?.message?.content || "Sin respuesta de GPT.";

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ reply }));

      } catch (error) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Error procesando solicitud GPT' }));
      }
    });
  } else {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end("Servidor robusto ejecutándose correctamente.");
  }
});

server.listen(PORT, () => {
  console.log(`Servidor escuchando en http://localhost:${PORT}`);
});
