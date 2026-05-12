# Connect-RPC Client Layer

> 34 nodes · cohesion 0.06

## Key Concepts

- **EcomRuntimeClientSync** (16 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **PcmRuntimeClientSync** (14 connections) — `bitgn/vm/pcm_connect.py`
- **ConnectClient** (9 connections) — `bitgn/_connect.py`
- **_connect.py** (2 connections) — `bitgn/_connect.py`
- **.__init__()** (2 connections) — `bitgn/harness_connect.py`
- **.__init__()** (2 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.__init__()** (2 connections) — `bitgn/vm/pcm_connect.py`
- **.call()** (1 connections) — `bitgn/_connect.py`
- **.__init__()** (1 connections) — `bitgn/_connect.py`
- **Minimal Connect RPC client using JSON protocol over httpx.** (1 connections) — `bitgn/_connect.py`
- **ecom_connect.py** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **pcm_connect.py** (1 connections) — `bitgn/vm/pcm_connect.py`
- **.answer()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.context()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.delete()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.exec()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.find()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.list()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.read()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.search()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.stat()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.tree()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.write()** (1 connections) — `bitgn/vm/ecom/ecom_connect.py`
- **.answer()** (1 connections) — `bitgn/vm/pcm_connect.py`
- **.context()** (1 connections) — `bitgn/vm/pcm_connect.py`
- *... and 9 more nodes in this community*

## Relationships

- [[BitGN Harness Integration]] (2 shared connections)
- [[Prephase & VM Bootstrap]] (1 shared connections)
- [[Orchestrator Entry Point]] (1 shared connections)

## Source Files

- `bitgn/_connect.py`
- `bitgn/harness_connect.py`
- `bitgn/vm/ecom/ecom_connect.py`
- `bitgn/vm/pcm_connect.py`

## Audit Trail

- EXTRACTED: 61 (82%)
- INFERRED: 13 (18%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*