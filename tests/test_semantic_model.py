from fabric_mesh_tools import semantic_model as sm


def test_query_selects_every_measure():
    q = sm.query()
    assert q.startswith("EVALUATE ROW (")
    assert all(f"[{m}]" in q for m in sm.MEASURES)


def response(**values):
    return {"results": [{"tables": [{"rows": [{f"[{k}]": v for k, v in values.items()}]}]}]}


def test_parse_and_pass():
    values = sm.parse(response(**{m: 1.0 for m in sm.MEASURES}))
    assert values["Trips per wet day"] == 1.0
    assert sm.problems(values) == []


def test_blank_measures_and_no_trips_fail():
    blank = sm.parse(response(**{m: (None if m == "Trips per wet day" else 1) for m in sm.MEASURES}))
    assert sm.problems(blank) == ["Trips per wet day is blank"]
    empty = sm.parse(response(**{m: 0 for m in sm.MEASURES}))
    assert sm.problems(empty) == ["no trips"]


def test_ci_checks_framing_instead_of_dax(monkeypatch, capsys):
    models = {"analytics": {"name": "sm", "workspace_id": "w", "id": "m"}}
    monkeypatch.setattr(sm.terraform, "output", lambda *a: models)
    monkeypatch.setattr(sm, "in_github_actions", lambda: True)
    calls = []

    def fake(method, url, body=None, scope=None):
        calls.append(url)
        return {"value": [{"status": status}]}

    monkeypatch.setattr(sm, "request", fake)
    status = "Completed"
    sm.main([])
    assert not any("executeQueries" in c for c in calls)
    assert "last framing Completed" in capsys.readouterr().out
    status = "Failed"
    try:
        sm.main([])
    except SystemExit as exc:
        assert "1 semantic model check(s) failed" in str(exc)
    else:
        raise AssertionError("a failed framing must fail the check")
