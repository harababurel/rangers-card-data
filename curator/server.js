const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const https = require('https');
const crypto = require('crypto');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const cacheDir = path.join(__dirname, 'cache');
if (!fs.existsSync(cacheDir)) {
  fs.mkdirSync(cacheDir);
}

const jsonPath = path.join(__dirname, '../Earthborne_Rangers.json');

const activeDownloads = new Map();

app.get('/api/image', async (req, res) => {
  const imageUrl = req.query.url;
  if (!imageUrl) return res.status(400).send('Missing url parameter');

  const hash = crypto.createHash('md5').update(imageUrl).digest('hex');
  const ext = path.extname(new URL(imageUrl).pathname) || '.jpg';
  const cachedFilePath = path.join(cacheDir, `${hash}${ext}`);

  if (fs.existsSync(cachedFilePath)) {
    return res.sendFile(cachedFilePath);
  }

  if (activeDownloads.has(hash)) {
    try {
      await activeDownloads.get(hash);
      return res.sendFile(cachedFilePath);
    } catch (err) {
      return res.status(500).send(err.message);
    }
  }

  const downloadPromise = new Promise((resolve, reject) => {
    https.get(imageUrl, (response) => {
      if (response.statusCode !== 200) {
        return reject(new Error('Failed to fetch image'));
      }
      const fileStream = fs.createWriteStream(cachedFilePath);
      response.pipe(fileStream);
      fileStream.on('finish', () => {
        fileStream.close();
        resolve();
      });
    }).on('error', (err) => {
      fs.unlink(cachedFilePath, () => {});
      reject(err);
    });
  });

  activeDownloads.set(hash, downloadPromise);

  try {
    await downloadPromise;
    res.sendFile(cachedFilePath);
  } catch (err) {
    res.status(500).send(err.message);
  } finally {
    activeDownloads.delete(hash);
  }
});

app.get('/api/repo-cards', (req, res) => {
  const packsDir = path.join(__dirname, '../packs');
  const allCards = [];
  
  if (fs.existsSync(packsDir)) {
    const packs = fs.readdirSync(packsDir);
    for (const pack of packs) {
      const packPath = path.join(packsDir, pack);
      if (fs.statSync(packPath).isDirectory()) {
        const jsonFiles = fs.readdirSync(packPath).filter(f => f.endsWith('.json'));
        for (const file of jsonFiles) {
          const filePath = path.join(packPath, file);
          try {
            const content = JSON.parse(fs.readFileSync(filePath, 'utf8'));
            if (Array.isArray(content)) {
              allCards.push(...content);
            }
          } catch (e) {
            console.error('Error parsing', filePath, e);
          }
        }
      }
    }
  }
  console.log(`Repo search: found ${allCards.length} cards across all packs.`);
  res.json(allCards);
});

app.get('/api/packs', (req, res) => {
  const packsPath = path.join(__dirname, '../packs.json');
  if (fs.existsSync(packsPath)) {
    res.json(JSON.parse(fs.readFileSync(packsPath, 'utf8')));
  } else {
    res.json([]);
  }
});

app.get('/api/tokens', (req, res) => {
  const tokensPath = path.join(__dirname, '../tokens.json');
  if (fs.existsSync(tokensPath)) {
    const tokens = JSON.parse(fs.readFileSync(tokensPath, 'utf8'));
    tokens.sort((a, b) => a.name.localeCompare(b.name));
    res.json(tokens);
  } else {
    res.json([]);
  }
});

app.get('/api/categories', (req, res) => {
  const categoriesPath = path.join(__dirname, '../categories.json');
  if (fs.existsSync(categoriesPath)) {
    res.json(JSON.parse(fs.readFileSync(categoriesPath, 'utf8')));
  } else {
    res.json([]);
  }
});

app.get('/api/areas', (req, res) => {
  const areasPath = path.join(__dirname, '../areas.json');
  if (fs.existsSync(areasPath)) {
    res.json(JSON.parse(fs.readFileSync(areasPath, 'utf8')));
  } else {
    res.json([]);
  }
});

app.get('/api/cards', (req, res) => {
  const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
  const cards = [];

  function processObject(obj) {
    if (['Card', 'CardCustom'].includes(obj.Name) && (obj.Description === '' || obj.Description === undefined)) {
      if (obj.Nickname && obj.CustomDeck) {
        const deckId = Object.keys(obj.CustomDeck)[0];
        const deckInfo = obj.CustomDeck[deckId];
        const cardId = obj.CardID;
        const index = cardId % 100;
        
        cards.push({
          nickname: obj.Nickname,
          deckInfo,
          index
        });
      }
    }
    
    if (obj.ContainedObjects) {
      obj.ContainedObjects.forEach(processObject);
    }
  }

  data.ObjectStates.forEach(processObject);
  
  // Deduplicate by nickname and index
  const uniqueCards = [];
  const seen = new Set();
  for (const c of cards) {
    const key = `${c.nickname}-${c.index}-${c.deckInfo.FaceURL}`;
    if (!seen.has(key)) {
      seen.add(key);
      uniqueCards.push(c);
    }
  }

  res.json(uniqueCards);
});

const statePath = path.join(__dirname, 'state.json');

app.get('/api/state', (req, res) => {
  if (fs.existsSync(statePath)) {
    res.json(JSON.parse(fs.readFileSync(statePath, 'utf8')));
  } else {
    res.json({ queue: [], completedCards: [] });
  }
});

app.post('/api/state', (req, res) => {
  fs.writeFileSync(statePath, JSON.stringify(req.body, null, 2));
  res.json({ success: true });
});

app.post('/api/save', (req, res) => {
  const newCards = req.body;
  const outPath = path.join(__dirname, '../packs/core/new_encounter_cards.json');
  
  let existing = [];
  if (fs.existsSync(outPath)) {
    existing = JSON.parse(fs.readFileSync(outPath, 'utf8'));
  }
  
  existing = existing.concat(newCards);
  fs.writeFileSync(outPath, JSON.stringify(existing, null, 2));

  // Also clear the queue in the state file since it has been flushed
  if (fs.existsSync(statePath)) {
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    state.queue = [];
    fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
  }
  
  res.json({ success: true, count: newCards.length });
});

const PORT = 3002;
const HOST = '127.0.0.1';
app.listen(PORT, '0.0.0.0', () => console.log(`Server running on http://${HOST}:${PORT}`));
