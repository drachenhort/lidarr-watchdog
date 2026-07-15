from lidarr_watchdog.main import main


def test_main(capsys):
    main()
    assert capsys.readouterr().out == "lidarr-watchdog\n"
