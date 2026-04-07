# agentcontainer

`agentcontainer` e' un runtime TCP per agenti mobili scritti in Python. Ogni agente viene inviato come file Python puro autenticato a livello di messaggio, viene caricato "in vivo" nel container di destinazione e puo' usare primitive host per filesystem, processi locali, rete HTTP e mobilita' tra container federati ad albero.

## Obiettivi

- Trasporto e attivazione di agenti Python come file Python puri.
- Autenticazione esplicita per ogni messaggio tramite HMAC.
- Secret dell'agente incorporata nell'agente stesso.
- Nessuna dipendenza da un provider LLM specifico nel container.
- Primitive di base per clone, move, networks, filesystem e HTTP.
- Federazione di `agentcontainer` in topologie ad albero.
- Ambiente Docker per testare deploy, clonazione, viaggio e ricerca distribuita.

## Stato del progetto

Questa repository implementa una base funzionante:

- Server TCP `asyncio` con protocollo JSON Lines.
- CLI unificata con `server`, `send`, `run`, `invoke`, `tree`.
- Loader di agenti Python con lifecycle `on_activate` e `on_message`.
- Primitive host: `read_file`, `search_files`, `run`, `http_request`, `clone`, `move`, `networks`, `capabilities`, `resources`, `return_to_stage`.
- Federazione statica ad albero via file JSON di configurazione.
- Agente di esempio `travelling_scout` che visita i nodi e cerca file che contengono una query.
- Test automatici di autenticazione, deploy/invoke e clone/move.
- Ambiente `docker compose` con tre container federati.

## Architettura rapida

Ogni messaggio e' una riga JSON con struttura:

```json
{
  "type": "deploy_agent",
  "sender": "admin",
  "timestamp": 1770000000,
  "nonce": "uuid",
  "payload": {},
  "signature": "hex-hmac"
}
```

La firma e' calcolata sul messaggio canonico senza `signature`.

Tipi principali:

- `deploy_agent`: deploy amministrativo di un agente sorgente.
- `invoke_agent`: invoca un agente gia' attivo.
- `receive_agent`: ricezione di un agente clonato o spostato.
- `list_agents`: elenco degli agenti caricati.
- `describe_container`: metadati del nodo.
- `network_tree`: topologia federata configurata.

## Contratto dell'agente

Un agente e' un file Python che definisce almeno:

```python
AGENT_ID = "travelling-scout"
AGENT_SECRET = "change-me"

class Agent:
    async def on_activate(self, ctx, payload):
        ...

    async def on_message(self, ctx, payload):
        ...
```

`ctx` espone primitive host e di mobilita'. L'agente porta con se' la propria secret e la usa implicitamente quando il container esegue `clone` o `move`.

## CLI

`agentcontainer` e' anche la CLI utente da installare sul proprio PC per inviare agenti verso nodi remoti. Lo scambio dell'agente resta sempre il sorgente Python puro; stage, routing e autenticazione viaggiano come metadati separati dal file.

Esempi:

```bash
agentcontainer server 0.0.0.0:7007
agentcontainer send agents/demo/visitcontainer-and-go-back.py 0.0.0.0:7007
agentcontainer run agents/demo/visitcontainer-and-go-back.py
agentcontainer list-agents 127.0.0.1:7007
```

`agentcontainer server HOST:PORT` avvia un nodo con configurazione di sviluppo pronta all'uso. `agentcontainer send AGENTE.py HOST:PORT` apre automaticamente uno stage locale, spedisce il file Python puro al nodo remoto e resta appeso finche' l'agente non torna allo stage oppure finche' non premi `Ctrl+C`. `agentcontainer run AGENTE.py` fa la stessa cosa ma crea anche un nodo sandbox locale di destinazione, utile per test rapidi.

Per avviare un nodo come servizio:

```bash
agentcontainer server 0.0.0.0:7007
```

## Avvio locale

```bash
make install
pytest -q
agentcontainer server 0.0.0.0:7007
```

In un altro terminale:

```bash
agentcontainer send agents/demo/visitcontainer-and-go-back.py 0.0.0.0:7007
```

Se il nodo remoto deve richiamare il tuo stage attraverso un IP diverso da quello rilevato automaticamente, usa `--stage-host`.

## Ambiente Docker federato

Avvio:

```bash
docker compose up --build
```

Deploy dell'agente sul nodo root:

```bash
agentcontainer send agents/demo/visitcontainer-and-go-back.py 127.0.0.1:7000 --secret root-admin-secret
```

Lista agenti:

```bash
agentcontainer list-agents 127.0.0.1:7000 --secret root-admin-secret
```

Topologia:

```bash
agentcontainer tree 127.0.0.1:7000 --secret root-admin-secret
```

## Demo prevista

I container Docker montano dataset differenti:

- `root`: documenti generali.
- `department-a`: documenti con riferimenti agli scacchi.
- `department-b`: documenti tecnici e un altro riferimento agli scacchi.

L'agente `travelling_scout`:

- cerca la query localmente;
- legge l'albero federato;
- clona se stesso nei figli non ancora visitati;
- puo' muoversi in un nodo specifico;
- accumula risultati in memoria locale e li restituisce via `invoke`.

L'agente [visitcontainer-and-go-back.py](/home/francesco/Develop/_/agentcontainer/agents/demo/visitcontainer-and-go-back.py):

- arriva nel container target;
- legge primitive e risorse esposte agli agenti;
- prepara un report;
- torna allo stage da cui era partito;
- fa terminare automaticamente la CLI `send` o `run` quando rientra.

## Sicurezza e limiti della base

- Il modello di trust e' volutamente minimale: l'integrita' del messaggio e' garantita dall'HMAC, ma il primo `receive_agent` su un nodo nuovo si basa sulla secret trasportata dall'agente.
- Il runtime esegue codice Python dinamico: va usato solo in ambienti fidati o molto isolati.
- Le primitive locali sono potenti. In produzione e' necessario introdurre sandbox per processo, quote, ACL, auditing e policy per network e filesystem.
- La federazione nella base e' statica via configurazione; discovery dinamica e PKI non sono incluse.

## File principali

- [README.md](/home/francesco/Develop/_/agentcontainer/README.md)
- [DESIGN.md](/home/francesco/Develop/_/agentcontainer/DESIGN.md)
- [pyproject.toml](/home/francesco/Develop/_/agentcontainer/pyproject.toml)
- [src/agentcontainer/server.py](/home/francesco/Develop/_/agentcontainer/src/agentcontainer/server.py)
- [src/agentcontainer/runtime.py](/home/francesco/Develop/_/agentcontainer/src/agentcontainer/runtime.py)
- [src/agentcontainer/client.py](/home/francesco/Develop/_/agentcontainer/src/agentcontainer/client.py)
- [agents/travelling_scout.py](/home/francesco/Develop/_/agentcontainer/agents/travelling_scout.py)
- [docker-compose.yml](/home/francesco/Develop/_/agentcontainer/docker-compose.yml)
- [scripts/generate_whitepaper_pdf.py](/home/francesco/Develop/_/agentcontainer/scripts/generate_whitepaper_pdf.py)
- [WHITEPAPER.pdf](/home/francesco/Develop/_/agentcontainer/WHITEPAPER.pdf)

## Whitepaper

Il whitepaper sorgente e' in [WHITEPAPER.md](/home/francesco/Develop/_/agentcontainer/WHITEPAPER.md) e il PDF viene generato con:

```bash
python3 scripts/generate_whitepaper_pdf.py
```
