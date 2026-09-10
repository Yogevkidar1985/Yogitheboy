from marketwatch.sources.yad2 import Yad2Source, parse_price


def test_parse_price():
    assert parse_price("1,200 ₪") == 1200
    assert parse_price(950) == 950
    assert parse_price("לא צוין מחיר") is None
    assert parse_price(0) is None


def test_parse_gateway_json_shape():
    data = {
        "data": {
            "feed": {
                "feed_items": [
                    {"type": "ad", "token": "abcd1234", "title": "iPhone 13", "price": "1,400 ₪",
                     "city": "תל אביב", "img_url": "https://img/1.jpg"},
                    {"type": "banner", "id": 5},  # no price -> ignored
                    {"token": "efgh5678", "title": "iPhone 12", "price": "לא צוין מחיר", "city": "חיפה"},
                ]
            }
        }
    }
    items = {l.listing_id: l for l in Yad2Source.parse_json(data)}
    assert set(items) == {"abcd1234", "efgh5678"}
    a = items["abcd1234"]
    assert a.price == 1400 and a.location == "תל אביב" and a.url.endswith("/item/abcd1234")
    assert items["efgh5678"].price is None


def test_parse_next_data_html():
    html = ('<html><script id="__NEXT_DATA__" type="application/json">'
            '{"props":{"pageProps":{"feed":[{"token":"zz99yy88","title":"אופניים חשמליים",'
            '"price":2300,"address":{"city":{"text":"רמת גן"}}}]}}}</script></html>')
    (l,) = Yad2Source.parse_html(html)
    assert l.title == "אופניים חשמליים" and l.price == 2300 and l.location == "רמת גן"


def test_parse_html_without_blob_is_empty():
    assert Yad2Source.parse_html("<html>captcha</html>") == []
