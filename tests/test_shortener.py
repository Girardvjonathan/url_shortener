import pytest

from app.shortener import MAX_ID, base62_decode, base62_encode, generate_unique_id


class TestBase62Encode:
    def test_zero(self):
        assert base62_encode(0) == "0"

    def test_61_is_z(self):
        assert base62_encode(61) == "z"

    def test_62_rolls_over(self):
        assert base62_encode(62) == "10"

    def test_max_id_is_zzz(self):
        assert base62_encode(238327) == "zzz"

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            base62_encode(-1)


class TestBase62Decode:
    def test_zero(self):
        assert base62_decode("0") == 0

    def test_z_is_61(self):
        assert base62_decode("z") == 61

    def test_10_is_62(self):
        assert base62_decode("10") == 62

    def test_zzz_is_max(self):
        assert base62_decode("zzz") == 238327


class TestRoundtrip:
    @pytest.mark.parametrize("num", [0, 1, 61, 62, 1000, 12345, 238327])
    def test_encode_decode_roundtrip(self, num):
        assert base62_decode(base62_encode(num)) == num


class TestGenerateUniqueId:
    def test_always_in_range(self):
        for _ in range(200):
            uid = generate_unique_id()
            assert 0 <= uid < MAX_ID

    def test_produces_different_values(self):
        ids = {generate_unique_id() for _ in range(30)}
        assert len(ids) > 1
