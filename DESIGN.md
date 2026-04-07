# Design di agentcontainer

## 1. Visione

`agentcontainer` e' un nodo di esecuzione per agenti mobili. Un agente non e' un record in database o una funzione serializzata: e' sorgente Python trasferibile, firmato a livello di messaggio, che viene caricato in memoria da un container e puo' chiedere al container primitive locali per agire sul sistema o per spostarsi verso altri container federati.

La separazione chiave e' questa:

- il container offre il substrate operativo;
- l'agente contiene identita', secret, logica e configurazione dei servizi esterni;
- l'accesso a LLM o API esterne e' deciso dall'agente, non dal container.

## 2. Requisiti tradotti in architettura

### 2.1 Messaggi autenticati

Ogni messaggio ricevuto sul socket TCP contiene:

- `type`
- `sender`
- `timestamp`
- `nonce`
- `payload`
- `signature`

La firma e' `HMAC-SHA256(secret, canonical_json(message_without_signature))`.

Il server valida:

- freshness del timestamp;
- presenza del nonce;
- firma;
- autorizzazione del `sender` rispetto al tipo di messaggio.

### 2.2 Agenti come file Python

L'agente e' distribuito come testo Python.

Manifest minimo richiesto:

- `AGENT_ID`
- `AGENT_SECRET`
- `class Agent`

Hook supportati:

- `on_activate(ctx, payload)`
- `on_message(ctx, payload)`

### 2.3 Secret posseduta dall'agente

Il container non e' source of truth per la secret applicativa dell'agente. Durante deploy o `receive_agent`, il sorgente dell'agente contiene la secret che il nodo usa per:

- verificare eventuali messaggi firmati dall'agente quando esso e' gia' registrato;
- rifirmare trasferimenti `clone` e `move`;
- mantenere coerenza di identita' tra nodi.

### 2.4 Primitive host

Primitive minime della base:

- `networks()`: albero federato configurato.
- `read_file(path)`: lettura controllata dentro `data_root`.
- `search_files(query)`: ricerca full text su file di testo.
- `run(command)`: esecuzione processo locale con timeout.
- `http_request(...)`: uscita HTTP per LLM o altre API esterne.
- `clone(destination, payload)`: copia l'agente su un altro nodo e lo attiva.
- `move(destination, payload)`: come `clone`, poi rimuove l'istanza locale.
- `log(message)`: logging strutturato.

### 2.5 Federazione ad albero

Il modello e' volutamente gerarchico:

- ogni nodo conosce i figli;
- l'albero e' dichiarato in configurazione;
- gli agenti vedono l'albero via `networks`;
- la mobilita' avviene sempre tramite endpoint e porta del nodo target.

La base non implementa discovery dinamica, consenso, routing opportunistico o mesh.

## 3. Protocollo

### 3.1 Trasporto

- TCP
- framing: JSON Lines
- una richiesta, una risposta

### 3.2 Tipi di messaggio

#### `deploy_agent`

Mittente previsto: `admin`

Payload:

- `source_code`
- `activate_payload` opzionale

Effetto:

- parsing manifest
- caricamento modulo
- istanziazione agente
- invocazione opzionale di `on_activate`

#### `receive_agent`

Mittente previsto: un agente o un admin

Payload:

- `source_code`
- `activate_payload`
- `mode`: `clone` oppure `move`
- `trace`: hop gia' attraversati

Effetto:

- registrazione/aggiornamento agente
- invocazione `on_activate`

#### `invoke_agent`

Mittente previsto: `admin`

Payload:

- `agent_id`
- `message`

Effetto:

- invocazione `on_message`

#### `network_tree`

Restituisce l'albero statico definito nella config locale.

#### `describe_container`

Restituisce nome nodo, porta e figli configurati.

## 4. Runtime interno

### 4.1 Registry agenti

Per ogni agente attivo il nodo mantiene:

- `agent_id`
- `agent_secret`
- `source_code`
- `instance`
- `module`
- `last_result`
- `metadata`

### 4.2 Loader dinamico

Il loader:

1. esegue il sorgente in un `ModuleType` dedicato;
2. estrae manifest e classe `Agent`;
3. istanzia la classe;
4. salva l'istanza nel registry.

