def test_standings(make_client):
    rows = [{"team": "Spain", "points": 9, "matches_played": 3}]
    client = make_client([rows])
    resp = client.get("/analytics/standings")
    assert resp.status_code == 200
    assert resp.json() == rows


def test_leaderboard_rejects_unknown_metric(client):
    resp = client.get("/analytics/leaderboard?metric=not_a_real_column")
    assert resp.status_code == 422


def test_leaderboard_valid_metric(make_client):
    rows = [{"player_id": "P00001", "player_name": "Test Player", "goals": 5}]
    client = make_client([rows])
    resp = client.get("/analytics/leaderboard?metric=goals&limit=5")
    assert resp.status_code == 200
    assert resp.json() == rows


def test_player_ids(make_client):
    rows = [{"player_id": "P00001"}, {"player_id": "P00002"}]
    client = make_client([rows])
    resp = client.get("/analytics/players/ids")
    assert resp.status_code == 200
    assert resp.json() == ["P00001", "P00002"]


def test_player_not_found(make_client):
    client = make_client([[]])  # profile query returns no rows
    resp = client.get("/analytics/players/P99999")
    assert resp.status_code == 404


def test_player_profile_found(make_client):
    profile_row = [{"player_id": "P00001", "player_name": "Test Player", "goals": 3}]
    matches_rows = [{"match_id": "M00001", "goals": 1}]
    client = make_client([profile_row, matches_rows])
    resp = client.get("/analytics/players/P00001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile"]["player_name"] == "Test Player"
    assert body["matches"] == matches_rows


def test_team_not_found(make_client):
    client = make_client([[]])
    resp = client.get("/analytics/teams/Nowhereland")
    assert resp.status_code == 404


def test_match_not_found(make_client):
    client = make_client([[]])
    resp = client.get("/analytics/matches/M99999")
    assert resp.status_code == 404


def test_match_detail_found(make_client):
    match_row = [{"match_id": "M00001", "team_a": "France", "team_b": "Brazil", "goals_a": 2, "goals_b": 1}]
    box_score_rows = [{"player_name": "Kylian Mbappe", "team": "France", "goals": 2}]
    client = make_client([match_row, box_score_rows])
    resp = client.get("/analytics/matches/M00001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["match"]["team_a"] == "France"
    assert body["box_score"] == box_score_rows
