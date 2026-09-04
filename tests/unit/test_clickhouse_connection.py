from types import SimpleNamespace

from thai_data_platform.warehouse import clickhouse


def test_clickhouse_connection_bootstraps_database_before_using_it(monkeypatch):
    calls = []
    client = SimpleNamespace(database="__default__")

    def fake_get_client(**kwargs):
        calls.append(kwargs)

        def command(sql, **options):
            calls.append((sql, options))

        client.command = command
        return client

    monkeypatch.setattr(clickhouse.clickhouse_connect, "get_client", fake_get_client)

    returned = clickhouse.connect(host="localhost", database="analytics")

    assert returned is client
    assert calls[0]["database"] == "__default__"
    assert calls[1] == (
        "CREATE DATABASE IF NOT EXISTS analytics",
        {"use_database": False},
    )
    assert returned.database == "analytics"
