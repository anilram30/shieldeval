import json

from shieldeval.cli import main


def test_cli_compare_and_evaluate(archive, tmp_path, capsys):
    assert main(["compare", str(archive)]) == 0
    assert "6/6" in capsys.readouterr().out
    rc = main(["evaluate", str(archive / "raw" / "S02_optimised_braid.dat"), "--with-legacy", "--out", str(tmp_path)])
    assert rc == 0
    d = json.loads((tmp_path / "S02_optimised_braid.json").read_text())
    assert d["verdict"] == "PASS" and d["summary"]["zt_10mhz_mohm"] > 9
    assert (tmp_path / "S02_optimised_braid.html").read_text().count("<svg") == 1
    rc = main(["legacy", str(archive / "raw" / "S02_optimised_braid.dat")])
    assert rc == 0 and "SHIELDEVAL v3.2 RESULT" in capsys.readouterr().out
    assert main(["fixtures"]) == 0
