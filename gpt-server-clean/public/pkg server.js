// server.js

const express = require('express');
const path = require('path');
const fs = require('fs');
const axios = require('axios');

const app = express();
const PORT = 3000;
const DATA_FILE = path.join(__dirname, 'data.json');
const API_KEY = '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';

let state = { orden: '', messages: [] };
if (fs.existsSync(DATA_FILE)) {
  try {
    const data = fs.readFileSync(DATA_FILE, 'utf-8');
    state = JSON.parse(data);
  } catch (e) {
    console.error('Error leyendo data.json:', e);
  }
}

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

app.get('/data', (req, res) => {
  res.json(state);
});

app.post('/data', (req, res) => {
  const { orden, messages } = req.body;
  if (orden !== undefined) state.orden = orden;
  if (messages !== undefined) state.messages = messages;
  fs.writeFileSync(DATA_FILE, JSON.stringify(state, null, 2));
  res.json({ status: 'ok' });
});

app.post('/gpt', async (req, res) => {
  const { input, role } = req.body;
  const fullPrompt = `${state.orden}\nUsuario: ${input}`;
  try {
    const response = await axios.post('https://api.openai.com/v1/chat/completions', {
      model: 'gpt-3.5-turbo',
      messages: [
        { role: 'system', content: state.orden },
        { role: 'user', content: input }
      ]
    }, {
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json'
      }
    });
    const output = response.data.choices[0].message.content;
    state.messages.push({ role, content: input });
    state.messages.push({ role: 'assistant', content: output });
    fs.writeFileSync(DATA_FILE, JSON.stringify(state, null, 2));
    res.json({ output });
  } catch (err) {
    console.error('Error al llamar a GPT:', err);
    res.status(500).json({ error: 'Error al contactar GPT' });
  }
});

app.listen(PORT, () => {
  console.log(`Servidor Node.js corriendo en http://localhost:${PORT}`);
});
