from app.utils.hh_resume import candidate_link_matches_resume_id, normalize_hh_resume_id


def test_normalize_hh_resume_id_from_url():
    assert normalize_hh_resume_id("https://hh.ru/resume/09866c49ff00") == "09866c49ff00"
    assert normalize_hh_resume_id("09866c49ff00") == "09866c49ff00"
    assert normalize_hh_resume_id(None) is None


def test_candidate_link_matches_resume_id():
    link = "https://hh.ru/resume/09866c49ff00?query=1"
    assert candidate_link_matches_resume_id(link, "09866c49ff00")
    assert candidate_link_matches_resume_id(link, "https://hh.ru/resume/09866c49ff00")
    assert not candidate_link_matches_resume_id(link, "deadbeef")
