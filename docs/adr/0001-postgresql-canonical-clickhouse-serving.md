# PostgreSQL canonical truth with ClickHouse serving

**Status:** accepted

Thai Public Data Platform uses PostgreSQL as the canonical relational truth for raw evidence, source-aligned staging, approved core facts and operational metadata. ClickHouse is a downstream analytical serving layer populated only after the PostgreSQL quality gate passes. This preserves transactional integrity and replayability while allowing an analytical engine to serve read-heavy SQL without becoming the authority for corrections or lineage.

DuckDB was considered as a local embedded option and is deliberately not carried into this canonical architecture.
