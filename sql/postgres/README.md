# PostgreSQL SQL

This directory contains the ordered PostgreSQL migrations and DDL.

The first implementation must create exactly these schemas:

```text
raw
staging
core
ops
```

See [`docs/DATA_MODEL.md`](../../docs/DATA_MODEL.md) for the implemented grain and constraint contract.