### 4.3 Context

Il `ctx` consegnato all'agente incapsula il riferimento al runtime e all'agente corrente. In questo modo le primitive non sono globali ma contestualizzate.

## 5. Mobilita' degli agenti

### 5.1 Clone

`clone(destination, payload)`:

1. risolve il nodo target dall'albero federato;
2. prepara un messaggio `receive_agent`;
3. firma usando `AGENT_SECRET`;
4. invia il proprio sorgente;
5. il nodo target carica ed eventualmente attiva il clone;
6. il nodo corrente resta attivo.

### 5.2 Move

`move(destination, payload)`:

1. esegue il flusso di `clone`;
2. se il target risponde `ok`, deregistra l'agente locale.

### 5.3 Tracciamento

Per evitare loop banali, la base supporta un campo `trace` che l'agente puo' usare per segnare i nodi visitati. Il runtime non impone policy globale, ma offre il meccanismo.

## 6. Modello LLM

`agentcontainer` non incorpora un motore LLM. La responsabilita' e' dell'agente:

- l'agente puo' possedere URL, model id e API key;
- l'agente usa `http_request` o librerie Python eventualmente importate dal proprio sorgente;
- il container resta neutrale rispetto al provider.

Questo evita lock-in architetturale e rende l'agente portabile.

## 7. Sicurezza

### 7.1 Proprieta' offerte dalla base

- integrita' del messaggio;
- identificazione del mittente tramite secret condivisa;
- separazione tra secret admin e secret agente;
- superficie di protocollo piccola e leggibile.

### 7.2 Rischi aperti

- esecuzione di codice arbitrario;
- bootstrap debole per un agente che arriva la prima volta;
- mancanza di sandbox OS-level;
- mancanza di limitazioni fini per le primitive;
- assenza di rotazione secret, revoca, attestazione e audit robusto.

### 7.3 Roadmap di hardening

- firma asimmetrica con chiavi pubbliche distribuite;
- sandbox per agente in subprocess o microVM;
- capability token per primitive;
- quote CPU/RAM/I/O;
- event sourcing e audit append-only;
- federation discovery con trust anchors.

## 8. Layout del progetto

### 8.1 Package

- `auth.py`: HMAC, firma, verifica.
- `cli.py`: CLI unificata con `server`, `send`, `run`, `invoke`.
- `protocol.py`: framing JSON Lines.
- `config.py`: caricamento config.
- `runtime.py`: registry, loader, context, primitive.
- `server.py`: TCP server e dispatch.
- `client.py`: CLI di controllo.

### 8.2 Materiale demo

- `agents/travelling_scout.py`: agente mobile di ricerca.
- `examples/*.json`: config dei nodi.
- `fixtures/*`: dataset per la demo.
- `docker-compose.yml`: laboratorio federato.

## 9. Scenario d'uso: laboratorio

Ogni PC del laboratorio esegue un `agentcontainer`. Un agente viene deployato sul nodo root con la richiesta:

- esplora l'albero;
- cerca file che citano "scacchi";
- lascia copie nei dipartimenti;
- torna i risultati parziali a ogni nodo.

Questo repository implementa esattamente una versione dimostrativa di quello scenario.

## 11. Modalita' di test locale

La CLI include `agentcontainer run <agente.py>`.

Questa modalita':

- avvia un server locale temporaneo isolato;
- espone un `data_root` locale dedicato o configurabile;
- invia automaticamente l'agente al server appena avviato;
- opzionalmente esegue una `invoke` subito dopo il deploy;
- termina il server al termine del test.

Lo scopo e' consentire sviluppo e debug rapido dell'agente senza dipendere da un nodo di dipartimento gia' acceso. Anche se sulla macchina esiste gia' un `agentcontainer server`, `run` resta utile per una prova isolata su una porta dedicata.

## 10. Decisioni progettuali

- Python puro e `asyncio` per ridurre attrito iniziale.
- TCP custom invece di HTTP per tenere il protocollo minimale.
- JSON Lines invece di un framing binario proprietario.
- Federazione statica prima della discovery.
- Runtime "unsafe by design" per privilegiare il modello concettuale; hardening rinviato.
