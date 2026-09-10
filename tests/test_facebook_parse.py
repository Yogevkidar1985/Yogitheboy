from marketwatch.sources.facebook import parse_card_text


def test_card_with_price_title_location():
    assert parse_card_text("₪1,200\niPhone 12 128GB\nTel Aviv, Israel") == (1200.0, "iPhone 12 128GB", "Tel Aviv, Israel")


def test_card_with_sale_price_takes_first():
    price, title, _ = parse_card_text("₪900₪1,200\nSamsung S21\nHaifa")
    assert price == 900 and title == "Samsung S21"


def test_card_free_and_no_price():
    assert parse_card_text("חינם\nספה\nחולון")[0] == 0.0
    assert parse_card_text("ספה\nחולון") == (None, "ספה", "חולון")
