"""adql_run: optional Gaia login and limits. The auth branch is tested with a mocked login; no real login."""
import sys
import types

from pipeline.archives import adql_run as ar


def _fake_gaia(monkeypatch, login):
    mod = types.ModuleType("astroquery.gaia")
    mod.Gaia = types.SimpleNamespace(login=login)
    monkeypatch.setitem(sys.modules, "astroquery.gaia", mod)


def test_anonymous_without_credentials(capsys):
    assert ar.gaia_login(env={}) is None
    assert "anonymous" in capsys.readouterr().out
    assert ar.gaia_login(env={"GAIA_USER": "u"}) is None  # password missing


def test_authenticated_logs_user_not_password(monkeypatch, capsys):
    calls = []
    _fake_gaia(monkeypatch, lambda **kw: calls.append(kw))
    assert ar.gaia_login(env={"GAIA_USER": "alice", "GAIA_PASSWORD": "s3cret-pw"}) == "alice"
    out = capsys.readouterr().out
    assert "authenticated as alice" in out and "s3cret-pw" not in out
    assert calls == [{"user": "alice", "password": "s3cret-pw"}]


def test_failed_login_falls_back_without_leaking(monkeypatch, capsys):
    def boom(**kw):
        raise RuntimeError("bad credentials s3cret-pw")

    _fake_gaia(monkeypatch, boom)
    assert ar.gaia_login(env={"GAIA_USER": "alice", "GAIA_PASSWORD": "s3cret-pw"}) is None
    out = capsys.readouterr().out
    assert "s3cret-pw" not in out and "login failed" in out


def test_limits(tmp_path):
    cfg = tmp_path / "a.yaml"
    cfg.write_text("archives:\n  - key: gaia\n    authenticated_row_limit: null\n")
    assert ar.limits(True, cfg) == (50_000, 40_000)  # unknown limit: stay conservative
    assert ar.limits(False, cfg) == (50_000, 40_000)
    cfg.write_text("archives:\n  - key: gaia\n    authenticated_row_limit: 3000000\n")
    assert ar.limits(True, cfg) == (3_000_000, 2_400_000)
    assert ar.limits(False, cfg) == (50_000, 40_000)  # anonymous ignores the config value


def test_repo_config_limit_is_unmeasured():
    assert ar.authenticated_row_limit() is None
