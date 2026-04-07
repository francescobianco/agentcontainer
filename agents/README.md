# Agent Catalog

Collezione iniziale di agenti organizzata per categorie.

- `basic/`: agenti minimi per smoke test e introspezione di base.
- `demo/`: agenti dimostrativi per stage, viaggio e tour.
- `search/`: agenti orientati a trovare informazioni nei file locali.
- `maintain/`: agenti per snapshot operative e manutenzione.
- `lab/`: agenti sperimentali per ambienti di test e laboratorio.

Ogni file e' un agente Python puro, inviabile direttamente con:

```bash
agentcontainer send agents/basic/ping_agent.py 0.0.0.0:7007
```
