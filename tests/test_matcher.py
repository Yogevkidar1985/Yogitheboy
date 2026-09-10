from marketwatch.matcher import matches, normalize
from marketwatch.models import Listing, SearchSpec


def L(title, price=1000.0, desc=""):
    return Listing(source="yad2", listing_id="abc123", title=title, price=price, url="u", description=desc)


def test_normalize_hebrew_finals_and_case():
    assert normalize("אופניים") == normalize("אופניימ")
    assert normalize("iPhone 13!") == "iphone 13"


def test_price_bounds():
    spec = SearchSpec(name="x", query="q", max_price=1500, min_price=300)
    assert matches(L("iphone", 1500), spec)[0]
    assert not matches(L("iphone", 1501), spec)[0]
    assert not matches(L("iphone", 299), spec)[0]


def test_no_price_rejected_unless_allowed():
    assert not matches(L("iphone", None), SearchSpec(name="x", query="q"))[0]
    assert matches(L("iphone", None), SearchSpec(name="x", query="q", allow_no_price=True))[0]


def test_keyword_filters():
    spec = SearchSpec(name="x", query="q", must_include=["13"], any_of=["pro", "max"], exclude=["שבור"])
    assert matches(L("iPhone 13 Pro"), spec)[0]
    assert not matches(L("iPhone 12 Pro"), spec)[0]          # missing required
    assert not matches(L("iPhone 13"), spec)[0]              # none of any_of
    assert not matches(L("iPhone 13 Max מסך שבור"), spec)[0]  # excluded
    assert matches(L("אייפון", desc="13 max במצב מעולה"), spec)[0]  # description counts
